"""Tela da agenda do médico: mostra os horários do dia com três estados.

  * Disponível   (verde)   - pode ser agendado; clicando, dá para bloqueá-lo (folga, reunião...);
  * Reservado    (laranja) - já tem consulta; clicando, mostra qual;
  * Indisponível (cinza)   - fora do expediente ou bloqueado; se foi bloqueado, dá para liberar.

O expediente (horário e dias de atendimento) fica em `services/agenda.py`.
"""
import sqlite3
from datetime import date, timedelta
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from services import agenda, consultas, profissionais
from services.validacoes import (
    ErroValidacao,
    data_br_para_date,
    date_para_br,
    mascara_data,
)
from ui import componentes

DIAS_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


class TelaAgenda(ctk.CTkFrame):
    NOME_MENU = "Agenda"

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.profissional = None  # dicionário do médico escolhido
        self.var_data = ctk.StringVar(value=date_para_br(date.today()))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Agenda do médico",
            "Veja os horários disponíveis, reservados e indisponíveis de cada médico.",
        ).grid(row=0, column=0, sticky="w", pady=(0, 16))

        self._montar_filtros()
        self._montar_grade()

    # ------------------------------------------------------------ layout
    def _montar_filtros(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        grade = ctk.CTkFrame(cartao, fg_color="transparent")
        grade.pack(fill="x", padx=20, pady=18)
        grade.grid_columnconfigure(0, weight=3)
        grade.grid_columnconfigure(1, weight=2)

        self.campo_medico = componentes.CampoComSugestoes(
            grade, "Médico *", self._buscar_medicos, self._texto_medico,
            self._ao_escolher_medico, dica="busque por nome ou especialidade",
            ao_limpar=self._ao_limpar_medico,
        )
        self.campo_medico.grid(row=0, column=0, sticky="new", padx=(0, 12))

        lado = ctk.CTkFrame(grade, fg_color="transparent")
        lado.grid(row=0, column=1, sticky="new")
        bloco, self.entrada_data = componentes.campo_texto(
            lado, "Data", self.var_data, dica="DD/MM/AAAA"
        )
        bloco.pack(fill="x")
        self._ligar_mascara_data()

        navegacao = ctk.CTkFrame(lado, fg_color="transparent")
        navegacao.pack(fill="x", pady=(8, 0))
        componentes.botao(
            navegacao, "◀", lambda: self._mudar_dia(-1), estilo="secundario", largura=44
        ).pack(side="left")
        componentes.botao(
            navegacao, "Hoje", self._hoje, estilo="secundario", largura=70
        ).pack(side="left", padx=6)
        componentes.botao(
            navegacao, "▶", lambda: self._mudar_dia(1), estilo="secundario", largura=44
        ).pack(side="left")

    def _ligar_mascara_data(self):
        def ao_alterar(*_):
            novo = mascara_data(self.var_data.get())
            if novo != self.var_data.get():
                self.var_data.set(novo)
            self.entrada_data.after_idle(lambda: self.entrada_data.icursor("end"))
            self.atualizar_grade()

        self.var_data.trace_add("write", ao_alterar)

    def _montar_grade(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="nsew")
        cartao.grid_columnconfigure(0, weight=1)

        self.titulo_dia = componentes.titulo_cartao(cartao, "Horários")
        self.grade = componentes.GradeHorarios(cartao, ao_clicar=self._ao_clicar_horario)
        self.grade.pack(fill="x", padx=20)

        botoes = ctk.CTkFrame(cartao, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(14, 20))
        self.botao_bloquear_dia = componentes.botao(
            botoes, "Bloquear o dia (folga)", self._bloquear_dia, largura=200, state="disabled"
        )
        self.botao_bloquear_dia.pack(side="left")
        self.botao_liberar_dia = componentes.botao(
            botoes, "Liberar o dia", self._liberar_dia, estilo="secundario",
            largura=150, state="disabled",
        )
        self.botao_liberar_dia.pack(side="left", padx=10)

        self.atualizar_grade()

    # ------------------------------------------------------------- busca
    def _buscar_medicos(self, texto, limite):
        return profissionais.listar(texto, apenas_ativos=True, limite=limite)

    @staticmethod
    def _texto_medico(p):
        return f"{p['nome']} - {p['especialidade']} ({p['registro']})"

    def _ao_escolher_medico(self, profissional):
        self.profissional = profissional
        self.atualizar_grade()

    def _ao_limpar_medico(self):
        self.profissional = None
        self.atualizar_grade()

    # ------------------------------------------------------------- dados
    def atualizar_lista(self):
        """Chamado pelo App quando a tela aparece."""
        self.atualizar_grade()

    def _data_escolhida(self):
        try:
            return data_br_para_date(self.var_data.get())
        except ErroValidacao:
            return None

    def atualizar_grade(self):
        data = self._data_escolhida()
        habilitar = self.profissional is not None and data is not None
        for b in (self.botao_bloquear_dia, self.botao_liberar_dia):
            b.configure(state="normal" if habilitar else "disabled")

        if self.profissional is None:
            self.titulo_dia.configure(text="Horários")
            self.grade.limpar("Escolha um médico para ver a agenda.")
            return
        if data is None:
            self.titulo_dia.configure(text="Horários")
            self.grade.limpar("Digite uma data válida (DD/MM/AAAA).")
            return
        self.titulo_dia.configure(
            text=f"{self.profissional['nome']} — {DIAS_SEMANA[data.weekday()]}, {date_para_br(data)}"
        )
        try:
            horarios = agenda.horarios_do_dia(self.profissional["id"], data)
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível abrir a agenda: {erro}")
            return
        self.grade.mostrar(horarios)

    def _mudar_dia(self, dias):
        data = self._data_escolhida() or date.today()
        self.var_data.set(date_para_br(data + timedelta(days=dias)))

    def _hoje(self):
        self.var_data.set(date_para_br(date.today()))

    # ------------------------------------------------------------ ações
    def _ao_clicar_horario(self, h):
        data = self._data_escolhida()
        if self.profissional is None or data is None:
            return
        pid = self.profissional["id"]
        faixa = f"{h['hora_inicio']} às {h['hora_fim']}"
        try:
            if h["estado"] == agenda.DISPONIVEL:
                if not messagebox.askyesno(
                    "Bloquear horário",
                    f"Deixar o horário {faixa} indisponível para {self.profissional['nome']}?",
                ):
                    return
                motivo = simpledialog.askstring(
                    "Motivo do bloqueio", "Motivo (opcional, ex.: reunião, folga):"
                )
                agenda.bloquear_horario(pid, data, h["hora_inicio"], motivo or "")
            elif h["estado"] == agenda.RESERVADO:
                c = consultas.obter(h["consulta_id"])
                nome = c["paciente_nome"] if c else "paciente não encontrado"
                messagebox.showinfo(
                    "Horário reservado",
                    f"{faixa}: consulta #{h['consulta_id']} de {nome}.\n"
                    "Para liberar o horário, cancele a consulta na tela Consultas.",
                )
                return
            elif h["bloqueio_id"] is not None:
                if not messagebox.askyesno(
                    "Liberar horário",
                    f"O horário {faixa} está bloqueado ({h['motivo']}).\nDeseja liberá-lo?",
                ):
                    return
                agenda.liberar_horario(pid, data, h["hora_inicio"])
            else:
                messagebox.showinfo("Horário indisponível", f"{faixa}: {h['motivo']}.")
                return
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível alterar: {erro}")
            return
        self.atualizar_grade()

    def _bloquear_dia(self):
        data = self._data_escolhida()
        if self.profissional is None or data is None:
            return
        if not messagebox.askyesno(
            "Bloquear o dia",
            f"Bloquear todos os horários livres de {date_para_br(data)} para "
            f"{self.profissional['nome']}?\nHorários já reservados são mantidos.",
        ):
            return
        motivo = simpledialog.askstring("Motivo", "Motivo (opcional, padrão: Folga):")
        try:
            bloqueados, mantidos = agenda.bloquear_dia(
                self.profissional["id"], data, motivo or "Folga"
            )
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível bloquear: {erro}")
            return
        texto = f"{bloqueados} horário(s) bloqueado(s)."
        if mantidos:
            texto += f"\n{mantidos} horário(s) com consulta foram mantidos."
        messagebox.showinfo("Dia bloqueado", texto)
        self.atualizar_grade()

    def _liberar_dia(self):
        data = self._data_escolhida()
        if self.profissional is None or data is None:
            return
        try:
            liberados = agenda.liberar_dia(self.profissional["id"], data)
        except (ErroValidacao, sqlite3.Error) as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        messagebox.showinfo(
            "Dia liberado",
            f"{liberados} horário(s) liberado(s)." if liberados
            else "Não havia bloqueios neste dia.",
        )
        self.atualizar_grade()
