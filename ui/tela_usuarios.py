"""Tela de gerência de usuários (só aparece para o super usuário).

Permite cadastrar novos usuários, alterar os já cadastrados (nome, login, senha,
perfil e situação) e excluí-los. A lógica e a conferência de permissão ficam em
`services/autenticacao`; aqui só há o visual.
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import autenticacao
from services.validacoes import ErroValidacao
from ui import componentes, tema


class TelaUsuarios(ctk.CTkFrame):
    NOME_MENU = "Usuários"
    PRECISA_USUARIO = True  # o App entrega o usuário logado
    COLUNAS = (
        ("id", "ID", 50),
        ("nome", "Nome", 240),
        ("login", "Usuário", 160),
        ("perfil", "Perfil", 150),
        ("situacao", "Situação", 100),
    )

    def __init__(self, master, usuario_logado):
        super().__init__(master, fg_color="transparent")
        self.usuario_logado = usuario_logado
        self.id_selecionado = None

        self.var_nome = ctk.StringVar()
        self.var_login = ctk.StringVar()
        self.var_senha = ctk.StringVar()
        self.var_mostrar = ctk.BooleanVar(value=False)
        self.var_super = ctk.BooleanVar(value=False)
        self.var_ativo = ctk.BooleanVar(value=True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Usuários", "Cadastre novos usuários e altere os dados ou a senha dos já cadastrados."
        ).grid(row=0, column=0, sticky="w", pady=(0, 16))

        self._montar_formulario()
        self._montar_lista()
        self.atualizar_lista()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.titulo_form = componentes.titulo_cartao(cartao, "Novo usuário")

        grade = ctk.CTkFrame(cartao, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1, uniform="campos_usuario")

        bloco, self.entrada_nome = componentes.campo_texto(grade, "Nome *", self.var_nome)
        bloco.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 12))

        bloco, self.entrada_login = componentes.campo_texto(
            grade, "Usuário (login) *", self.var_login, dica="sem diferenciar maiúsculas"
        )
        bloco.grid(row=0, column=1, sticky="ew", padx=8, pady=(0, 12))

        bloco, self.entrada_senha = componentes.campo_texto(
            grade, "Senha *", self.var_senha,
            dica=f"mín. {autenticacao.TAMANHO_MINIMO_SENHA} caracteres",
        )
        bloco.grid(row=0, column=2, sticky="ew", padx=(8, 0), pady=(0, 12))
        self.entrada_senha.configure(show="•")

        opcoes = ctk.CTkFrame(cartao, fg_color="transparent")
        opcoes.pack(fill="x", padx=20, pady=(0, 6))
        for texto, variavel in (
            ("Mostrar senha", self.var_mostrar),
            ("Super usuário (pode gerenciar usuários)", self.var_super),
            ("Usuário ativo", self.var_ativo),
        ):
            ctk.CTkCheckBox(
                opcoes, text=texto, variable=variavel, font=tema.fonte(12),
                text_color=tema.COR_TEXTO, fg_color=tema.COR_PRIMARIA,
                hover_color=tema.COR_PRIMARIA_HOVER, border_color=tema.COR_BORDA,
                checkbox_width=18, checkbox_height=18, corner_radius=5,
                command=self._alternar_senha if variavel is self.var_mostrar else None,
            ).pack(side="left", padx=(0, 22))

        botoes = ctk.CTkFrame(cartao, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(8, 20))
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
        cartao.grid_rowconfigure(0, weight=1)

        quadro, self.tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=6)
        quadro.grid(row=0, column=0, sticky="nsew", padx=20, pady=(18, 0))
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ctk.CTkLabel(
            cartao, text="", font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE, anchor="w"
        )
        self.rotulo_total.grid(row=1, column=0, sticky="w", padx=20, pady=(8, 14))

    # ------------------------------------------------------------- dados
    def atualizar_lista(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        try:
            lista = autenticacao.listar_usuarios(self.usuario_logado["id"])
        except ErroValidacao as erro:
            messagebox.showwarning("Acesso negado", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return
        for u in lista:
            self.tabela.insert(
                "", "end", iid=str(u["id"]),
                values=(
                    u["id"], u["nome"], u["login"],
                    "Super usuário" if u["superusuario"] else "Usuário",
                    "Ativo" if u["ativo"] else "Inativo",
                ),
            )
        self.rotulo_total.configure(text=f"{len(lista)} usuário(s) cadastrado(s).")

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        _id, nome, login, perfil, situacao = self.tabela.item(selecionados[0], "values")
        self.var_nome.set(nome)
        self.var_login.set(login)
        self.var_senha.set("")  # a senha atual nunca é mostrada
        self.var_super.set(perfil == "Super usuário")
        self.var_ativo.set(situacao == "Ativo")
        self.titulo_form.configure(
            text=f"Editando usuário #{self.id_selecionado} (senha em branco mantém a atual)"
        )
        self.botao_salvar.configure(text="Salvar alterações")
        self.botao_excluir.configure(state="normal")

    # ------------------------------------------------------------ ações
    def _alternar_senha(self):
        self.entrada_senha.configure(show="" if self.var_mostrar.get() else "•")

    def salvar(self):
        executor = self.usuario_logado["id"]
        try:
            if self.id_selecionado is None:
                autenticacao.cadastrar_usuario_por(
                    executor, self.var_nome.get(), self.var_login.get(),
                    self.var_senha.get(), self.var_super.get(),
                )
                mensagem = "Usuário cadastrado com sucesso."
            else:
                autenticacao.atualizar_usuario(
                    executor, self.id_selecionado, self.var_nome.get(), self.var_login.get(),
                    self.var_senha.get(), self.var_ativo.get(), self.var_super.get(),
                )
                mensagem = "Usuário atualizado com sucesso."
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
            f"Deseja excluir o usuário '{nome}'?\nEssa ação não pode ser desfeita "
            "(para só bloquear o acesso, desmarque \"Usuário ativo\" e salve).",
        ):
            return
        try:
            autenticacao.excluir_usuario(self.usuario_logado["id"], self.id_selecionado)
        except ErroValidacao as erro:
            messagebox.showwarning("Não foi possível excluir", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível excluir: {erro}")
            return
        messagebox.showinfo("Sucesso", "Usuário excluído com sucesso.")
        self.limpar()
        self.atualizar_lista()

    def limpar(self):
        self.id_selecionado = None
        for variavel in (self.var_nome, self.var_login, self.var_senha):
            variavel.set("")
        self.var_super.set(False)
        self.var_ativo.set(True)
        self.tabela.selection_remove(self.tabela.selection())
        self.titulo_form.configure(text="Novo usuário")
        self.botao_salvar.configure(text="Cadastrar")
        self.botao_excluir.configure(state="disabled")
        self.entrada_nome.focus_set()
