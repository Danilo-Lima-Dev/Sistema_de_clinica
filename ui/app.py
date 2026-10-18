"""Janela principal do sistema (CustomTkinter).

Existe uma única janela. Ela mostra primeiro a tela de login e, depois do
login, troca o conteúdo pelo sistema: menu lateral com "cartões" à esquerda e
a tela escolhida à direita.
"""
import tkinter as tk

import customtkinter as ctk

from ui import tema
from ui.tela_consultas import TelaConsultas
from ui.tela_login import TelaLogin
from ui.tela_pacientes import TelaPacientes
from ui.tela_profissionais import TelaProfissionais


class App(ctk.CTk):
    # Telas do sistema, na ordem em que aparecem no menu.
    # Cada tela tem o atributo NOME_MENU com o texto do cartão.
    TELAS = (TelaPacientes, TelaProfissionais, TelaConsultas)


    def __init__(self):
        tema.aplicar_tema()
        super().__init__(fg_color=tema.COR_FUNDO)
        tema.estilizar_tabela()
        self.title(tema.NOME_PROGRAMA)

        self.usuario = None
        self.container = None
        self.telas = {}          # classe da tela -> tela já criada
        self.cartoes = {}        # classe da tela -> botão (cartão) do menu
        self._mostrar_login()

    # ----------------------------------------------------- troca de telas
    def _novo_container(self):
        """Apaga o que está na janela e devolve um quadro limpo para montar a próxima tela."""
        if self.container is not None:
            self.container.destroy()
        self.container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.container.pack(fill="both", expand=True)
        return self.container

    def _tamanho_seguro(self, largura, altura):
        """Reduz o tamanho desejado se a tela for pequena, para a janela caber inteira."""
        escala = self._get_window_scaling()  # ajuste de DPI do CustomTkinter (ex.: 1.25)
        largura = min(largura, int(self.winfo_screenwidth() / escala) - 60)
        altura = min(altura, int(self.winfo_screenheight() / escala) - 110)
        return largura, altura

    def _centralizar(self):
        """Põe a janela no meio da tela, usando o tamanho que ela realmente tem."""
        self.update()  # aplica o tamanho novo antes de medir a janela
        x = max(0, (self.winfo_screenwidth() - self.winfo_width()) // 2)
        y = max(0, (self.winfo_screenheight() - self.winfo_height()) // 2 - 20)
        # tk.Tk.geometry (sem o ajuste de escala do CustomTkinter): só a posição.
        tk.Tk.geometry(self, f"+{x}+{y}")

    # ------------------------------------------------------------- login
    def _mostrar_login(self):
        self.usuario = None
        self.telas, self.cartoes = {}, {}
        container = self._novo_container()
        largura, altura = self._tamanho_seguro(480, 620)
        self.resizable(False, False)
        self.minsize(largura, altura)
        self.geometry(f"{largura}x{altura}")
        TelaLogin(container, self._entrar, self.destroy).pack(fill="both", expand=True)
        self._centralizar()

    def _entrar(self, usuario):
        """Chamada pelo login quando usuário e senha estão corretos."""
        self.usuario = usuario
        self._montar_sistema()

    def _sair(self):
        """Volta para o login (o programa continua aberto)."""
        # Espera a animação do botão "Sair" terminar antes de destruir a tela.
        self.after(150, self._mostrar_login)

    # ----------------------------------------------------------- sistema
    def _montar_sistema(self):
        container = self._novo_container()
        largura, altura = self._tamanho_seguro(1180, 760)
        self.resizable(True, True)
        self.minsize(min(1000, largura), min(680, altura))
        self.geometry(f"{largura}x{altura}")
        container.grid_columnconfigure(1, weight=1)  # a área de conteúdo estica
        container.grid_rowconfigure(0, weight=1)

        self._montar_menu(container)

        # Área de conteúdo: todas as telas ficam aqui, só uma visível por vez.
        conteudo = ctk.CTkFrame(container, fg_color=tema.COR_FUNDO, corner_radius=0)
        conteudo.grid(row=0, column=1, sticky="nsew")
        conteudo.grid_columnconfigure(0, weight=1)
        conteudo.grid_rowconfigure(0, weight=1)

        self.telas = {}
        for classe in self.TELAS:
            self.telas[classe] = classe(conteudo)
        self._mostrar_tela(self.TELAS[0])
        self._centralizar()

    def _montar_menu(self, container):
        """Menu lateral: marca do programa, cartões de navegação e rodapé do usuário."""
        menu = ctk.CTkFrame(
            container, width=tema.LARGURA_MENU, corner_radius=0, fg_color=tema.COR_MENU
        )
        menu.grid(row=0, column=0, sticky="nsew")
        menu.pack_propagate(False)  # mantém a largura fixa

        # --- rodapé (empacotado primeiro para ficar sempre embaixo)
        rodape = ctk.CTkFrame(menu, fg_color="transparent")
        rodape.pack(side="bottom", fill="x", padx=14, pady=(0, 16))
        ctk.CTkLabel(
            rodape, text=self.usuario["nome"], font=tema.fonte(14, True),
            text_color=tema.COR_MENU_TEXTO, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            rodape, text=f"@{self.usuario['login']}", font=tema.fonte(11),
            text_color=tema.COR_MENU_TEXTO, anchor="w",
        ).pack(fill="x", pady=(0, 10))
        chave = ctk.CTkSwitch(
            rodape, text="Modo escuro", command=tema.alternar_modo,
            font=tema.fonte(12), text_color=tema.COR_MENU_TEXTO,
            progress_color=tema.COR_MENU_ATIVO,
        )
        chave.pack(anchor="w", pady=(0, 12))
        if tema.modo_escuro():
            chave.select()
        ctk.CTkButton(
            rodape, text="Sair", command=self._sair, height=38,
            corner_radius=tema.RAIO_BOTAO, font=tema.fonte(13, True),
            fg_color="transparent", border_width=1,
            border_color=tema.COR_MENU_TEXTO, text_color=tema.COR_MENU_TEXTO,
            hover_color=tema.COR_MENU_HOVER,
        ).pack(fill="x")

        # --- marca do programa (círculo com cruz + nome)
        marca = ctk.CTkFrame(menu, fg_color="transparent")
        marca.pack(fill="x", padx=18, pady=(26, 22))
        logo = ctk.CTkFrame(
            marca, width=40, height=40, corner_radius=20, fg_color=tema.COR_MENU_ATIVO
        )
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(
            logo, text="+", font=tema.fonte(24, True),
            text_color=tema.COR_MENU_ATIVO_TEXTO,
        ).place(relx=0.5, rely=0.46, anchor="center")
        ctk.CTkLabel(
            marca, text=tema.NOME_PROGRAMA, font=tema.fonte(16, True),
            text_color=tema.COR_MENU_TEXTO, wraplength=150, justify="left",
        ).pack(side="left", padx=(12, 0))

        # --- cartões de navegação (um por tela)
        ctk.CTkLabel(
            menu, text="MENU", font=tema.fonte(11, True),
            text_color=tema.COR_MENU_TEXTO, anchor="w",
        ).pack(fill="x", padx=22, pady=(0, 6))
        for classe in self.TELAS:
            cartao = ctk.CTkButton(
                menu, text=classe.NOME_MENU, anchor="w", height=52,
                corner_radius=tema.RAIO_CARTAO, font=tema.fonte(14, True),
                command=lambda c=classe: self._mostrar_tela(c),
            )
            cartao.pack(fill="x", padx=14, pady=4)
            self.cartoes[classe] = cartao

    def _mostrar_tela(self, classe_escolhida):
        """Mostra a tela escolhida e destaca o cartão dela no menu."""
        for classe, tela in self.telas.items():
            if classe is classe_escolhida:
                tela.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)
                if hasattr(tela, "recarregar_especialidades"):
                    tela.recarregar_especialidades()
                if hasattr(tela, "recarregar_opcoes"):
                    tela.recarregar_opcoes()
                if hasattr(tela, "atualizar_lista"):
                    tela.atualizar_lista()
            else:
                tela.grid_remove()

        for classe, cartao in self.cartoes.items():
            if classe is classe_escolhida:  # cartão da tela atual: destacado
                cartao.configure(
                    fg_color=tema.COR_MENU_ATIVO, hover_color=tema.COR_MENU_ATIVO,
                    text_color=tema.COR_MENU_ATIVO_TEXTO,
                )
            else:  # os outros: transparentes, acendem com o mouse
                cartao.configure(
                    fg_color="transparent", hover_color=tema.COR_MENU_HOVER,
                    text_color=tema.COR_MENU_TEXTO,
                )
