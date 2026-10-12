"""Tela de cadastro de pacientes (cadastrar, listar, buscar, alterar e excluir)."""
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from services import pacientes
from services.validacoes import (
    ErroValidacao,
    formatar_cpf,
    formatar_telefone,
    iso_para_data_br,
    mascara_data,
    somente_digitos,
)


def aplicar_mascara(variavel, funcao):
    """Faz o campo se ajustar sozinho enquanto o usuário digita ou cola."""

    def ao_alterar(*_):
        novo = funcao(variavel.get())
        if novo != variavel.get():
            variavel.set(novo)

    variavel.trace_add("write", ao_alterar)


class TelaPacientes(ttk.Frame):
    COLUNAS = (
        ("id", "ID", 50),
        ("nome", "Nome", 230),
        ("cpf", "CPF", 120),
        ("nascimento", "Nascimento", 100),
        ("telefone", "Telefone", 120),
        ("email", "E-mail", 200),
    )

    def __init__(self, master):
        super().__init__(master, padding=10)
        self.id_selecionado = None  # None = cadastrando; número = editando

        self.var_nome = tk.StringVar()
        self.var_cpf = tk.StringVar()
        self.var_nascimento = tk.StringVar()
        self.var_telefone = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_busca = tk.StringVar()

        # CPF e telefone: só números, sem pontuação. Data: barras automáticas.
        aplicar_mascara(self.var_cpf, lambda t: somente_digitos(t)[:11])
        aplicar_mascara(self.var_telefone, lambda t: somente_digitos(t)[:11])
        aplicar_mascara(self.var_nascimento, mascara_data)

        self._montar_formulario()
        self._montar_busca()
        self._montar_tabela()
        self.atualizar_lista()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        self.quadro = ttk.LabelFrame(self, text="Novo paciente", padding=10)
        self.quadro.pack(fill="x")

        campos = [
            ("Nome *", self.var_nome, 40, ""),
            ("CPF * (só números)", self.var_cpf, 14, "Ex.: 12345678909"),
            ("Nascimento * (DD/MM/AAAA)", self.var_nascimento, 14, "Ex.: 25/03/1990"),
            ("Telefone (com DDD)", self.var_telefone, 14, "Ex.: 11987654321"),
            ("E-mail", self.var_email, 40, ""),
        ]
        for linha, (rotulo, variavel, largura, dica) in enumerate(campos):
            ttk.Label(self.quadro, text=rotulo).grid(row=linha, column=0, sticky="w", pady=3)
            entrada = ttk.Entry(self.quadro, textvariable=variavel, width=largura)
            entrada.grid(row=linha, column=1, sticky="w", padx=8, pady=3)
            if dica:
                ttk.Label(self.quadro, text=dica, foreground="gray").grid(
                    row=linha, column=2, sticky="w"
                )
            if linha == 0:
                self.entrada_nome = entrada

        botoes = ttk.Frame(self.quadro)
        botoes.grid(row=len(campos), column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.botao_salvar = ttk.Button(botoes, text="Cadastrar", command=self.salvar)
        self.botao_salvar.pack(side="left")
        ttk.Button(botoes, text="Limpar / Novo", command=self.limpar).pack(side="left", padx=6)
        self.botao_excluir = ttk.Button(
            botoes, text="Excluir", command=self.excluir, state="disabled"
        )
        self.botao_excluir.pack(side="left")

    def _montar_busca(self):
        quadro = ttk.Frame(self)
        quadro.pack(fill="x", pady=(12, 4))
        ttk.Label(quadro, text="Buscar por nome ou CPF:").pack(side="left")
        entrada = ttk.Entry(quadro, textvariable=self.var_busca, width=30)
        entrada.pack(side="left", padx=6)
        entrada.bind("<Return>", lambda _e: self.buscar())
        ttk.Button(quadro, text="Buscar", command=self.buscar).pack(side="left")
        ttk.Button(quadro, text="Mostrar todos", command=self.mostrar_todos).pack(
            side="left", padx=6
        )

    def _montar_tabela(self):
        quadro = ttk.Frame(self)
        quadro.pack(fill="both", expand=True)
        self.tabela = ttk.Treeview(
            quadro,
            columns=[c[0] for c in self.COLUNAS],
            show="headings",
            selectmode="browse",
        )
        for chave, titulo, largura in self.COLUNAS:
            self.tabela.heading(chave, text=titulo)
            self.tabela.column(chave, width=largura, anchor="w")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ttk.Label(self, text="")
        self.rotulo_total.pack(anchor="w", pady=(4, 0))

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
        self.rotulo_total.config(text=f"{len(lista)} paciente(s) listado(s).")

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
        self.quadro.config(text=f"Editando paciente #{self.id_selecionado}")
        self.botao_salvar.config(text="Salvar alterações")
        self.botao_excluir.config(state="normal")

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
        self.quadro.config(text="Novo paciente")
        self.botao_salvar.config(text="Cadastrar")
        self.botao_excluir.config(state="disabled")
        self.entrada_nome.focus_set()

    def buscar(self):
        self.atualizar_lista()

    def mostrar_todos(self):
        self.var_busca.set("")
        self.atualizar_lista()
