"""Tela de cadastro de pacientes (cadastrar, listar, buscar, alterar, desativar e excluir).

Visual em CustomTkinter. A lógica (validações, banco) continua em `services/`.
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import pacientes
from services.validacoes import (
    MSG_EMAIL,
    ErroValidacao,
    email_valido,
    formatar_cpf,
    formatar_telefone,
    iso_para_data_br,
    mascara_data,
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
        entrada.after_idle(lambda: entrada.icursor("end"))  # cursor sempre no final

    variavel.trace_add("write", ao_alterar)


class TelaPacientes(ctk.CTkFrame):
    NOME_MENU = "Pacientes"  # texto do cartão no menu lateral
    COLUNAS = (
        ("id", "ID", 50),
        ("nome", "Nome", 165),
        ("cpf", "CPF", 128),
        ("nascimento", "Nascimento", 108),
        ("telefone", "Telefone", 138),
        ("email", "E-mail", 190),
        ("situacao", "Situação", 80),
    )

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.id_selecionado = None  # None = cadastrando; número = editando

        self.var_nome = ctk.StringVar()
        self.var_cpf = ctk.StringVar()
        self.var_nascimento = ctk.StringVar()
        self.var_telefone = ctk.StringVar()
        self.var_email = ctk.StringVar()
        self.var_busca = ctk.StringVar()
        self.var_mostrar_inativos = ctk.BooleanVar(value=True)

        # A linha 2 (tabela) é a que estica quando a janela cresce.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Pacientes", "Cadastre, busque, altere, desative e exclua pacientes."
        ).grid(row=0, column=0, sticky="w", pady=(0, 16))
        self._montar_formulario()
        self._montar_lista()
        self.atualizar_lista()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        self.cartao_form = componentes.cartao(self)
        self.cartao_form.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.titulo_form = componentes.titulo_cartao(self.cartao_form, "Novo paciente")

        # Grade de campos: 3 colunas iguais.
        grade = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1, uniform="campos")

        # (rótulo, dica, variável, linha, coluna, quantas colunas ocupa)
        campos = [
            ("Nome *", "", self.var_nome, 0, 0, 2),
            ("CPF *", "só números", self.var_cpf, 0, 2, 1),
            ("Nascimento *", "DD/MM/AAAA", self.var_nascimento, 1, 0, 1),
            ("Telefone", "(86) 99999-9999", self.var_telefone, 1, 1, 1),
            ("E-mail", "", self.var_email, 1, 2, 1),
        ]
        entradas, blocos = {}, {}
        for rotulo, dica, variavel, linha, coluna, ocupa in campos:
            bloco, entrada = componentes.campo_texto(grade, rotulo, variavel, dica)
            blocos[rotulo] = bloco
            bloco.grid(
                row=linha, column=coluna, columnspan=ocupa, sticky="ew",
                padx=(0 if coluna == 0 else 8, 8 if coluna + ocupa < 3 else 0),
                pady=(0, 12),
            )
            entradas[rotulo] = entrada

        self.entrada_nome = entradas["Nome *"]
        # CPF e telefone: só números, sem pontuação. Data: barras automáticas.
        aplicar_mascara(self.var_cpf, lambda t: somente_digitos(t)[:11], entradas["CPF *"])
        aplicar_mascara(self.var_nascimento, mascara_data, entradas["Nascimento *"])
        aplicar_mascara(self.var_telefone, mascara_telefone, entradas["Telefone"])
        # Erros de telefone e e-mail aparecem logo abaixo do campo (e o back-end confere de novo).
        self.validar_telefone = componentes.anexar_validacao(
            blocos["Telefone"], entradas["Telefone"], self.var_telefone,
            lambda t: motivo_telefone_invalido(t) if somente_digitos(t) else None,
        )
        self.validar_email = componentes.anexar_validacao(
            blocos["E-mail"], entradas["E-mail"], self.var_email,
            lambda t: None if not t.strip() or email_valido(t) else MSG_EMAIL,
        )

        botoes = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(2, 20))
        self.botao_salvar = componentes.botao(botoes, "Cadastrar", self.salvar, largura=170)
        self.botao_salvar.pack(side="left")
        componentes.botao(
            botoes, "Limpar / Novo", self.limpar, estilo="secundario"
        ).pack(side="left", padx=10)
        self.botao_ativo = componentes.botao(
            botoes, "Desativar", self.alternar_ativo, estilo="secundario", state="disabled"
        )
        self.botao_ativo.pack(side="left", padx=(0, 10))
        self.botao_excluir = componentes.botao(
            botoes, "Excluir", self.excluir, estilo="perigo", state="disabled"
        )
        self.botao_excluir.pack(side="left")

    def _montar_lista(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="nsew")
        cartao.grid_columnconfigure(0, weight=1)
        cartao.grid_rowconfigure(1, weight=1)

        # Barra de busca (filtra enquanto digita)
        busca = ctk.CTkFrame(cartao, fg_color="transparent")
        busca.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        quadro_busca, _entrada = componentes.barra_busca(
            busca, "Buscar por nome ou CPF:", self.var_busca, self.atualizar_lista
        )
        quadro_busca.pack(side="left")
        ctk.CTkSwitch(
            busca, text="Mostrar desativados", variable=self.var_mostrar_inativos,
            command=self.atualizar_lista, font=tema.fonte(12),
            text_color=tema.COR_TEXTO, progress_color=tema.COR_PRIMARIA,
        ).pack(side="left", padx=(16, 0))

        # Tabela
        quadro, self.tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=6)
        quadro.grid(row=1, column=0, sticky="nsew", padx=20)
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ctk.CTkLabel(
            cartao, text="", font=tema.fonte(12),
            text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self.rotulo_total.grid(row=2, column=0, sticky="w", padx=20, pady=(8, 14))

    # ------------------------------------------------------------- dados
    def atualizar_lista(self):
        """Recarrega a tabela a partir do banco, respeitando a busca atual."""
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        try:
            lista = pacientes.listar(
                self.var_busca.get(), incluir_inativos=self.var_mostrar_inativos.get()
            )
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return
        for p in lista:
            self.tabela.insert(
                "",
                "end",
                iid=str(p["id"]),
                values=(
                    p["id"],
                    p["nome"],
                    formatar_cpf(p["cpf"]),
                    iso_para_data_br(p["data_nascimento"]),
                    formatar_telefone(p["telefone"]),
                    p["email"] or "",
                    "Ativo" if p["ativo"] else "Desativado",
                ),
            )
        self.rotulo_total.configure(
            text=componentes.texto_total(len(lista), self.var_busca.get(), "paciente(s)")
        )

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        _id, nome, cpf, nascimento, telefone, email, situacao = self.tabela.item(
            selecionados[0], "values"
        )
        self.var_nome.set(nome)
        self.var_cpf.set(cpf)  # a máscara tira os pontos sozinha
        self.var_nascimento.set(nascimento)
        self.var_telefone.set(telefone)
        self.var_email.set(email)
        self.titulo_form.configure(text=f"Editando paciente #{self.id_selecionado}")
        self.botao_salvar.configure(text="Salvar alterações")
        self.botao_excluir.configure(state="normal")
        self.botao_ativo.configure(
            state="normal", text="Desativar" if situacao == "Ativo" else "Reativar"
        )

    # ------------------------------------------------------------ ações
    def salvar(self):
        # Validação na tela (o back-end confere de novo): mostra os erros e não salva.
        ok_telefone, ok_email = self.validar_telefone(), self.validar_email()
        if not (ok_telefone and ok_email):
            messagebox.showwarning(
                "Verifique os dados", "Corrija os campos destacados em vermelho antes de salvar."
            )
            return
        dados = (
            self.var_nome.get(),
            self.var_cpf.get(),
            self.var_nascimento.get(),
            self.var_telefone.get(),
            self.var_email.get(),
        )
        try:
            if self.id_selecionado is None:
                pacientes.cadastrar(*dados)
                mensagem = "Paciente cadastrado com sucesso."
            else:
                pacientes.atualizar(self.id_selecionado, *dados)
                mensagem = "Dados do paciente atualizados com sucesso."
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível salvar: {erro}")
            return
        messagebox.showinfo("Sucesso", mensagem)
        self.limpar()
        self.atualizar_lista()

    def excluir(self):
        if self.id_selecionado is None:
            return
        nome = self.var_nome.get()
        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Tem certeza que deseja excluir o paciente '{nome}'?\nEsta ação não pode ser desfeita.",
        ):
            return
        try:
            pacientes.excluir(self.id_selecionado)
        except ErroValidacao as erro:
            messagebox.showwarning("Não foi possível excluir", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível excluir: {erro}")
            return
        messagebox.showinfo("Sucesso", "Paciente excluído com sucesso.")
        self.limpar()
        self.atualizar_lista()

    def alternar_ativo(self):
        """Desativa (exclusão lógica) ou reativa o paciente selecionado, preservando o histórico."""
        if self.id_selecionado is None:
            return
        nome = self.var_nome.get()
        desativando = self.botao_ativo.cget("text") == "Desativar"
        if desativando and not messagebox.askyesno(
            "Confirmar",
            f"Tem certeza que deseja desativar o paciente '{nome}'?\n"
            "Ele deixa de aparecer no agendamento, mas o histórico é mantido.",
        ):
            return
        try:
            novo = pacientes.alternar_ativo(self.id_selecionado)
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível alterar: {erro}")
            return
        messagebox.showinfo("Sucesso", "Paciente reativado." if novo else "Paciente desativado.")
        self.limpar()
        self.atualizar_lista()

    def limpar(self):
        """Volta o formulário para o modo 'novo paciente'."""
        self.id_selecionado = None
        for variavel in (
            self.var_nome,
            self.var_cpf,
            self.var_nascimento,
            self.var_telefone,
            self.var_email,
        ):
            variavel.set("")
        self.tabela.selection_remove(self.tabela.selection())
        self.titulo_form.configure(text="Novo paciente")
        self.botao_salvar.configure(text="Cadastrar")
        self.botao_excluir.configure(state="disabled")
        self.botao_ativo.configure(state="disabled", text="Desativar")
        self.entrada_nome.focus_set()
