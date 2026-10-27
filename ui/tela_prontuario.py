"""Documentos salvos do paciente (atestados e receituários) - SÓ o super usuário vê.

Escolha o paciente na busca; a lista mostra tudo que foi emitido para ele, com o texto ao
lado e o botão de reimprimir. A permissão é conferida de novo no back-end (`services/documentos.py`).
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import documentos, pacientes
from services.validacoes import ErroValidacao, formatar_cpf
from ui import componentes, tema


class TelaProntuario(ctk.CTkFrame):
    NOME_MENU = "Prontuário"
    PRECISA_USUARIO = True  # o App entrega o usuário logado
    COLUNAS = (
        ("id", "ID", 50),
        ("data", "Emitido em", 130),
        ("tipo", "Documento", 110),
        ("medico", "Médico", 170),
        ("por", "Emitido por", 160),
    )

    def __init__(self, master, usuario_logado):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario_logado
        self.paciente = None
        self.id_documento = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        componentes.cabecalho(
            self, "Prontuário",
            "Atestados e receituários salvos de cada paciente (visível só para o super usuário).",
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        cartao = componentes.cartao(self)
        cartao.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.campo_paciente = componentes.CampoComSugestoes(
            cartao, "Paciente", self._buscar,
            lambda p: f"{p['nome']} (CPF: {formatar_cpf(p['cpf'])})"
                      + ("" if p["ativo"] else " [desativado]"),
            self._ao_escolher, dica="nome, CPF ou telefone", ao_limpar=self._ao_limpar,
        )
        self.campo_paciente.pack(fill="x", padx=20, pady=18)

        corpo = componentes.cartao(self)
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=3)
        corpo.grid_columnconfigure(1, weight=2)
        corpo.grid_rowconfigure(0, weight=1)

        quadro, self.tabela = componentes.criar_tabela(corpo, self.COLUNAS, altura=8)
        quadro.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=(18, 6))
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.previa = ctk.CTkTextbox(
            corpo, corner_radius=tema.RAIO_BOTAO, border_width=1, border_color=tema.COR_BORDA,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO, font=tema.fonte(12),
            wrap="word", state="disabled",
        )
        self.previa.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=(18, 6))

        rodape = ctk.CTkFrame(corpo, fg_color="transparent")
        rodape.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 14))
        self.botao_reimprimir = componentes.botao(
            rodape, "Reimprimir", self._reimprimir, largura=150, state="disabled"
        )
        self.botao_reimprimir.pack(side="left")
        self.rotulo = ctk.CTkLabel(
            rodape, text="Escolha um paciente para ver os documentos salvos.",
            font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE,
        )
        self.rotulo.pack(side="left", padx=14)

    # ------------------------------------------------------------- busca
    @staticmethod
    def _buscar(texto, limite):
        return pacientes.listar(texto, incluir_inativos=True, limite=limite)

    def _ao_escolher(self, paciente):
        self.paciente = paciente
        self.atualizar_lista()

    def _ao_limpar(self):
        self.paciente = None
        self.atualizar_lista()

    # ------------------------------------------------------------- dados
    def atualizar_lista(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        self._mostrar_texto("")
        self.id_documento = None
        self.botao_reimprimir.configure(state="disabled")
        if self.paciente is None:
            self.rotulo.configure(text="Escolha um paciente para ver os documentos salvos.")
            return
        try:
            lista = documentos.listar(self.usuario["id"], self.paciente["id"])
        except ErroValidacao as erro:
            messagebox.showwarning("Acesso negado", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return
        for d in lista:
            data = f"{d['data_hora'][8:10]}/{d['data_hora'][5:7]}/{d['data_hora'][:4]} {d['data_hora'][11:16]}"
            self.tabela.insert(
                "", "end", iid=str(d["id"]),
                values=(d["id"], data, d["tipo"], d["profissional_nome"], d["emitido_por_nome"]),
            )
        self.rotulo.configure(
            text=f"{len(lista)} documento(s) salvo(s)." if lista
            else "Nenhum documento salvo para este paciente."
        )

    def _mostrar_texto(self, texto):
        self.previa.configure(state="normal")
        self.previa.delete("1.0", "end")
        self.previa.insert("1.0", texto)
        self.previa.configure(state="disabled")

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_documento = int(selecionados[0])
        try:
            doc = documentos.obter(self.usuario["id"], self.id_documento)
        except (ErroValidacao, sqlite3.Error) as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        self._mostrar_texto(doc["texto"])
        self.botao_reimprimir.configure(state="normal")

    def _reimprimir(self):
        if self.id_documento is None:
            return
        try:
            documentos.reimprimir(self.usuario["id"], self.id_documento)
        except (ErroValidacao, sqlite3.Error) as erro:
            messagebox.showwarning("Aviso", str(erro))
