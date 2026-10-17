"""Tela de cadastro de pacientes (cadastrar, listar, buscar, alterar e excluir).

Visual em CustomTkinter. A lógica (validações, banco) continua em `services/`.
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import pacientes
from services.validacoes import (
    ErroValidacao,
    formatar_cpf,
    formatar_telefone,
    iso_para_data_br,
    mascara_data,
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
        ("nome", "Nome", 230),
        ("cpf", "CPF", 130),
        ("nascimento", "Nascimento", 110),
        ("telefone", "Telefone", 130),
        ("email", "E-mail", 220),
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

        # A linha 2 (tabela) é a que estica quando a janela cresce.
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Pacientes", "Cadastre, busque, altere e exclua pacientes."
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
            ("Telefone", "com DDD", self.var_telefone, 1, 1, 1),
            ("E-mail", "", self.var_email, 1, 2, 1),
        ]
        entradas = {}
        for rotulo, dica, variavel, linha, coluna, ocupa in campos:
            bloco, entrada = componentes.campo_texto(grade, rotulo, variavel, dica)
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
        aplicar_mascara(
            self.var_telefone, lambda t: somente_digitos(t)[:11], entradas["Telefone"]
        )

        botoes = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(2, 20))
        self.botao_salvar = componentes.botao(botoes, "Cadastrar", self.salvar, largura=170)
        self.botao_salvar.pack(side="left")
        componentes.botao(
            botoes, "Limpar / Novo", self.limpar, estilo="secundario"
        ).pack(side="left", padx=10)
        self.botao_excluir = componentes.botao(
            botoes, "Excluir", self.excluir, estilo="perigo", state="disabled"
        )
        self.botao_excluir.pack(side="left")

    def _montar_lista(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="nsew")
        cartao.grid_columnconfigure(0, weight=1)
        cartao.grid_rowconfigure(1, weight=1)

        # Barra de busca
        busca = ctk.CTkFrame(cartao, fg_color="transparent")
        busca.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        ctk.CTkLabel(
            busca, text="Buscar por nome ou CPF:", font=tema.fonte(12, True),
            text_color=tema.COR_TEXTO,
        ).pack(side="left", padx=(0, 10))
        entrada = ctk.CTkEntry(
            busca, textvariable=self.var_busca, width=280, height=38,
            corner_radius=tema.RAIO_BOTAO, border_color=tema.COR_BORDA,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO, font=tema.fonte(13),
        )
        entrada.pack(side="left")
        entrada.bind("<Return>", lambda _e: self.buscar())
        componentes.botao(busca, "Buscar", self.buscar, largura=100).pack(side="left", padx=10)
        componentes.botao(
            busca, "Mostrar todos", self.mostrar_todos, estilo="secundario"
        ).pack(side="left")

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
            lista = pacientes.listar(self.var_busca.get())
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
                ),
            )
        self.rotulo_total.configure(text=f"{len(lista)} paciente(s) listado(s).")

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        _id, nome, cpf, nascimento, telefone, email = self.tabela.item(selecionados[0], "values")
        self.var_nome.set(nome)
        self.var_cpf.set(cpf)  # a máscara tira os pontos sozinha
        self.var_nascimento.set(nascimento)
        self.var_telefone.set(telefone)
        self.var_email.set(email)
        self.titulo_form.configure(text=f"Editando paciente #{self.id_selecionado}")
        self.botao_salvar.configure(text="Salvar alterações")
        self.botao_excluir.configure(state="normal")

    # ------------------------------------------------------------ ações
    def salvar(self):
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
        if not messagebox.askyesno("Confirmar exclusão", f"Excluir o paciente '{nome}'?"):
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
        self.entrada_nome.focus_set()

    def buscar(self):
        self.atualizar_lista()

    def mostrar_todos(self):
        self.var_busca.set("")
        self.atualizar_lista()
