"""Tela de agendamento e acompanhamento de consultas médicas.

Visual em CustomTkinter. A lógica (validações, regras de negócio) fica em `services/`.

No agendamento:
  * busca de médico (por nome ou especialidade) e de paciente (por nome, CPF ou telefone)
    com sugestões enquanto digita; pacientes desativados não aparecem;
  * ao escolher o médico aparecem a especialidade, o valor da consulta e os horários do dia
    (disponível, reservado e indisponível); clicar num horário disponível preenche o campo;
  * se o paciente não existir, o atalho "Cadastrar novo paciente" abre o cadastro rápido;
  * a consulta nasce "Aguardando pagamento" e só pode ser confirmada depois de paga.
"""
import sqlite3
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from services import (
    agenda, atestado, comprovante, consultas, pacientes, profissionais, receituario,
)
from services.validacoes import (
    ErroValidacao,
    brl,
    data_br_para_date,
    formatar_cpf,
    iso_para_data_br,
    mascara_data,
    mascara_hora,
)
from ui import componentes, tema
from ui.dialogos import DialogoAtestado, DialogoNovoPaciente, DialogoReceituario


def aplicar_mascara(variavel, funcao, entrada):
    """Ajusta o campo enquanto o usuário digita e mantém o cursor no final."""

    def ao_alterar(*_):
        novo = funcao(variavel.get())
        if novo != variavel.get():
            variavel.set(novo)
        entrada.after_idle(lambda: entrada.icursor("end"))

    variavel.trace_add("write", ao_alterar)


def texto_paciente(p):
    return f"{p['nome']} (CPF: {formatar_cpf(p['cpf'])})"


def texto_profissional(p):
    return f"{p['nome']} - {p['especialidade']} ({p['registro']})"


class TelaConsultas(ctk.CTkScrollableFrame):
    NOME_MENU = "Consultas"
    PRECISA_USUARIO = True  # o App entrega o usuário logado (fica registrado nos documentos salvos)
    COLUNAS = (
        ("id", "ID", 45),
        ("data", "Data", 85),
        ("hora", "Horário", 60),
        ("paciente", "Paciente", 160),
        ("profissional", "Profissional", 160),
        ("situacao", "Situação", 90),
        ("pagamento", "Pagamento", 135),
        ("valor", "Valor", 80),
        ("observacoes", "Observações", 160),
    )

    def __init__(self, master, usuario_logado):
        # Tela rolável: o formulário é alto e, sem a rolagem, a lista de consultas ficava
        # sem espaço. Agora a lista tem altura mínima própria e a página inteira rola.
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario_logado
        self.id_selecionado = None
        self.situacao_selecionada = None
        self.paciente = None      # paciente escolhido (dicionário)
        self.profissional = None  # médico escolhido (dicionário)

        self.var_data = ctk.StringVar()
        self.var_hora = ctk.StringVar()
        self.var_obs = ctk.StringVar()
        self.var_busca = ctk.StringVar()
        self.var_filtro_situacao = ctk.StringVar(value="Todas")
        self.var_papel = ctk.StringVar(value="80 mm")

        self.grid_columnconfigure(0, weight=1)

        componentes.cabecalho(
            self, "Consultas",
            "Agende, confirme (após o pagamento), remarque, cancele e registre consultas realizadas.",
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        self._montar_formulario()
        self._montar_lista()
        self.atualizar_lista()
        self.atualizar_horarios()

    # ------------------------------------------------------------ layout
    def _montar_formulario(self):
        self.cartao_form = componentes.cartao(self)
        self.cartao_form.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.titulo_form = componentes.titulo_cartao(self.cartao_form, "Agendar consulta")

        grade = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        grade.pack(fill="x", padx=20)
        for coluna, peso in enumerate((3, 3, 2, 2)):
            grade.grid_columnconfigure(coluna, weight=peso, uniform="campos_cons")

        # Linha 0: busca de paciente e de médico (com sugestões)
        self.campo_paciente = componentes.CampoComSugestoes(
            grade, "Paciente *", self._buscar_pacientes, texto_paciente,
            self._ao_escolher_paciente, dica="nome, CPF ou telefone",
            ao_limpar=self._ao_limpar_paciente,
            acao_sem_resultado=("+ Cadastrar novo paciente", self._cadastrar_paciente_rapido),
        )
        self.campo_paciente.grid(row=0, column=0, columnspan=2, sticky="new", padx=(0, 8), pady=(0, 10))

        self.campo_medico = componentes.CampoComSugestoes(
            grade, "Profissional de Saúde *", self._buscar_profissionais, texto_profissional,
            self._ao_escolher_profissional, dica="nome ou especialidade",
            ao_limpar=self._ao_limpar_profissional,
        )
        self.campo_medico.grid(row=0, column=2, columnspan=2, sticky="new", padx=(8, 0), pady=(0, 10))

        # Resumo do médico escolhido: especialidade e valor da consulta
        self.rotulo_medico = ctk.CTkLabel(
            grade, text="", font=tema.fonte(12, True), text_color=tema.COR_PRIMARIA, anchor="w",
        )
        self.rotulo_medico.grid(row=1, column=2, columnspan=2, sticky="w", padx=(8, 0), pady=(0, 8))

        # Linha 2: data, horário e observações
        bloco_data, self.entrada_data = componentes.campo_texto(
            grade, "Data *", self.var_data, dica="DD/MM/AAAA"
        )
        bloco_data.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        bloco_hora, self.entrada_hora = componentes.campo_texto(
            grade, "Horário *", self.var_hora, dica="clique abaixo ou digite HH:MM"
        )
        bloco_hora.grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(0, 10))
        bloco_obs, self.entrada_obs = componentes.campo_texto(
            grade, "Observações", self.var_obs, dica="opcional"
        )
        bloco_obs.grid(row=2, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=(0, 10))

        aplicar_mascara(self.var_data, mascara_data, self.entrada_data)
        aplicar_mascara(self.var_hora, mascara_hora, self.entrada_hora)
        self.var_data.trace_add("write", lambda *_: self.atualizar_horarios())
        self.var_hora.trace_add("write", lambda *_: self._marcar_horario_escolhido())

        # Linha 3: horários do médico no dia (três estados)
        self.grade_horarios = componentes.GradeHorarios(grade, ao_clicar=self._ao_clicar_horario)
        self.grade_horarios.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 6))

        botoes = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(2, 10))
        self.botao_salvar = componentes.botao(botoes, "Agendar", self.salvar, largura=170)
        self.botao_salvar.pack(side="left")
        componentes.botao(
            botoes, "Limpar / Novo", self.limpar, estilo="secundario"
        ).pack(side="left", padx=10)
        self.botao_confirmar = componentes.botao(
            botoes, "Confirmar consulta", self.confirmar_consulta, estilo="secundario",
            state="disabled", largura=170,
        )
        self.botao_confirmar.pack(side="left", padx=(0, 10))
        self.botao_realizada = componentes.botao(
            botoes, "Marcar como realizada", self.marcar_como_realizada,
            estilo="secundario", state="disabled", largura=190,
        )
        self.botao_realizada.pack(side="left", padx=(0, 10))
        self.botao_cancelar = componentes.botao(
            botoes, "Cancelar consulta", self.cancelar_consulta,
            estilo="perigo", state="disabled", largura=160,
        )
        self.botao_cancelar.pack(side="left")

        # Comprovante, atestado e receituário: o grupo só aparece quando uma consulta é selecionada.
        self.grupo_documentos = ctk.CTkFrame(self.cartao_form, fg_color="transparent")
        componentes.botao(
            self.grupo_documentos, "Imprimir comprovante", self.imprimir_comprovante, largura=190,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            self.grupo_documentos, text="Papel:", font=tema.fonte(12, True),
            text_color=tema.COR_TEXTO,
        ).pack(side="left", padx=(6, 6))
        ctk.CTkOptionMenu(
            self.grupo_documentos, values=["80 mm", "58 mm"], variable=self.var_papel,
            width=90, height=38, corner_radius=tema.RAIO_BOTAO,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO,
            button_color=tema.COR_BORDA, button_hover_color=tema.COR_HOVER_SUAVE,
            font=tema.fonte(12, True), dropdown_font=tema.fonte(12),
        ).pack(side="left")
        self.botao_atestado = componentes.botao(
            self.grupo_documentos, "Gerar atestado", self.gerar_atestado,
            estilo="secundario", largura=160,
        )
        self.botao_atestado.pack(side="left", padx=(24, 0))
        self.botao_receituario = componentes.botao(
            self.grupo_documentos, "Gerar receituário", self.gerar_receituario,
            estilo="secundario", largura=170,
        )
        self.botao_receituario.pack(side="left", padx=(8, 0))

    def _montar_lista(self):
        cartao = componentes.cartao(self)
        cartao.grid(row=2, column=0, sticky="nsew")
        cartao.grid_columnconfigure(0, weight=1)
        cartao.grid_rowconfigure(1, weight=1)

        barra = ctk.CTkFrame(cartao, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 8))

        ctk.CTkLabel(
            barra, text="Situação:", font=tema.fonte(12, True), text_color=tema.COR_TEXTO,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(
            barra, values=["Todas", "Agendada", "Confirmada", "Realizada", "Cancelada"],
            variable=self.var_filtro_situacao, command=lambda _v: self.atualizar_lista(),
            height=38, corner_radius=tema.RAIO_BOTAO,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO,
            button_color=tema.COR_BORDA, button_hover_color=tema.COR_HOVER_SUAVE,
            dropdown_font=tema.fonte(12), font=tema.fonte(12, True),
        ).pack(side="left", padx=(0, 14))

        busca, _entrada = componentes.barra_busca(
            barra, "Buscar (nome ou data):", self.var_busca, self.atualizar_lista, largura=220
        )
        busca.pack(side="left")

        self.botao_formulario = componentes.botao(
            barra, "Ocultar formulário", self._alternar_formulario,
            estilo="secundario", largura=170,
        )
        self.botao_formulario.pack(side="right")

        # 12 linhas visíveis (antes eram 5 e ainda sobrava quase nada de espaço).
        quadro, self.tabela = componentes.criar_tabela(cartao, self.COLUNAS, altura=12)
        quadro.grid(row=1, column=0, sticky="nsew", padx=20)
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self.rotulo_total = ctk.CTkLabel(
            cartao, text="", font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self.rotulo_total.grid(row=2, column=0, sticky="w", padx=20, pady=(8, 12))

    def _alternar_formulario(self):
        """Recolhe ou mostra o formulário de agendamento para dar mais espaço à lista."""
        if self.cartao_form.winfo_ismapped():
            self.cartao_form.grid_remove()
            self.botao_formulario.configure(text="Mostrar formulário")
        else:
            self.cartao_form.grid()
            self.botao_formulario.configure(text="Ocultar formulário")

    def _mostrar_formulario(self):
        if not self.cartao_form.winfo_ismapped():
            self._alternar_formulario()

    # ------------------------------------------------------------- buscas
    @staticmethod
    def _buscar_pacientes(texto, limite):
        # Pacientes desativados não aparecem no agendamento.
        return pacientes.listar(texto, incluir_inativos=False, limite=limite)

    @staticmethod
    def _buscar_profissionais(texto, limite):
        return profissionais.listar(texto, apenas_ativos=True, limite=limite)

    def _ao_escolher_paciente(self, paciente):
        self.paciente = paciente

    def _ao_limpar_paciente(self):
        self.paciente = None

    def _ao_escolher_profissional(self, profissional):
        self.profissional = profissional
        self._mostrar_resumo_medico()
        self.atualizar_horarios()

    def _ao_limpar_profissional(self):
        self.profissional = None
        self._mostrar_resumo_medico()
        self.atualizar_horarios()

    def _mostrar_resumo_medico(self):
        """Mostra a especialidade e o valor da consulta do médico escolhido."""
        if self.profissional is None:
            self.rotulo_medico.configure(text="")
            return
        self.rotulo_medico.configure(
            text=f"{self.profissional['especialidade']}  ·  Valor da consulta: "
                 f"{brl(self.profissional['valor_consulta'])}"
        )

    def _cadastrar_paciente_rapido(self):
        """Atalho: cadastra um paciente novo sem sair do agendamento e já o seleciona."""
        sugerido = self.campo_paciente.var.get().strip()
        dialogo = DialogoNovoPaciente(self.winfo_toplevel(), nome_sugerido=sugerido)
        self.wait_window(dialogo)
        if dialogo.resultado:
            novo = pacientes.obter(dialogo.resultado)
            self.campo_paciente.definir(novo)
            self.paciente = novo

    # ----------------------------------------------------- horários do médico
    def _data_escolhida(self):
        try:
            return data_br_para_date(self.var_data.get())
        except ErroValidacao:
            return None

    def atualizar_horarios(self):
        """Redesenha os horários (disponível/reservado/indisponível) do médico no dia escolhido."""
        if self.profissional is None:
            self.grade_horarios.limpar("Escolha o profissional para ver os horários.")
            return
        data = self._data_escolhida()
        if data is None:
            self.grade_horarios.limpar("Digite a data (DD/MM/AAAA) para ver os horários do médico.")
            return
        try:
            horarios = agenda.horarios_do_dia(
                self.profissional["id"], data, considerar_passado=True
            )
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível abrir a agenda: {erro}")
            return
        self.grade_horarios.mostrar(horarios, selecionado=self.var_hora.get().strip() or None)

    def _marcar_horario_escolhido(self):
        """Destaca na grade o horário digitado/clicado (sem consultar o banco de novo)."""
        for hora, b in self.grade_horarios._botoes.items():
            b.configure(
                border_width=3 if hora == self.var_hora.get().strip() else 0,
                border_color=tema.COR_TEXTO,
            )

    def _ao_clicar_horario(self, h):
        if h["estado"] == agenda.DISPONIVEL:
            self.var_hora.set(h["hora_inicio"])
        else:
            messagebox.showinfo(
                "Horário indisponível" if h["estado"] == agenda.INDISPONIVEL else "Horário reservado",
                f"{h['hora_inicio']} às {h['hora_fim']}: {h['motivo']}.\nEscolha um horário verde.",
            )

    # ------------------------------------------------------------- dados
    def recarregar_opcoes(self):
        """Chamado pelo App quando a tela aparece: atualiza o resumo e os horários."""
        if self.profissional is not None:  # o valor da especialidade pode ter mudado
            atualizado = profissionais.obter(self.profissional["id"])
            if atualizado:
                self.profissional = atualizado
                self._mostrar_resumo_medico()
        self.atualizar_horarios()

    def atualizar_lista(self):
        """Recarrega a tabela de consultas a partir do banco de dados."""
        for item in self.tabela.get_children():
            self.tabela.delete(item)

        try:
            lista = consultas.listar(
                busca=self.var_busca.get(), situacao=self.var_filtro_situacao.get()
            )
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return

        for c in lista:
            obs = c["observacoes"] or ""
            if c["motivo_cancelamento"]:
                obs = f"[Cancelamento: {c['motivo_cancelamento']}] {obs}".strip()
            self.tabela.insert(
                "", "end", iid=str(c["id"]),
                values=(
                    c["id"], iso_para_data_br(c["data"]), c["hora_inicio"],
                    c["paciente_nome"], c["profissional_nome"], c["situacao"],
                    c["pagamento_status"], brl(c["valor_centavos"]), obs,
                ),
            )
        self.rotulo_total.configure(
            text=componentes.texto_total(len(lista), self.var_busca.get(), "consulta(s)")
        )

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        self.id_selecionado = int(selecionados[0])
        self._mostrar_formulario()
        try:
            dados = consultas.obter(self.id_selecionado)
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível abrir a consulta: {erro}")
            return
        if not dados:
            return

        self.situacao_selecionada = dados["situacao"]

        self.paciente = pacientes.obter(dados["paciente_id"])
        self.campo_paciente.definir(self.paciente)
        self.profissional = profissionais.obter(dados["profissional_id"])
        self.campo_medico.definir(self.profissional)
        self._mostrar_resumo_medico()

        self.var_data.set(iso_para_data_br(dados["data"]))
        self.var_hora.set(dados["hora_inicio"])
        self.var_obs.set(dados["observacoes"] or "")
        self.atualizar_horarios()

        self.titulo_form.configure(
            text=f"Editando consulta #{self.id_selecionado} "
                 f"({self.situacao_selecionada} · {dados['pagamento_status']})"
        )
        self.grupo_documentos.pack(fill="x", padx=20, pady=(0, 18))
        for botao_doc in (self.botao_atestado, self.botao_receituario):
            botao_doc.configure(
                state="disabled" if self.situacao_selecionada == "Cancelada" else "normal"
            )

        ativa = self.situacao_selecionada in ("Agendada", "Confirmada")
        if ativa:
            self.botao_salvar.configure(state="normal", text="Salvar alterações")
            self.botao_realizada.configure(state="normal")
            self.botao_cancelar.configure(state="normal")
        else:
            # Consultas já canceladas ou realizadas não podem mais ser alteradas
            self.botao_salvar.configure(state="disabled", text="Consulta finalizada")
            self.botao_realizada.configure(state="disabled")
            self.botao_cancelar.configure(state="disabled")
        # "Confirmar" fica ligado enquanto Agendada: se não estiver paga, o sistema explica o porquê.
        self.botao_confirmar.configure(
            state="normal" if self.situacao_selecionada == "Agendada" else "disabled"
        )

    # ------------------------------------------------------------ ações
    def salvar(self):
        paciente_id = self.paciente["id"] if self.paciente else None
        profissional_id = self.profissional["id"] if self.profissional else None
        data_br = self.var_data.get()
        hora = self.var_hora.get()
        obs = self.var_obs.get()

        try:
            if self.id_selecionado is None:
                consultas.agendar(paciente_id, profissional_id, data_br, hora, obs)
                mensagem = (
                    "Consulta agendada com sucesso!\n"
                    "Situação: Aguardando pagamento. Ela só poderá ser confirmada depois que o "
                    "pagamento for registrado no módulo Financeiro."
                )
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

    def confirmar_consulta(self):
        if self.id_selecionado is None:
            return
        try:
            consultas.confirmar(self.id_selecionado)
        except ErroValidacao as erro:  # ex.: pagamento ainda não registrado
            messagebox.showwarning("Não foi possível confirmar", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro", f"Não foi possível confirmar a consulta: {erro}")
            return
        messagebox.showinfo("Sucesso", "Consulta confirmada com sucesso.")
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

    def imprimir_comprovante(self):
        """Abre o comprovante (com o status do pagamento) na janela de impressão."""
        if self.id_selecionado is None:
            return
        largura = 58 if self.var_papel.get().startswith("58") else 80
        try:
            comprovante.imprimir(self.id_selecionado, largura, clinica=tema.NOME_PROGRAMA)
        except ErroValidacao as erro:
            messagebox.showwarning("Comprovante", str(erro))
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível gerar: {erro}")

    def gerar_atestado(self):
        """Pede os dias e o CID e abre o atestado médico para impressão."""
        if self.id_selecionado is None:
            return
        dialogo = DialogoAtestado(self.winfo_toplevel())
        self.wait_window(dialogo)
        if not dialogo.resultado:
            return
        dias, cid, local = dialogo.resultado
        try:
            atestado.imprimir(
                self.id_selecionado, dias, cid, local, clinica=tema.NOME_PROGRAMA,
                usuario=self.usuario,
            )
        except ErroValidacao as erro:
            messagebox.showwarning("Atestado", str(erro))
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível gerar: {erro}")

    def gerar_receituario(self):
        """Abre o receituário (paciente e médico automáticos) para impressão."""
        if self.id_selecionado is None:
            return
        dialogo = DialogoReceituario(
            self.winfo_toplevel(),
            paciente=self.paciente["nome"] if self.paciente else "",
            medico=self.profissional["nome"] if self.profissional else "",
        )
        self.wait_window(dialogo)
        if not dialogo.resultado:
            return
        prescricao, local = dialogo.resultado
        try:
            receituario.imprimir(
                self.id_selecionado, prescricao, local, clinica=tema.NOME_PROGRAMA,
                usuario=self.usuario,
            )
        except ErroValidacao as erro:
            messagebox.showwarning("Receituário", str(erro))
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível gerar: {erro}")

    def limpar(self):
        self.id_selecionado = None
        self.situacao_selecionada = None
        self.paciente = None
        self.profissional = None
        self.grupo_documentos.pack_forget()  # esconde comprovante e atestado
        self.campo_paciente.limpar()
        self.campo_medico.limpar()
        self.rotulo_medico.configure(text="")
        self.var_data.set("")
        self.var_hora.set("")
        self.var_obs.set("")
        self.tabela.selection_remove(self.tabela.selection())
        self.titulo_form.configure(text="Agendar consulta")
        self.botao_salvar.configure(state="normal", text="Agendar")
        self.botao_confirmar.configure(state="disabled")
        self.botao_realizada.configure(state="disabled")
        self.botao_cancelar.configure(state="disabled")
        self.atualizar_horarios()
