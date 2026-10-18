"""Peças visuais reutilizadas pelas telas (cartão, cabeçalho, campo, botão, tabela).

Assim todas as telas ficam iguais e, para mudar o visual, basta mexer aqui
ou em `ui/tema.py`.
"""
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
        tabela.column(chave, width=largura, anchor="w")
    barra = ctk.CTkScrollbar(quadro, command=tabela.yview)
    tabela.configure(yscrollcommand=barra.set)
    tabela.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y", padx=(4, 0))
    return quadro, tabela
