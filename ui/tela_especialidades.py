"""Tela de especialidades: cadastro, valor da consulta, busca e exclusão.

O "valor da consulta" só pode ser alterado pelo super usuário. Para os outros usuários o
campo aparece bloqueado; e, mesmo que alguém contornasse a tela, o back-end
(`services/especialidades.py` e `services/financeiro.py`) confere a permissão de novo.
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import especialidades
from services.validacoes import (
    ErroValidacao,
    brl,
    centavos_para_campo,
    valor_para_centavos,
)
from ui import componentes, tema


class TelaEspecialidades(ctk.CTkFrame):
    NOME_MENU = "Especialidades"
    PRECISA_USUARIO = True  # o App entrega o usuário logado
    COLUNAS = (
        ("id", "ID", 50),
        ("nome", "Especialidade", 260),
        ("valor", "Valor da consulta", 160),
        ("medicos", "Médicos", 90),
    )

    def __init__(self, master, usuario_logado):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario_logado
        self.eh_super = bool(usuario_logado.get("superusuario"))
        self.id_selecionado = None

        self.var_nome = ctk.StringVar()
        self.var_valor = ctk.StringVar()
        self.var_busca = ctk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Especialidades",
            "Cadastre as especialidades e o valor da consulta de cada uma.",
        ).grid(row=0, column=0, sticky="w", pady=(0, 16))

        self._montar_formulario()
        self._montar_lista()
        self.atualizar_lista()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.titulo_form = componentes.titulo_cartao(cartao, "Nova especialidade")

        grade = ctk.CTkFrame(cartao, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        grade.grid_columnconfigure(0, weight=2, uniform="campos_esp")
        grade.grid_columnconfigure(1, weight=1, uniform="campos_esp")

        bloco, self.entrada_nome = componentes.campo_texto(grade, "Nome *", self.var_nome)
        bloco.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 12))

        dica = "R$ — ex.: 150,00" if self.eh_super else "só o super usuário altera"
        bloco, self.entrada_valor = componentes.campo_texto(
            grade, "Valor da consulta", self.var_valor, dica=dica,
            estado="normal" if self.eh_super else "disabled",
        )
        bloco.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 12))

        botoes = ctk.CTkFrame(cartao, fg_color="transparent")
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

        busca, _entrada = componentes.barra_busca(
            cartao, "Buscar especialidade:", self.var_busca, self.atualizar_lista
        )
        busca.grid(row=0, column=0, sticky="w", padx=20, pady=(18, 10))

        quadro, self.tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=6)
        quadro.grid(row=1, column=0, sticky="nsew", padx=20)
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ctk.CTkLabel(
            cartao, text="", font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE, anchor="w"
        )
        self.rotulo_total.grid(row=2, column=0, sticky="w", padx=20, pady=(8, 14))

    # ------------------------------------------------------------- dados
    def atualizar_lista(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        try:
            lista = especialidades.listar(self.var_busca.get())
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return
        for e in lista:
            self.tabela.insert(
                "", "end", iid=str(e["id"]),
                values=(e["id"], e["nome"], brl(e["valor_consulta"]), e["total_medicos"]),
            )
        self.rotulo_total.configure(
            text=componentes.texto_total(len(lista), self.var_busca.get(), "especialidade(s)")
        )

    def _definir_valor_campo(self, texto):
        """O campo do valor fica bloqueado para quem não é super usuário."""
        self.entrada_valor.configure(state="normal")
        self.var_valor.set(texto)
        if not self.eh_super:
            self.entrada_valor.configure(state="disabled")

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        esp = especialidades.obter(self.id_selecionado)
        if not esp:
            return
        self.var_nome.set(esp["nome"])
        self._definir_valor_campo(centavos_para_campo(esp["valor_consulta"]))
        self.titulo_form.configure(text=f"Editando especialidade #{self.id_selecionado}")
        self.botao_salvar.configure(text="Salvar alterações")
        self.botao_excluir.configure(state="normal")

    # ------------------------------------------------------------ ações
    def salvar(self):
        try:
            valor = None
            if self.eh_super and self.var_valor.get().strip():
                valor = valor_para_centavos(self.var_valor.get())
            elif self.eh_super and self.id_selecionado is None:
                valor = 0
            if self.id_selecionado is None:
                especialidades.cadastrar(
                    self.var_nome.get(), valor or 0, executor_id=self.usuario["id"]
                )
                mensagem = "Especialidade cadastrada com sucesso."
            else:
                especialidades.atualizar(
                    self.id_selecionado, self.var_nome.get(), valor,
                    executor_id=self.usuario["id"],
                )
                mensagem = "Especialidade atualizada com sucesso."
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
            f"Tem certeza que deseja excluir a especialidade '{nome}'?\n"
            "Esta ação não pode ser desfeita.",
        ):
            return
        try:
            especialidades.excluir(self.id_selecionado)
        except ErroValidacao as erro:
            messagebox.showwarning("Não foi possível excluir", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível excluir: {erro}")
            return
        messagebox.showinfo("Sucesso", "Especialidade excluída com sucesso.")
        self.limpar()
        self.atualizar_lista()

    def limpar(self):
        self.id_selecionado = None
        self.var_nome.set("")
        self._definir_valor_campo("")
        self.tabela.selection_remove(self.tabela.selection())
        self.titulo_form.configure(text="Nova especialidade")
        self.botao_salvar.configure(text="Cadastrar")
        self.botao_excluir.configure(state="disabled")
        self.entrada_nome.focus_set()
