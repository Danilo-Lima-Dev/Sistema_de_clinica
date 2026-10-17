"""Tema visual do sistema: nome do programa, cores, fontes e tamanhos.

PARA PERSONALIZAR A APARÊNCIA, MUDE SOMENTE ESTE ARQUIVO.

Todas as cores são pares (modo claro, modo escuro): o CustomTkinter escolhe
sozinho o lado certo quando o usuário alterna entre claro e escuro.
"""
import customtkinter as ctk
from tkinter import ttk

# ------------------------------------------------------------------ textos
NOME_PROGRAMA = "Sistema de Clínica"          # título da janela, menu e login
SLOGAN = "Gestão de pacientes e consultas"    # frase abaixo do nome

# ------------------------------------------------------------------- modo
MODO_INICIAL = "light"  # "light" (claro), "dark" (escuro) ou "system" (do Windows/macOS)

# ------------------------------------------------------------------ fontes
FAMILIA_FONTE = "Segoe UI"  # se não existir no computador, o Tk usa outra parecida

# ------------------------------------------------------------------ cores
COR_PRIMARIA = ("#0f766e", "#14b8a6")          # botões e destaques (verde-água)
COR_PRIMARIA_HOVER = ("#115e59", "#2dd4bf")    # cor do botão ao passar o mouse
COR_SOBRE_PRIMARIA = "#ffffff"                 # texto escrito sobre a cor primária

COR_FUNDO = ("#f1f5f9", "#0b1220")             # fundo geral da janela
COR_CARTAO = ("#ffffff", "#162032")            # fundo dos cartões
COR_BORDA = ("#e2e8f0", "#26344d")             # borda dos cartões e campos
COR_HOVER_SUAVE = ("#f1f5f9", "#1f2d45")       # hover de botões "secundários"

COR_TEXTO = ("#0f172a", "#e2e8f0")             # texto principal
COR_TEXTO_SUAVE = ("#64748b", "#94a3b8")       # dicas e textos secundários

COR_PERIGO = ("#dc2626", "#ef4444")            # excluir / mensagens de erro
COR_PERIGO_HOVER = ("#b91c1c", "#dc2626")

COR_AVISO_FUNDO = ("#fef3c7", "#3b2a0a")       # faixa de aviso (protótipos)
COR_AVISO_TEXTO = ("#92400e", "#fcd34d")

# Menu lateral (cartões de navegação)
COR_MENU = ("#0f766e", "#0d1a2b")              # fundo do menu lateral
COR_MENU_TEXTO = ("#ecfeff", "#cbd5e1")        # texto dos cartões inativos
COR_MENU_HOVER = ("#14857b", "#1b2b45")        # cartão inativo com o mouse em cima
COR_MENU_ATIVO = ("#ffffff", "#14b8a6")        # cartão da tela atual
COR_MENU_ATIVO_TEXTO = ("#0f766e", "#052e2b")  # texto do cartão da tela atual

# ---------------------------------------------------------------- formas
RAIO_CARTAO = 14   # arredondamento dos cartões
RAIO_BOTAO = 10    # arredondamento de botões e campos
LARGURA_MENU = 250


# ------------------------------------------------------------------ funções
def fonte(tamanho=13, negrito=False):
    """Cria uma fonte do tema. Só pode ser chamada depois de existir uma janela."""
    return ctk.CTkFont(
        family=FAMILIA_FONTE, size=tamanho, weight="bold" if negrito else "normal"
    )


def aplicar_tema():
    """Liga o modo (claro/escuro). Chame uma vez, antes de criar a janela."""
    ctk.set_appearance_mode(MODO_INICIAL)
    ctk.set_default_color_theme("blue")


def modo_escuro():
    """True se o sistema está no modo escuro agora."""
    return ctk.get_appearance_mode() == "Dark"


def alternar_modo():
    """Troca entre claro e escuro e reestiliza as tabelas."""
    ctk.set_appearance_mode("light" if modo_escuro() else "dark")
    estilizar_tabela()


def _cor(par):
    """Escolhe, de um par (claro, escuro), a cor do modo atual (para widgets ttk)."""
    return par[1] if modo_escuro() else par[0]


def estilizar_tabela():
    """Pinta as tabelas (ttk.Treeview) com as cores do tema.

    O CustomTkinter não estiliza o Treeview sozinho, então fazemos aqui.
    As tabelas usam o estilo chamado "Clinica.Treeview".
    """
    estilo = ttk.Style()
    estilo.theme_use("clam")  # tema base que aceita cores personalizadas
    estilo.configure(
        "Clinica.Treeview",
        background=_cor(COR_CARTAO),
        fieldbackground=_cor(COR_CARTAO),
        foreground=_cor(COR_TEXTO),
        rowheight=32,
        borderwidth=1,
        bordercolor=_cor(COR_BORDA),  # contorno da tabela (sem isso fica branco no escuro)
        lightcolor=_cor(COR_BORDA),
        darkcolor=_cor(COR_BORDA),
        font=(FAMILIA_FONTE, 11),
    )
    estilo.configure(
        "Clinica.Treeview.Heading",
        background=_cor(COR_FUNDO),
        foreground=_cor(COR_TEXTO_SUAVE),
        relief="flat",
        borderwidth=0,
        padding=(8, 8),
        font=(FAMILIA_FONTE, 11, "bold"),
    )
    estilo.map(
        "Clinica.Treeview",
        background=[("selected", _cor(COR_PRIMARIA))],
        foreground=[("selected", COR_SOBRE_PRIMARIA)],
    )
    estilo.map(
        "Clinica.Treeview.Heading",
        background=[("active", _cor(COR_BORDA))],
    )
