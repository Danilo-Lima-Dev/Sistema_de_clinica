"""Tela de login (CustomTkinter).

Não é uma janela separada: é um quadro que a janela principal (`ui/app.py`)
mostra primeiro. Quando o login dá certo, o quadro avisa a janela principal
chamando a função `ao_entrar(usuario)`.
"""
import customtkinter as ctk

from services import autenticacao
from services.validacoes import ErroValidacao
from ui import componentes, tema

MAX_TENTATIVAS = 5  # depois disso, o programa fecha


class TelaLogin(ctk.CTkFrame):
    def __init__(self, master, ao_entrar, ao_cancelar):
        """
        ao_entrar(usuario)  -> chamada quando usuário e senha estão corretos.
        ao_cancelar()       -> chamada quando erra a senha MAX_TENTATIVAS vezes.
        """
        super().__init__(master, fg_color="transparent")
        self._ao_entrar = ao_entrar
        self._ao_cancelar = ao_cancelar
        self.tentativas = 0

        self.var_login = ctk.StringVar()
        self.var_senha = ctk.StringVar()
        self.var_mostrar = ctk.BooleanVar(value=False)
        self.var_erro = ctk.StringVar()

        self._montar_layout()
        # Dá um instante para a janela aparecer e só então põe o cursor no usuário.
        self.after(250, self.entrada_login.focus_set)

    def _montar_layout(self):
        # Cartão centralizado na janela.
        quadro = componentes.cartao(self)
        quadro.place(relx=0.5, rely=0.5, anchor="center")

        # "Logotipo": um círculo com uma cruz, desenhado só com texto e cor.
        logo = ctk.CTkFrame(
            quadro, width=64, height=64, corner_radius=32, fg_color=tema.COR_PRIMARIA
        )
        logo.pack(pady=(32, 14), padx=40)
        logo.pack_propagate(False)
        ctk.CTkLabel(
            logo, text="+", font=tema.fonte(34, True), text_color=tema.COR_SOBRE_PRIMARIA
        ).place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(
            quadro, text=tema.NOME_PROGRAMA, font=tema.fonte(22, True),
            text_color=tema.COR_TEXTO,
        ).pack()
        ctk.CTkLabel(
            quadro, text=tema.SLOGAN, font=tema.fonte(12),
            text_color=tema.COR_TEXTO_SUAVE,
        ).pack(pady=(0, 22))

        bloco, self.entrada_login = componentes.campo_texto(
            quadro, "Usuário", self.var_login
        )
        bloco.pack(fill="x", padx=36, pady=(0, 12))

        bloco, self.entrada_senha = componentes.campo_texto(
            quadro, "Senha", self.var_senha
        )
        bloco.pack(fill="x", padx=36)
        self.entrada_senha.configure(show="•")  # esconde o que é digitado

        ctk.CTkCheckBox(
            quadro, text="Mostrar senha", variable=self.var_mostrar,
            command=self._alternar_senha, font=tema.fonte(12),
            text_color=tema.COR_TEXTO_SUAVE, fg_color=tema.COR_PRIMARIA,
            hover_color=tema.COR_PRIMARIA_HOVER, border_color=tema.COR_BORDA,
            checkbox_width=18, checkbox_height=18, corner_radius=5,
        ).pack(anchor="w", padx=36, pady=(10, 4))

        # Mensagem de erro: vazia até que algo dê errado.
        ctk.CTkLabel(
            quadro, textvariable=self.var_erro, font=tema.fonte(12),
            text_color=tema.COR_PERIGO, wraplength=300, height=22,
        ).pack(padx=36, pady=(0, 6))

        componentes.botao(
            quadro, "Entrar", self._entrar, largura=300, altura=44
        ).pack(padx=36, pady=(0, 34))

        # Enter nos campos também tenta entrar.
        self.entrada_login.bind("<Return>", lambda _e: self._entrar())
        self.entrada_senha.bind("<Return>", lambda _e: self._entrar())

    # ------------------------------------------------------------ ações
    def _alternar_senha(self):
        """Mostra ou esconde a senha conforme a caixinha marcada."""
        self.entrada_senha.configure(show="" if self.var_mostrar.get() else "•")

    def _entrar(self):
        """Confere login e senha e avisa a janela principal se estiver certo."""
        try:
            usuario = autenticacao.autenticar(
                self.var_login.get(), self.var_senha.get()
            )
        except ErroValidacao as erro:
            self.tentativas += 1
            if self.tentativas >= MAX_TENTATIVAS:
                self._ao_cancelar()
                return
            self.var_erro.set(str(erro))
            self.var_senha.set("")  # limpa só a senha
            self.entrada_senha.focus_set()
            return
        # Espera a animação do botão terminar antes de trocar de tela,
        # senão o Tk reclama de um botão que já foi destruído.
        self.winfo_toplevel().after(150, lambda: self._ao_entrar(usuario))
