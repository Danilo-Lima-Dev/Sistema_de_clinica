"""Janelinhas (diálogos) usadas pela tela de consultas.

  * DialogoNovoPaciente - cadastro rápido de paciente sem sair do agendamento;
  * DialogoAtestado     - pede os campos manuais do atestado (dias, CID e local).

  * DialogoReceituario  - pede a prescrição (texto livre) e o local de emissão;

Cada diálogo guarda o que o usuário informou em `self.resultado` (None se cancelou).
Uso:  dlg = DialogoXxx(janela); janela.wait_window(dlg); dlg.resultado
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import atestado, pacientes, receituario
from services.validacoes import (
    MSG_EMAIL,
    ErroValidacao,
    email_valido,
    mascara_data,
    mascara_telefone,
    motivo_telefone_invalido,
    somente_digitos,
)
from ui import componentes, tema


def _aplicar_mascara(variavel, funcao, entrada):
    def ao_alterar(*_):
        novo = funcao(variavel.get())
        if novo != variavel.get():
            variavel.set(novo)
        entrada.after_idle(lambda: entrada.icursor("end"))

    variavel.trace_add("write", ao_alterar)


class _Dialogo(ctk.CTkToplevel):
    """Base: janela modal, centralizada sobre a janela principal."""

    def __init__(self, janela, titulo, largura, altura):
        super().__init__(janela, fg_color=tema.COR_FUNDO)
        self.resultado = None
        self.title(titulo)
        self.resizable(False, False)
        x = janela.winfo_rootx() + max(0, (janela.winfo_width() - largura) // 2)
        y = janela.winfo_rooty() + max(0, (janela.winfo_height() - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        self.transient(janela)
        self.bind("<Escape>", lambda _e: self.destroy())
        # Em alguns sistemas a janela precisa existir na tela antes de "prender" o foco.
        self.after(150, self._prender_foco)

    def _prender_foco(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:  # janela já fechada
            pass

    def _linha_botoes(self, texto_ok, comando_ok):
        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(6, 20))
        componentes.botao(botoes, texto_ok, comando_ok, largura=170).pack(side="left")
        componentes.botao(
            botoes, "Cancelar", self.destroy, estilo="secundario", largura=110
        ).pack(side="left", padx=10)


class DialogoNovoPaciente(_Dialogo):
    """Cadastro rápido de paciente. `resultado` = id do paciente criado."""

    def __init__(self, janela, nome_sugerido=""):
        super().__init__(janela, "Novo paciente", 460, 600)
        self.var_nome = ctk.StringVar(value=nome_sugerido)
        self.var_cpf = ctk.StringVar()
        self.var_nasc = ctk.StringVar()
        self.var_tel = ctk.StringVar()
        self.var_email = ctk.StringVar()

        componentes.cabecalho(
            self, "Novo paciente", "Cadastre sem sair do agendamento."
        ).pack(anchor="w", padx=24, pady=(20, 10))

        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="x", padx=24)
        campos = (
            ("Nome *", "", self.var_nome),
            ("CPF *", "só números", self.var_cpf),
            ("Nascimento *", "DD/MM/AAAA", self.var_nasc),
            ("Telefone", "(86) 99999-9999", self.var_tel),
            ("E-mail", "", self.var_email),
        )
        entradas = {}
        for rotulo, dica, variavel in campos:
            bloco, entrada = componentes.campo_texto(quadro, rotulo, variavel, dica)
            bloco.pack(fill="x", pady=(0, 10))
            entradas[rotulo] = (bloco, entrada)
        _aplicar_mascara(self.var_cpf, lambda t: somente_digitos(t)[:11], entradas["CPF *"][1])
        _aplicar_mascara(self.var_nasc, mascara_data, entradas["Nascimento *"][1])
        _aplicar_mascara(self.var_tel, mascara_telefone, entradas["Telefone"][1])
        self.validar_telefone = componentes.anexar_validacao(
            *entradas["Telefone"], self.var_tel,
            lambda t: motivo_telefone_invalido(t) if somente_digitos(t) else None,
        )
        self.validar_email = componentes.anexar_validacao(
            *entradas["E-mail"], self.var_email,
            lambda t: None if not t.strip() or email_valido(t) else MSG_EMAIL,
        )
        self._linha_botoes("Cadastrar paciente", self._salvar)
        entradas["Nome *"][1].focus_set() if not nome_sugerido else entradas["CPF *"][1].focus_set()

    def _salvar(self):
        if not (self.validar_telefone() and self.validar_email()):
            return
        try:
            self.resultado = pacientes.cadastrar(
                self.var_nome.get(), self.var_cpf.get(), self.var_nasc.get(),
                self.var_tel.get(), self.var_email.get(),
            )
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro), parent=self)
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível salvar: {erro}", parent=self)
            return
        self.destroy()


class DialogoAtestado(_Dialogo):
    """Campos manuais do atestado. `resultado` = (dias, cid, local)."""

    def __init__(self, janela):
        super().__init__(janela, "Atestado médico", 440, 410)
        self.var_dias = ctk.StringVar()
        self.var_cid = ctk.StringVar()
        self.var_local = ctk.StringVar(value=tema.LOCAL_EMISSAO)

        componentes.cabecalho(
            self, "Atestado médico",
            "Paciente e médico são preenchidos automaticamente.",
        ).pack(anchor="w", padx=24, pady=(20, 10))

        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="x", padx=24)
        bloco, entrada_dias = componentes.campo_texto(
            quadro, "Quantidade de dias *", self.var_dias, "1 a 365"
        )
        bloco.pack(fill="x", pady=(0, 10))
        _aplicar_mascara(self.var_dias, lambda t: somente_digitos(t)[:3], entrada_dias)
        bloco, entrada_cid = componentes.campo_texto(
            quadro, "CID", self.var_cid, "opcional — ex.: J11 ou J11.1"
        )
        bloco.pack(fill="x", pady=(0, 10))
        _aplicar_mascara(self.var_cid, lambda t: t.upper()[:6], entrada_cid)
        bloco, _entrada_local = componentes.campo_texto(
            quadro, "Local de emissão", self.var_local, "cidade - UF"
        )
        bloco.pack(fill="x", pady=(0, 10))
        self._linha_botoes("Gerar atestado", self._confirmar)
        entrada_dias.focus_set()

    def _confirmar(self):
        try:
            dias = atestado.validar_dias(self.var_dias.get())
            cid = atestado.validar_cid(self.var_cid.get())
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro), parent=self)
            return
        self.resultado = (dias, cid, self.var_local.get().strip())
        self.destroy()


class DialogoReceituario(_Dialogo):
    """Prescrição do receituário. `resultado` = (prescricao, local)."""

    def __init__(self, janela, paciente="", medico=""):
        super().__init__(janela, "Receituário médico", 520, 560)
        self.var_local = ctk.StringVar(value=tema.LOCAL_EMISSAO)

        componentes.cabecalho(
            self, "Receituário médico",
            f"Paciente: {paciente}\nMédico: {medico}" if paciente else
            "Paciente e médico são preenchidos automaticamente.",
        ).pack(anchor="w", padx=24, pady=(20, 10))

        ctk.CTkLabel(
            self, text="Prescrição *", font=tema.fonte(12, True),
            text_color=tema.COR_TEXTO, anchor="w",
        ).pack(fill="x", padx=24)
        self.texto = ctk.CTkTextbox(
            self, height=220, corner_radius=tema.RAIO_BOTAO, border_width=1,
            border_color=tema.COR_BORDA, fg_color=tema.COR_CARTAO,
            text_color=tema.COR_TEXTO, font=tema.fonte(13),
        )
        self.texto.pack(fill="x", padx=24, pady=(4, 2))
        ctk.CTkLabel(
            self, text="Ex.: 1) Dipirona 500 mg - 1 comprimido a cada 6 horas por 3 dias",
            font=tema.fonte(11), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 10))

        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="x", padx=24)
        bloco, _entrada = componentes.campo_texto(
            quadro, "Local de emissão", self.var_local, "cidade - UF"
        )
        bloco.pack(fill="x", pady=(0, 10))
        self._linha_botoes("Gerar receituário", self._confirmar)
        self.texto.focus_set()

    def _confirmar(self):
        try:
            prescricao = receituario.validar_prescricao(self.texto.get("1.0", "end"))
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro), parent=self)
            return
        self.resultado = (prescricao, self.var_local.get().strip())
        self.destroy()
