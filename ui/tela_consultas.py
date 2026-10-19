"""Tela de agendamento e acompanhamento de consultas médicas.

Visual em CustomTkinter. A lógica (validações, regras de negócio) fica em `services/consultas`.
"""
import sqlite3
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from services import consultas, pacientes, profissionais
from services.validacoes import (
    ErroValidacao,
    formatar_cpf,
    iso_para_data_br,
    mascara_data,
    mascara_hora,
    somente_digitos,
)
from ui import componentes, tema


def aplicar_mascara(variavel, funcao, entrada):
    """Ajusta o campo enquanto o usuário digita e mantém o cursor no final."""

    def ao_alterar(*_):
        novo = funcao(variavel.get())
        if novo != variavel.get():
            variavel.set(novo)
        entrada.after_idle(lambda: entrada.icursor("end"))

    variavel.trace_add("write", ao_alterar)


class TelaConsultas(ctk.CTkFrame):
    NOME_MENU = "Consultas"
    COLUNAS = (
        ("id", "ID", 50),
        ("data", "Data", 90),
        ("hora", "Horário", 70),
        ("paciente", "Paciente", 200),
        ("profissional", "Profissional", 200),
        ("situacao", "Situação", 95),
        ("observacoes", "Observações", 200),
    )

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.id_selecionado = None
        self.situacao_selecionada = None

        self.mapa_pacientes = {}      # texto_exibicao -> id
        self.mapa_profissionais = {}  # texto_exibicao -> id

        self.var_paciente = ctk.StringVar()
        self.var_profissional = ctk.StringVar()
        self.var_data = ctk.StringVar()
        self.var_hora = ctk.StringVar()
        self.var_obs = ctk.StringVar()

        self.var_busca = ctk.StringVar()
        self.var_filtro_situacao = ctk.StringVar(value="Todas")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        componentes.cabecalho(
            self, "Consultas", "Agende, remarque, cancele e registre consultas realizadas."
        ).grid(row=0, column=0, sticky="w", pady=(0, 16))

        self._montar_formulario()
        self._montar_lista()
        self.recarregar_opcoes()
        self.atualizar_lista()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        self.cartao_form = componentes.cartao(self)
        self.cartao_form.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.titulo_form = componentes.titulo_cartao(self.cartao_form, "Agendar consulta")

        grade = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        grade.grid_columnconfigure(0, weight=3, uniform="campos_cons")
        grade.grid_columnconfigure(1, weight=3, uniform="campos_cons")
        grade.grid_columnconfigure(2, weight=2, uniform="campos_cons")
        grade.grid_columnconfigure(3, weight=2, uniform="campos_cons")

        # Linha 0: Paciente (2 colunas) e Profissional (2 colunas)
        bloco_pac, self.combo_paciente = componentes.campo_combobox(
            grade, "Paciente *", valores=[""], variavel=self.var_paciente,
            dica="selecione o paciente"
        )
        bloco_pac.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=(0, 12))

        bloco_prof, self.combo_profissional = componentes.campo_combobox(
            grade, "Profissional de Saúde *", valores=[""], variavel=self.var_profissional,
            dica="selecione o médico"
        )
        bloco_prof.grid(row=0, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=(0, 12))

        # Linha 1: Data, Horário e Observações
        bloco_data, self.entrada_data = componentes.campo_texto(
            grade, "Data *", self.var_data, dica="DD/MM/AAAA"
        )
        bloco_data.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 12))

        bloco_hora, self.entrada_hora = componentes.campo_texto(
            grade, "Horário *", self.var_hora, dica="HH:MM (ex: 09:30)"
        )
        bloco_hora.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(0, 12))

        bloco_obs, self.entrada_obs = componentes.campo_texto(
            grade, "Observações", self.var_obs, dica="opcional"
        )
        bloco_obs.grid(row=1, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=(0, 12))

        aplicar_mascara(self.var_data, mascara_data, self.entrada_data)
        aplicar_mascara(self.var_hora, mascara_hora, self.entrada_hora)

        botoes = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(2, 20))

        self.botao_salvar = componentes.botao(botoes, "Agendar", self.salvar, largura=170)
        self.botao_salvar.pack(side="left")

        componentes.botao(
            botoes, "Limpar / Novo", self.limpar, estilo="secundario"
        ).pack(side="left", padx=10)

        self.botao_realizada = componentes.botao(
            botoes, "Marcar como realizada", self.marcar_como_realizada,
            estilo="secundario", state="disabled", largura=190
        )
        self.botao_realizada.pack(side="left", padx=(0, 10))

        self.botao_cancelar = componentes.botao(
            botoes, "Cancelar consulta", self.cancelar_consulta,
            estilo="perigo", state="disabled", largura=160
        )
        self.botao_cancelar.pack(side="left")

    def _montar_lista(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="nsew")
        cartao.grid_columnconfigure(0, weight=1)
        cartao.grid_rowconfigure(1, weight=1)

        barra = ctk.CTkFrame(cartao, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))

        ctk.CTkLabel(
            barra, text="Situação:", font=tema.fonte(12, True),
            text_color=tema.COR_TEXTO,
        ).pack(side="left", padx=(0, 6))

        filtro = ctk.CTkOptionMenu(
            barra, values=["Todas", "Agendada", "Realizada", "Cancelada"],
            variable=self.var_filtro_situacao, command=lambda _v: self.buscar(),
            height=38, corner_radius=tema.RAIO_BOTAO,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO,
            button_color=tema.COR_BORDA, button_hover_color=tema.COR_HOVER_SUAVE,
            dropdown_font=tema.fonte(12), font=tema.fonte(12, True),
        )
        filtro.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(
            barra, text="Buscar (nome ou data):", font=tema.fonte(12, True),
            text_color=tema.COR_TEXTO,
        ).pack(side="left", padx=(0, 6))

        entrada_busca = ctk.CTkEntry(
            barra, textvariable=self.var_busca, width=220, height=38,
            corner_radius=tema.RAIO_BOTAO, border_color=tema.COR_BORDA,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO, font=tema.fonte(13),
        )
        entrada_busca.pack(side="left")
        entrada_busca.bind("<Return>", lambda _e: self.buscar())

        componentes.botao(barra, "Buscar", self.buscar, largura=90).pack(side="left", padx=10)
        componentes.botao(
            barra, "Mostrar todas", self.mostrar_todas, estilo="secundario"
        ).pack(side="left")

        quadro, self.tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=6)
        quadro.grid(row=1, column=0, sticky="nsew", padx=20)
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ctk.CTkLabel(
            cartao, text="", font=tema.fonte(12),
            text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self.rotulo_total.grid(row=2, column=0, sticky="w", padx=20, pady=(8, 14))

    # ------------------------------------------------------------- dados
    def recarregar_opcoes(self):
        """Recarrega os pacientes e profissionais disponíveis nos menus suspensos."""
        try:
            # Pacientes
            self.mapa_pacientes.clear()
            lista_p = pacientes.listar()
            opcoes_pacientes = []
            for p in lista_p:
                txt = f"{p['nome']} (CPF: {formatar_cpf(p['cpf'])})"
                self.mapa_pacientes[txt] = p["id"]
                opcoes_pacientes.append(txt)

            self.combo_paciente.configure(values=opcoes_pacientes or ["Nenhum paciente cadastrado"])
            if not self.var_paciente.get() and opcoes_pacientes:
                self.var_paciente.set(opcoes_pacientes[0])

            # Profissionais
            self.mapa_profissionais.clear()
            lista_pr = profissionais.listar()
            opcoes_profissionais = []
            for pr in lista_pr:
                txt = f"{pr['nome']} - {pr['especialidade']} ({pr['registro']})"
                if pr["ativo"] == 0:
                    txt += " [Inativo]"
                self.mapa_profissionais[txt] = pr["id"]
                opcoes_profissionais.append(txt)

            self.combo_profissional.configure(
                values=opcoes_profissionais or ["Nenhum profissional cadastrado"]
            )
            if not self.var_profissional.get() and opcoes_profissionais:
                # pré-seleciona o primeiro profissional ativo (inativos não podem ser agendados)
                ativos = [t for t in opcoes_profissionais if not t.endswith("[Inativo]")]
                self.var_profissional.set((ativos or opcoes_profissionais)[0])

        except sqlite3.Error as erro:
            messagebox.showerror(
                "Erro no banco de dados",
                f"Não foi possível carregar pacientes e profissionais: {erro}",
            )

    def atualizar_lista(self):
        """Recarrega a tabela de consultas a partir do banco de dados."""
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        situacao = self.var_filtro_situacao.get()
        busca = self.var_busca.get()

        try:
            lista = consultas.listar(busca=busca, situacao=situacao)
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return

        for c in lista:
            obs = c["observacoes"] or ""
            if c["motivo_cancelamento"]:
                obs = f"[Cancelamento: {c['motivo_cancelamento']}] {obs}".strip()

            self.tabela.insert(
                "",
                "end",
                iid=str(c["id"]),
                values=(
                    c["id"],
                    iso_para_data_br(c["data"]),
                    c["hora_inicio"],
                    c["paciente_nome"],
                    c["profissional_nome"],
                    c["situacao"],
                    obs,
                ),
            )

        self.rotulo_total.configure(text=f"{len(lista)} consulta(s) listada(s).")

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        try:
            dados = consultas.obter(self.id_selecionado)
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível abrir a consulta: {erro}")
            return
        if not dados:
            return

        self.situacao_selecionada = dados["situacao"]

        # Encontrar texto no mapa de pacientes
        for texto, p_id in self.mapa_pacientes.items():
            if p_id == dados["paciente_id"]:
                self.var_paciente.set(texto)
                break

        # Encontrar texto no mapa de profissionais
        for texto, pr_id in self.mapa_profissionais.items():
            if pr_id == dados["profissional_id"]:
                self.var_profissional.set(texto)
                break

        self.var_data.set(iso_para_data_br(dados["data"]))
        self.var_hora.set(dados["hora_inicio"])
        self.var_obs.set(dados["observacoes"] or "")

        self.titulo_form.configure(
            text=f"Editando consulta #{self.id_selecionado} ({self.situacao_selecionada})"
        )

        if self.situacao_selecionada == "Agendada":
            self.botao_salvar.configure(state="normal", text="Salvar alterações")
            self.botao_realizada.configure(state="normal")
            self.botao_cancelar.configure(state="normal")
        else:
            # Consultas já canceladas ou realizadas não podem ser reagendadas/canceladas de novo
            self.botao_salvar.configure(state="disabled", text="Consulta finalizada")
            self.botao_realizada.configure(state="disabled")
            self.botao_cancelar.configure(state="disabled")

    # ------------------------------------------------------------ ações
    def salvar(self):
        txt_paciente = self.var_paciente.get()
        txt_profissional = self.var_profissional.get()
        paciente_id = self.mapa_pacientes.get(txt_paciente)
        profissional_id = self.mapa_profissionais.get(txt_profissional)

        data_br = self.var_data.get()
        hora = self.var_hora.get()
        obs = self.var_obs.get()

        try:
            if self.id_selecionado is None:
                consultas.agendar(paciente_id, profissional_id, data_br, hora, obs)
                mensagem = "Consulta agendada com sucesso!"
            else:
                consultas.alterar_dados(
                    self.id_selecionado, paciente_id, profissional_id, data_br, hora, obs
                )
                mensagem = "Dados da consulta atualizados com sucesso!"
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível salvar: {erro}")
            return

        messagebox.showinfo("Sucesso", mensagem)
        self.limpar()
        self.atualizar_lista()

    def marcar_como_realizada(self):
        if self.id_selecionado is None:
            return
        if not messagebox.askyesno(
            "Confirmar", "Deseja marcar esta consulta como realizada?"
        ):
            return
        try:
            consultas.marcar_realizada(self.id_selecionado)
            messagebox.showinfo("Sucesso", "Consulta registrada como realizada com sucesso.")
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro", f"Não foi possível atualizar a consulta: {erro}")
            return
        self.limpar()
        self.atualizar_lista()

    def cancelar_consulta(self):
        if self.id_selecionado is None:
            return
        if not messagebox.askyesno(
            "Confirmar cancelamento",
            "Deseja realmente cancelar esta consulta?\n"
            "O horário será liberado e o histórico será preservado."
        ):
            return

        motivo = simpledialog.askstring(
            "Motivo do cancelamento", "Informe o motivo do cancelamento (opcional):"
        )
        try:
            consultas.cancelar(self.id_selecionado, motivo or "")
            messagebox.showinfo("Sucesso", "Consulta cancelada com sucesso.")
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro", f"Não foi possível cancelar: {erro}")
            return

        self.limpar()
        self.atualizar_lista()

    def limpar(self):
        self.id_selecionado = None
        self.situacao_selecionada = None
        self.var_data.set("")
        self.var_hora.set("")
        self.var_obs.set("")
        self.tabela.selection_remove(self.tabela.selection())
        self.titulo_form.configure(text="Agendar consulta")
        self.botao_salvar.configure(state="normal", text="Agendar")
        self.botao_realizada.configure(state="disabled")
        self.botao_cancelar.configure(state="disabled")
        self.recarregar_opcoes()

    def buscar(self):
        self.atualizar_lista()

    def mostrar_todas(self):
        self.var_busca.set("")
        self.var_filtro_situacao.set("Todas")
        self.atualizar_lista()
