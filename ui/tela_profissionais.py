"""Tela de cadastro e gerenciamento de profissionais de saúde.

Visual em CustomTkinter. A lógica (validações, banco) fica em `services/profissionais`.
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import profissionais
from services.validacoes import (
    ErroValidacao,
    formatar_telefone,
    mascara_telefone,
    motivo_telefone_invalido,
    somente_digitos,
)
from ui import componentes, tema


def aplicar_mascara(variavel, funcao, entrada):
    """Ajusta o campo enquanto o usuário digita e mantém o cursor no final."""

    def ao_alterar(*_):
        novo = funcao(variavel.get())
        if novo != variavel.get():
            variavel.set(novo)
        entrada.after_idle(lambda: entrada.icursor("end"))

    variavel.trace_add("write", ao_alterar)


class TelaProfissionais(ctk.CTkFrame):
    NOME_MENU = "Profissionais"
    COLUNAS = (
        ("id", "ID", 50),
        ("nome", "Nome", 215),
        ("registro", "Registro (CRM)", 135),
        ("especialidade", "Especialidade", 150),
        ("telefone", "Telefone", 150),
        ("ativo", "Situação", 85),
    )

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.id_selecionado = None
        self.ativo_selecionado = 1

        self.var_nome = ctk.StringVar()
        self.var_registro = ctk.StringVar()
        self.var_especialidade = ctk.StringVar()
        self.var_telefone = ctk.StringVar()
        self.var_busca = ctk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Profissionais", "Cadastre, consulte, altere e inative profissionais da saúde."
        ).grid(row=0, column=0, sticky="w", pady=(0, 16))

        self._montar_formulario()
        self._montar_lista()
        self.recarregar_especialidades()
        self.atualizar_lista()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        self.cartao_form = componentes.cartao(self)
        self.cartao_form.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.titulo_form = componentes.titulo_cartao(self.cartao_form, "Novo profissional")

        grade = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1, uniform="campos_prof")

        # Linha 0: Nome (ocupa 2 colunas) e Registro (1 coluna)
        bloco_nome, self.entrada_nome = componentes.campo_texto(
            grade, "Nome *", self.var_nome, dica="nome completo"
        )
        bloco_nome.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(0, 12))

        bloco_reg, self.entrada_registro = componentes.campo_texto(
            grade, "Registro profissional *", self.var_registro, dica="ex.: CRM/SP 123456"
        )
        bloco_reg.grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=(0, 12))

        # Linha 1: Especialidade (ocupa 2 colunas) e Telefone (1 coluna)
        bloco_esp, self.combo_especialidade = componentes.campo_combobox(
            grade, "Especialidade *", valores=[""], variavel=self.var_especialidade,
            dica="selecione ou digite nova"
        )
        bloco_esp.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(0, 12))

        bloco_tel, self.entrada_telefone = componentes.campo_texto(
            grade, "Telefone", self.var_telefone, dica="(86) 99999-9999"
        )
        bloco_tel.grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=(0, 12))

        aplicar_mascara(self.var_telefone, mascara_telefone, self.entrada_telefone)
        self.validar_telefone = componentes.anexar_validacao(
            bloco_tel, self.entrada_telefone, self.var_telefone,
            lambda t: motivo_telefone_invalido(t) if somente_digitos(t) else None,
        )

        botoes = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(2, 20))
        self.botao_salvar = componentes.botao(botoes, "Cadastrar", self.salvar, largura=170)
        self.botao_salvar.pack(side="left")
        componentes.botao(
            botoes, "Limpar / Novo", self.limpar, estilo="secundario"
        ).pack(side="left", padx=10)

        self.botao_inativar = componentes.botao(
            botoes, "Inativar", self.alternar_status, estilo="secundario", state="disabled"
        )
        self.botao_inativar.pack(side="left", padx=(0, 10))

        self.botao_excluir = componentes.botao(
            botoes, "Excluir", self.excluir, estilo="perigo", state="disabled"
        )
        self.botao_excluir.pack(side="left")

    def _montar_lista(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="nsew")
        cartao.grid_columnconfigure(0, weight=1)
        cartao.grid_rowconfigure(1, weight=1)

        busca = ctk.CTkFrame(cartao, fg_color="transparent")
        busca.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        quadro_busca, _entrada = componentes.barra_busca(
            busca, "Buscar por nome ou especialidade:", self.var_busca, self.atualizar_lista
        )
        quadro_busca.pack(side="left")

        quadro, self.tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=6)
        quadro.grid(row=1, column=0, sticky="nsew", padx=20)
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ctk.CTkLabel(
            cartao, text="", font=tema.fonte(12),
            text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self.rotulo_total.grid(row=2, column=0, sticky="w", padx=20, pady=(8, 14))

    # ------------------------------------------------------------- dados
    def recarregar_especialidades(self):
        """Atualiza a lista de opções do combobox com as especialidades do banco."""
        try:
            lista = profissionais.listar_especialidades()
            nomes = [e["nome"] for e in lista]
            self.combo_especialidade.configure(values=nomes or ["Clínica Geral"])
            if not self.var_especialidade.get() and nomes:
                self.var_especialidade.set(nomes[0])
        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro no banco de dados",
                f"Não foi possível carregar as especialidades: {erro}",
            )

    def atualizar_lista(self):
        """Recarrega a tabela a partir do banco de dados."""
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        try:
            lista = profissionais.listar(self.var_busca.get())
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return
        for p in lista:
            situacao = "Ativo" if p["ativo"] == 1 else "Inativo"
            self.tabela.insert(
                "",
                "end",
                iid=str(p["id"]),
                values=(
                    p["id"],
                    p["nome"],
                    p["registro"],
                    p["especialidade"],
                    formatar_telefone(p["telefone"]) if p["telefone"] else "",
                    situacao,
                ),
            )
        self.rotulo_total.configure(
            text=componentes.texto_total(len(lista), self.var_busca.get(), "profissional(is)")
        )

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        _id, nome, registro, especialidade, telefone, situacao = self.tabela.item(
            selecionados[0], "values"
        )
        self.var_nome.set(nome)
        self.var_registro.set(registro)
        self.var_especialidade.set(especialidade)
        self.var_telefone.set(telefone)
        self.ativo_selecionado = 1 if situacao == "Ativo" else 0

        self.titulo_form.configure(text=f"Editando profissional #{self.id_selecionado}")
        self.botao_salvar.configure(text="Salvar alterações")
        self.botao_excluir.configure(state="normal")
        self.botao_inativar.configure(
            state="normal",
            text="Inativar" if self.ativo_selecionado == 1 else "Reativar",
        )

    # ------------------------------------------------------------ ações
    def salvar(self):
        if not self.validar_telefone():  # erro aparece abaixo do campo; o back-end confere de novo
            messagebox.showwarning(
                "Verifique os dados", "Corrija os campos destacados em vermelho antes de salvar."
            )
            return
        dados = (
            self.var_nome.get(),
            self.var_registro.get(),
            self.var_especialidade.get(),
            self.var_telefone.get(),
        )
        try:
            if self.id_selecionado is None:
                profissionais.cadastrar(*dados)
                mensagem = "Profissional cadastrado com sucesso."
            else:
                profissionais.atualizar(self.id_selecionado, *dados, ativo=self.ativo_selecionado)
                mensagem = "Dados do profissional atualizados com sucesso."
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível salvar: {erro}")
            return
        messagebox.showinfo("Sucesso", mensagem)
        self.recarregar_especialidades()
        self.limpar()
        self.atualizar_lista()

    def alternar_status(self):
        if self.id_selecionado is None:
            return
        try:
            novo = profissionais.alternar_ativo(self.id_selecionado)
            status_txt = "reativado" if novo == 1 else "inativado"
            messagebox.showinfo("Sucesso", f"Profissional {status_txt} com sucesso.")
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro", f"Não foi possível alterar a situação: {erro}")
            return
        self.limpar()
        self.atualizar_lista()

    def excluir(self):
        if self.id_selecionado is None:
            return
        nome = self.var_nome.get()
        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Tem certeza que deseja excluir o cadastro de '{nome}'?\nEsta ação não pode ser desfeita.",
        ):
            return
        try:
            profissionais.excluir(self.id_selecionado)
        except ErroValidacao as erro:
            messagebox.showwarning("Não foi possível excluir", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível excluir: {erro}")
            return
        messagebox.showinfo("Sucesso", "Profissional excluído com sucesso.")
        self.limpar()
        self.atualizar_lista()

    def limpar(self):
        self.id_selecionado = None
        self.ativo_selecionado = 1
        self.var_nome.set("")
        self.var_registro.set("")
        self.var_telefone.set("")
        self.tabela.selection_remove(self.tabela.selection())
        self.titulo_form.configure(text="Novo profissional")
        self.botao_salvar.configure(text="Cadastrar")
        self.botao_excluir.configure(state="disabled")
        self.botao_inativar.configure(state="disabled", text="Inativar")
        self.entrada_nome.focus_set()
