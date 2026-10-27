"""Peças visuais reutilizadas pelas telas (cartão, cabeçalho, campo, botão, tabela).

Assim todas as telas ficam iguais e, para mudar o visual, basta mexer aqui
ou em `ui/tema.py`.
"""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from ui import tema


def cartao(master):
    """Retângulo branco (ou escuro) de cantos arredondados que agrupa conteúdo."""
    return ctk.CTkFrame(
        master,
        fg_color=tema.COR_CARTAO,
        corner_radius=tema.RAIO_CARTAO,
        border_width=1,
        border_color=tema.COR_BORDA,
    )


def cabecalho(master, titulo, subtitulo=""):
    """Título grande da tela, com uma frase explicativa embaixo."""
    quadro = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(
        quadro, text=titulo, font=tema.fonte(26, True),
        text_color=tema.COR_TEXTO, anchor="w",
    ).pack(anchor="w")
    if subtitulo:
        ctk.CTkLabel(
            quadro, text=subtitulo, font=tema.fonte(13),
            text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        ).pack(anchor="w")
    return quadro


def titulo_cartao(master, texto):
    """Título pequeno dentro de um cartão. Devolve o label (o texto pode mudar depois)."""
    rotulo = ctk.CTkLabel(
        master, text=texto, font=tema.fonte(16, True),
        text_color=tema.COR_TEXTO, anchor="w",
    )
    rotulo.pack(fill="x", padx=20, pady=(18, 10))
    return rotulo


def campo_texto(master, rotulo, variavel=None, dica="", estado="normal"):
    """Campo de formulário: rótulo + dica pequena + caixa de texto.

    Devolve (bloco, entrada). O `bloco` deve ser posicionado pela tela
    (pack ou grid); a `entrada` serve para máscaras e foco.
    """
    bloco = ctk.CTkFrame(master, fg_color="transparent")
    linha = ctk.CTkFrame(bloco, fg_color="transparent")
    linha.pack(fill="x")
    ctk.CTkLabel(
        linha, text=rotulo, font=tema.fonte(12, True),
        text_color=tema.COR_TEXTO, anchor="w",
    ).pack(side="left")
    if dica:
        ctk.CTkLabel(
            linha, text=dica, font=tema.fonte(11),
            text_color=tema.COR_TEXTO_SUAVE, anchor="e",
        ).pack(side="right")
    entrada = ctk.CTkEntry(
        bloco, textvariable=variavel, height=38, corner_radius=tema.RAIO_BOTAO,
        border_color=tema.COR_BORDA, fg_color=tema.COR_CARTAO,
        text_color=tema.COR_TEXTO, font=tema.fonte(13), state=estado,
    )
    entrada.pack(fill="x", pady=(4, 0))
    return bloco, entrada


def campo_combobox(master, rotulo, valores=None, variavel=None, comando=None, dica=""):
    """Campo de seleção (ComboBox): rótulo + dica pequena + caixa suspensa."""
    bloco = ctk.CTkFrame(master, fg_color="transparent")
    linha = ctk.CTkFrame(bloco, fg_color="transparent")
    linha.pack(fill="x")
    ctk.CTkLabel(
        linha, text=rotulo, font=tema.fonte(12, True),
        text_color=tema.COR_TEXTO, anchor="w",
    ).pack(side="left")
    if dica:
        ctk.CTkLabel(
            linha, text=dica, font=tema.fonte(11),
            text_color=tema.COR_TEXTO_SUAVE, anchor="e",
        ).pack(side="right")
    combo = ctk.CTkComboBox(
        bloco, values=valores or [""], variable=variavel, command=comando,
        height=38, corner_radius=tema.RAIO_BOTAO, border_color=tema.COR_BORDA,
        fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO,
        button_color=tema.COR_BORDA, font=tema.fonte(13),
        dropdown_font=tema.fonte(13),
    )
    combo.pack(fill="x", pady=(4, 0))
    return bloco, combo



def botao(master, texto, comando=None, estilo="primario", largura=140, altura=38, **extra):
    """Botão do tema. estilo: "primario" (cheio), "secundario" (contorno) ou "perigo" (vermelho)."""
    if estilo == "perigo":
        cores = dict(
            fg_color=tema.COR_PERIGO, hover_color=tema.COR_PERIGO_HOVER,
            text_color=tema.COR_SOBRE_PRIMARIA,
        )
    elif estilo == "secundario":
        cores = dict(
            fg_color="transparent", hover_color=tema.COR_HOVER_SUAVE,
            text_color=tema.COR_TEXTO, border_width=1, border_color=tema.COR_BORDA,
        )
    else:
        cores = dict(
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color=tema.COR_SOBRE_PRIMARIA,
        )
    return ctk.CTkButton(
        master, text=texto, command=comando, width=largura, height=altura,
        corner_radius=tema.RAIO_BOTAO, font=tema.fonte(13, True),
        text_color_disabled=tema.COR_TEXTO_SUAVE, **cores, **extra,
    )


def criar_tabela(master, colunas, altura=8):
    """Tabela com barra de rolagem. `colunas` = [(chave, titulo, largura), ...].

    Devolve (quadro, tabela): o `quadro` é posicionado pela tela; a `tabela`
    (ttk.Treeview) recebe as linhas.
    """
    quadro = ctk.CTkFrame(master, fg_color="transparent")
    tabela = ttk.Treeview(
        quadro,
        columns=[c[0] for c in colunas],
        show="headings",
        selectmode="browse",
        height=altura,
        style="Clinica.Treeview",
    )
    for chave, titulo, largura in colunas:
        tabela.heading(chave, text=titulo, anchor="w")
        tabela.column(chave, width=largura, minwidth=50, anchor="w")
    barra = ctk.CTkScrollbar(quadro, command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y", padx=(4, 0))
    return quadro, tabela


# ====================================================================== busca
def texto_total(total, busca, unidade):
    """Texto de rodapé das listas. Sem resultado na busca: 'Nenhum resultado encontrado.'"""
    if total == 0 and (busca or "").strip():
        return "Nenhum resultado encontrado."
    return f"{total} {unidade} listado(s)."


def barra_busca(master, rotulo, variavel, ao_buscar, largura=280, atraso_ms=200):
    """Campo de busca em tempo real: filtra enquanto o usuário digita e tem botão 'Limpar busca'.

    `ao_buscar` é chamado (sem argumentos) ~0,2 s depois da última tecla, para não pesar
    a tela a cada letra. Devolve (quadro, entrada); o `quadro` é posicionado pela tela.
    """
    quadro = ctk.CTkFrame(master, fg_color="transparent")
    ctk.CTkLabel(
        quadro, text=rotulo, font=tema.fonte(12, True), text_color=tema.COR_TEXTO,
    ).pack(side="left", padx=(0, 10))
    entrada = ctk.CTkEntry(
        quadro, textvariable=variavel, width=largura, height=38,
        corner_radius=tema.RAIO_BOTAO, border_color=tema.COR_BORDA,
        fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO, font=tema.fonte(13),
        placeholder_text="digite para filtrar...",
    )
    entrada.pack(side="left")
    pendente = {"id": None}

    def agendar_busca(*_):
        if pendente["id"] is not None:
            entrada.after_cancel(pendente["id"])
        pendente["id"] = entrada.after(atraso_ms, ao_buscar)

    variavel.trace_add("write", agendar_busca)
    entrada.bind("<Return>", lambda _e: ao_buscar())
    botao(
        quadro, "Limpar busca", lambda: (variavel.set(""), ao_buscar()),
        estilo="secundario", largura=120,
    ).pack(side="left", padx=10)
    return quadro, entrada


def anexar_validacao(bloco, entrada, variavel, validador):
    """Mostra o erro do campo logo abaixo dele (em vermelho), sem esperar o botão Salvar.

    `validador(texto)` devolve a mensagem de erro, ou None se estiver certo. A conferência
    acontece quando o usuário sai do campo e, depois que um erro aparece, a cada tecla.
    Devolve uma função `validar()` que a tela chama antes de salvar (True = campo correto).
    """
    rotulo = ctk.CTkLabel(
        bloco, text="", font=tema.fonte(11), text_color=tema.COR_PERIGO,
        anchor="w", justify="left", wraplength=300,
    )

    def validar(*_):
        mensagem = validador(variavel.get())
        if mensagem:
            rotulo.configure(text=mensagem)
            rotulo.pack(fill="x", pady=(2, 0))
            entrada.configure(border_color=tema.COR_PERIGO)
        else:
            rotulo.pack_forget()
            entrada.configure(border_color=tema.COR_BORDA)
        return mensagem is None

    entrada.bind("<FocusOut>", validar, add="+")
    variavel.trace_add("write", lambda *_: validar() if rotulo.winfo_ismapped() else None)
    return validar


# ============================================================ sugestões (busca)
class CampoComSugestoes(ctk.CTkFrame):
    """Campo de busca com sugestões enquanto o usuário digita (autocompletar).

    * `buscar(texto, limite)` devolve a lista de itens (dicionários) que combinam com o texto;
    * `formatar(item)` devolve o texto mostrado para cada item;
    * `ao_selecionar(item)` é chamado quando o usuário escolhe uma sugestão;
    * `ao_limpar()` é chamado quando ele volta a digitar e a escolha anterior deixa de valer.

    No máximo `limite` sugestões aparecem por vez (padrão 10). Se nada for encontrado, mostra
    "Nenhum resultado encontrado" e, se `acao_sem_resultado` for dada, um botão de atalho
    (ex.: "Cadastrar novo paciente"). O atributo `item` guarda o item escolhido (ou None).
    """

    def __init__(self, master, rotulo, buscar, formatar, ao_selecionar, dica="",
                 limite=10, ao_limpar=None, acao_sem_resultado=None):
        super().__init__(master, fg_color="transparent")
        self._buscar, self._formatar = buscar, formatar
        self._ao_selecionar, self._ao_limpar = ao_selecionar, ao_limpar
        self._limite = limite
        self._acao_sem_resultado = acao_sem_resultado
        self._itens = []
        self._pendente = None
        self._definindo = False  # True enquanto o programa (e não o usuário) muda o texto
        self.item = None

        self.var = ctk.StringVar()
        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(fill="x")
        ctk.CTkLabel(
            linha, text=rotulo, font=tema.fonte(12, True),
            text_color=tema.COR_TEXTO, anchor="w",
        ).pack(side="left")
        if dica:
            ctk.CTkLabel(
                linha, text=dica, font=tema.fonte(11),
                text_color=tema.COR_TEXTO_SUAVE, anchor="e",
            ).pack(side="right")

        self.entrada = ctk.CTkEntry(
            self, textvariable=self.var, height=38, corner_radius=tema.RAIO_BOTAO,
            border_color=tema.COR_BORDA, fg_color=tema.COR_CARTAO,
            text_color=tema.COR_TEXTO, font=tema.fonte(13),
            placeholder_text="digite para buscar...",
        )
        self.entrada.pack(fill="x", pady=(4, 0))

        # Área das sugestões: só aparece quando há o que mostrar.
        self.area = ctk.CTkFrame(
            self, fg_color=tema.COR_CARTAO, border_width=1, border_color=tema.COR_BORDA,
            corner_radius=tema.RAIO_BOTAO,
        )
        self.lista = tk.Listbox(
            self.area, height=5, activestyle="none", exportselection=False,
            relief="flat", borderwidth=0, highlightthickness=0,
            font=(tema.FAMILIA_FONTE, 11),
            background=tema.cor(tema.COR_CARTAO), foreground=tema.cor(tema.COR_TEXTO),
            selectbackground=tema.cor(tema.COR_PRIMARIA), selectforeground=tema.COR_SOBRE_PRIMARIA,
        )
        self.barra = ctk.CTkScrollbar(self.area, command=self.lista.yview)
        self.lista.configure(yscrollcommand=self.barra.set)
        self.mensagem = ctk.CTkLabel(
            self.area, text="Nenhum resultado encontrado.", font=tema.fonte(12),
            text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self.botao_atalho = None
        if acao_sem_resultado:
            self.botao_atalho = botao(
                self.area, acao_sem_resultado[0], acao_sem_resultado[1],
                estilo="secundario", largura=200, altura=32,
            )

        self.var.trace_add("write", self._ao_digitar)
        self.entrada.bind("<FocusIn>", lambda _e: self._agendar())
        self.entrada.bind("<Down>", self._ir_para_lista)
        self.entrada.bind("<Escape>", lambda _e: self._esconder())
        self.lista.bind("<ButtonRelease-1>", self._escolher_clique)
        self.lista.bind("<Return>", self._escolher_clique)

    # ----------------------------------------------------------- uso externo
    def definir(self, item):
        """Escolhe um item pelo código (ex.: ao abrir uma consulta para editar)."""
        self._definindo = True
        self.item = item
        self.var.set(self._formatar(item) if item else "")
        self._definindo = False
        self._esconder()

    def limpar(self):
        self.definir(None)

    def esconder(self):
        self._esconder()

    # ------------------------------------------------------------- internos
    def _ao_digitar(self, *_):
        if self._definindo:
            return
        if self.item is not None:  # digitou de novo: a escolha anterior deixa de valer
            self.item = None
            if self._ao_limpar:
                self._ao_limpar()
        self._agendar()

    def _agendar(self):
        if self._pendente is not None:
            self.after_cancel(self._pendente)
        self._pendente = self.after(200, self._atualizar_sugestoes)

    def _atualizar_sugestoes(self):
        self._pendente = None
        if self.item is not None:
            return
        try:
            self._itens = list(self._buscar(self.var.get().strip(), self._limite))[: self._limite]
        except Exception:  # erro de banco etc.: não deixa a tela quebrar
            self._itens = []
        for filho in (self.lista, self.barra, self.mensagem, self.botao_atalho):
            if filho is not None:
                filho.pack_forget()
        self.lista.delete(0, "end")
        if self._itens:
            for item in self._itens:
                self.lista.insert("end", self._formatar(item))
            self.lista.configure(height=min(len(self._itens), 5))
            self.lista.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
            if len(self._itens) > 5:
                self.barra.pack(side="right", fill="y", padx=2, pady=4)
        else:
            self.mensagem.pack(fill="x", padx=12, pady=(8, 4))
            if self.botao_atalho is not None:
                self.botao_atalho.pack(anchor="w", padx=10, pady=(0, 8))
        self.area.pack(fill="x", pady=(2, 0))

    def _esconder(self):
        if self._pendente is not None:
            self.after_cancel(self._pendente)
            self._pendente = None
        self.area.pack_forget()

    def _ir_para_lista(self, _evento):
        if self._itens:
            self.lista.focus_set()
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(0)
            self.lista.activate(0)
        return "break"

    def _escolher_clique(self, _evento):
        selecionado = self.lista.curselection()
        if not selecionado:
            return
        self._escolher(self._itens[selecionado[0]])

    def _escolher(self, item):
        self.definir(item)
        if self._ao_selecionar:
            self._ao_selecionar(item)


# =========================================================== grade de horários
class GradeHorarios(ctk.CTkFrame):
    """Mostra os horários do médico com os três estados (disponível, reservado, indisponível).

    Os dados vêm de `services.agenda.horarios_do_dia`. `ao_clicar(horario)` recebe o
    dicionário do horário clicado (qualquer estado); cada tela decide o que fazer.
    """
    COLUNAS = 6

    def __init__(self, master, ao_clicar=None):
        super().__init__(master, fg_color="transparent")
        self._ao_clicar = ao_clicar
        self._botoes = {}
        self._selecionado = None

        legenda = ctk.CTkFrame(self, fg_color="transparent")
        legenda.pack(fill="x", pady=(0, 8))
        for texto, cor in (
            ("Disponível", tema.COR_SLOT_DISPONIVEL),
            ("Reservado", tema.COR_SLOT_RESERVADO),
            ("Indisponível", tema.COR_SLOT_INDISPONIVEL),
        ):
            ctk.CTkLabel(legenda, text="", width=14, height=14, corner_radius=4, fg_color=cor
                         ).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(legenda, text=texto, font=tema.fonte(11),
                         text_color=tema.COR_TEXTO_SUAVE).pack(side="left", padx=(0, 16))

        self.grade = ctk.CTkFrame(self, fg_color="transparent")
        self.grade.pack(fill="x")
        self.aviso = ctk.CTkLabel(
            self, text="", font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )

    def mostrar(self, horarios, selecionado=None):
        """Redesenha os horários. `selecionado` = hora de início a destacar."""
        for botao_antigo in self._botoes.values():
            botao_antigo.destroy()
        self._botoes = {}
        self._selecionado = selecionado
        self.aviso.pack_forget()
        for posicao, h in enumerate(horarios):
            estado = h["estado"]
            if estado == "disponivel":
                cores = dict(fg_color=tema.COR_SLOT_DISPONIVEL, hover_color=tema.COR_PRIMARIA_HOVER,
                             text_color=tema.COR_SOBRE_PRIMARIA)
            elif estado == "reservado":
                cores = dict(fg_color=tema.COR_SLOT_RESERVADO, hover_color=tema.COR_SLOT_RESERVADO,
                             text_color=tema.COR_SOBRE_PRIMARIA)
            else:
                cores = dict(fg_color=tema.COR_SLOT_INDISPONIVEL,
                             hover_color=tema.COR_SLOT_INDISPONIVEL,
                             text_color=tema.COR_SLOT_INDISPONIVEL_TEXTO)
            marcado = h["hora_inicio"] == selecionado
            b = ctk.CTkButton(
                self.grade, text=h["hora_inicio"], width=78, height=32,
                corner_radius=tema.RAIO_BOTAO, font=tema.fonte(12, True),
                border_width=3 if marcado else 0, border_color=tema.COR_TEXTO,
                command=lambda item=h: self._clicou(item), **cores,
            )
            b.grid(row=posicao // self.COLUNAS, column=posicao % self.COLUNAS, padx=3, pady=3)
            self._botoes[h["hora_inicio"]] = b

    def limpar(self, mensagem=""):
        """Apaga os horários e, se vier `mensagem`, mostra um aviso no lugar."""
        self.mostrar([])
        if mensagem:
            self.aviso.configure(text=mensagem)
            self.aviso.pack(fill="x", pady=(4, 0))

    def _clicou(self, item):
        if self._ao_clicar:
            self._ao_clicar(item)
