"""Telas de PROTÓTIPO (Etapa 2): mostram o layout previsto, ainda sem ligação com o banco.

Profissionais e Consultas serão implementados nas próximas etapas.
"""
import customtkinter as ctk

from ui import componentes, tema


class _TelaBase(ctk.CTkFrame):
    NOME_MENU = ""        # texto do cartão no menu lateral
    TITULO = ""           # título grande da tela
    SUBTITULO = ""
    TITULO_FORM = ""      # título do cartão do formulário
    CAMPOS = []           # (rótulo, tipo, opções)  tipo: "texto" | "lista"
    BOTOES = []
    COLUNAS = []

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # a tabela é a que estica

        componentes.cabecalho(self, self.TITULO, self.SUBTITULO).grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        # Faixa de aviso: deixa claro que a tela ainda não funciona.
        aviso = ctk.CTkFrame(
            self, fg_color=tema.COR_AVISO_FUNDO, corner_radius=tema.RAIO_BOTAO
        )
        aviso.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(
            aviso,
            text="PROTÓTIPO — tela prevista para as próximas etapas (ainda não funciona).",
            font=tema.fonte(12, True), text_color=tema.COR_AVISO_TEXTO, anchor="w",
        ).pack(fill="x", padx=14, pady=8)

        self._montar_formulario()
        self._montar_tabela()

    def _montar_formulario(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        componentes.titulo_cartao(cartao, self.TITULO_FORM)

        grade = ctk.CTkFrame(cartao, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        grade.grid_columnconfigure(0, weight=1, uniform="campos")
        grade.grid_columnconfigure(1, weight=1, uniform="campos")
        for i, (rotulo, tipo, opcoes) in enumerate(self.CAMPOS):
            if tipo == "lista":
                bloco = ctk.CTkFrame(grade, fg_color="transparent")
                ctk.CTkLabel(
                    bloco, text=rotulo, font=tema.fonte(12, True),
                    text_color=tema.COR_TEXTO, anchor="w",
                ).pack(fill="x")
                lista = ctk.CTkComboBox(
                    bloco, values=opcoes or [""], height=38,
                    corner_radius=tema.RAIO_BOTAO, border_color=tema.COR_BORDA,
                    fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO,
                    button_color=tema.COR_BORDA, font=tema.fonte(13),
                )
                lista.set("")  # começa vazio (sem o texto padrão da biblioteca)
                lista.configure(state="disabled")  # protótipo: não funciona ainda
                lista.pack(fill="x", pady=(4, 0))
            else:
                bloco, _entrada = componentes.campo_texto(
                    grade, rotulo, estado="disabled"
                )
            bloco.grid(
                row=i // 2, column=i % 2, sticky="ew",
                padx=(0, 8) if i % 2 == 0 else (8, 0), pady=(0, 12),
            )

        botoes = ctk.CTkFrame(cartao, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(2, 20))
        for i, texto in enumerate(self.BOTOES):
            componentes.botao(
                botoes, texto, estilo="primario" if i == 0 else "secundario",
                largura=150, state="disabled",
            ).pack(side="left", padx=(0, 10))

    def _montar_tabela(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=3, column=0, sticky="nsew")
        quadro, _tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=5)
        quadro.pack(fill="both", expand=True, padx=20, pady=20)


class TelaProfissionais(_TelaBase):
    NOME_MENU = "Profissionais"
    TITULO = "Profissionais"
    SUBTITULO = "Médicos e demais profissionais da clínica."
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
    NOME_MENU = "Consultas"
    TITULO = "Consultas"
    SUBTITULO = "Agende, remarque e acompanhe as consultas."
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
