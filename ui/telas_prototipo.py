"""Telas de PROTÓTIPO (Etapa 2): mostram o layout previsto, ainda sem ligação com o banco.

Profissionais e Consultas serão implementados nas próximas etapas.
"""
import tkinter as tk
from tkinter import ttk


def _desativar(widget):
    """Desativa recursivamente os campos e botões do protótipo."""
    for filho in widget.winfo_children():
        try:
            filho.configure(state="disabled")
        except tk.TclError:
            pass
        _desativar(filho)


class _TelaBase(ttk.Frame):
    TITULO_FORM = ""
    CAMPOS = []  # (rótulo, tipo, opções)  tipo: "texto" | "lista"
    BOTOES = []
    COLUNAS = []

    def __init__(self, master):
        super().__init__(master, padding=10)
        aviso = ttk.Label(
            self,
            text="PROTÓTIPO — tela prevista para as próximas etapas (ainda não funciona).",
            foreground="#b45309",
        )
        aviso.pack(anchor="w", pady=(0, 8))

        quadro = ttk.LabelFrame(self, text=self.TITULO_FORM, padding=10)
        quadro.pack(fill="x")
        for linha, (rotulo, tipo, opcoes) in enumerate(self.CAMPOS):
            ttk.Label(quadro, text=rotulo).grid(row=linha, column=0, sticky="w", pady=3)
            if tipo == "lista":
                campo = ttk.Combobox(quadro, values=opcoes, width=37, state="readonly")
            else:
                campo = ttk.Entry(quadro, width=40)
            campo.grid(row=linha, column=1, sticky="w", padx=8, pady=3)

        botoes = ttk.Frame(quadro)
        botoes.grid(row=len(self.CAMPOS), column=0, columnspan=2, sticky="w", pady=(10, 0))
        for texto in self.BOTOES:
            ttk.Button(botoes, text=texto).pack(side="left", padx=(0, 6))

        tabela = ttk.Treeview(
            self, columns=[c[0] for c in self.COLUNAS], show="headings", height=8
        )
        for chave, titulo, largura in self.COLUNAS:
            tabela.heading(chave, text=titulo)
            tabela.column(chave, width=largura, anchor="w")
        tabela.pack(fill="both", expand=True, pady=(12, 0))

        _desativar(quadro)


class TelaProfissionais(_TelaBase):
    TITULO_FORM = "Novo profissional"
    CAMPOS = [
        ("Nome *", "texto", None),
        ("Registro profissional * (ex.: CRM)", "texto", None),
        ("Especialidade *", "lista", ["Clínica Geral", "Pediatria", "Cardiologia"]),
        ("Telefone (com DDD)", "texto", None),
    ]
    BOTOES = ["Cadastrar", "Limpar / Novo", "Inativar", "Excluir"]
    COLUNAS = [
        ("id", "ID", 50),
        ("nome", "Nome", 230),
        ("registro", "Registro", 120),
        ("especialidade", "Especialidade", 160),
        ("telefone", "Telefone", 120),
        ("ativo", "Situação", 90),
    ]


class TelaConsultas(_TelaBase):
    TITULO_FORM = "Agendar consulta"
    CAMPOS = [
        ("Paciente *", "lista", []),
        ("Profissional *", "lista", []),
        ("Data * (DD/MM/AAAA)", "texto", None),
        ("Horário * (HH:MM)", "texto", None),
        ("Observações", "texto", None),
    ]
    BOTOES = ["Agendar", "Remarcar", "Cancelar consulta", "Marcar como realizada"]
    COLUNAS = [
        ("id", "ID", 50),
        ("data", "Data", 90),
        ("hora", "Horário", 70),
        ("paciente", "Paciente", 200),
        ("profissional", "Profissional", 200),
        ("situacao", "Situação", 100),
    ]
