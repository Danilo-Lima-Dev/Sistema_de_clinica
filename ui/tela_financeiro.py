"""Módulo financeiro (só aparece para o super usuário).

Três abas:
  * Pagamentos - painel (total recebido e pendente), filtros por período, médico e
    especialidade, e os botões para registrar/desfazer o pagamento e ajustar o valor da consulta;
  * Valores por especialidade - define o valor da consulta de cada especialidade;
  * Histórico - quem alterou valores e pagamentos, e quando.

A permissão é conferida de novo no back-end (`services/financeiro.py`) a cada ação.
"""
import sqlite3
from tkinter import messagebox, simpledialog

import customtkinter as ctk

from services import especialidades, financeiro, profissionais
from services.validacoes import (
    ErroValidacao,
    brl,
    centavos_para_campo,
    data_br_para_date,
    iso_para_data_br,
    mascara_data,
    valor_para_centavos,
)
from ui import componentes, tema

TODOS = "Todos"


def _ligar_mascara(variavel, entrada, funcao):
    def ao_alterar(*_):
        novo = funcao(variavel.get())
        if novo != variavel.get():
            variavel.set(novo)
        entrada.after_idle(lambda: entrada.icursor("end"))

    variavel.trace_add("write", ao_alterar)


class TelaFinanceiro(ctk.CTkFrame):
    NOME_MENU = "Financeiro"
    PRECISA_USUARIO = True  # o App entrega o usuário logado
    COLUNAS_PAGAMENTOS = (
        ("id", "ID", 50),
        ("data", "Data", 90),
        ("paciente", "Paciente", 170),
        ("profissional", "Médico", 170),
        ("especialidade", "Especialidade", 130),
        ("valor", "Valor", 90),
        ("situacao", "Consulta", 90),
        ("pagamento", "Pagamento", 140),
    )

    def __init__(self, master, usuario_logado):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario_logado
        self.id_consulta = None
        self.id_especialidade = None
        self.mapa_medicos = {TODOS: None}
        self.mapa_especialidades = {TODOS: None}

        self.var_de = ctk.StringVar()
        self.var_ate = ctk.StringVar()
        self.var_medico = ctk.StringVar(value=TODOS)
        self.var_especialidade = ctk.StringVar(value=TODOS)
        self.var_pagamento = ctk.StringVar(value=TODOS)
        self.var_valor_esp = ctk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        componentes.cabecalho(
            self, "Financeiro",
            "Valores das consultas, pagamentos recebidos e histórico de alterações.",
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.abas = ctk.CTkTabview(
            self, fg_color=tema.COR_CARTAO, border_width=1, border_color=tema.COR_BORDA,
            segmented_button_selected_color=tema.COR_PRIMARIA,
            segmented_button_selected_hover_color=tema.COR_PRIMARIA_HOVER,
        )
        self.abas.grid(row=1, column=0, sticky="nsew")
        for nome in ("Pagamentos", "Valores por especialidade", "Histórico"):
            self.abas.add(nome)
        self._montar_pagamentos(self.abas.tab("Pagamentos"))
        self._montar_valores(self.abas.tab("Valores por especialidade"))
        self._montar_historico(self.abas.tab("Histórico"))

        self.recarregar_opcoes()
        self.atualizar_lista()

    # ======================================================== aba Pagamentos
    def _montar_pagamentos(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(3, weight=1)

        # --- totais
        totais = ctk.CTkFrame(aba, fg_color="transparent")
        totais.grid(row=0, column=0, sticky="ew", pady=(4, 10))
        self.rotulo_recebido = self._painel(totais, "Total recebido", tema.COR_PRIMARIA)
        self.rotulo_pendente = self._painel(totais, "Total pendente", tema.COR_SLOT_RESERVADO)

        # --- filtros
        filtros = ctk.CTkFrame(aba, fg_color="transparent")
        filtros.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        bloco, entrada = componentes.campo_texto(filtros, "De", self.var_de, dica="DD/MM/AAAA")
        bloco.pack(side="left", padx=(0, 8))
        bloco.configure(width=130)
        _ligar_mascara(self.var_de, entrada, mascara_data)
        bloco, entrada = componentes.campo_texto(filtros, "Até", self.var_ate, dica="DD/MM/AAAA")
        bloco.pack(side="left", padx=(0, 8))
        _ligar_mascara(self.var_ate, entrada, mascara_data)

        bloco, self.combo_medico = componentes.campo_combobox(
            filtros, "Médico", valores=[TODOS], variavel=self.var_medico,
        )
        bloco.pack(side="left", padx=(0, 8))
        bloco, self.combo_especialidade = componentes.campo_combobox(
            filtros, "Especialidade", valores=[TODOS], variavel=self.var_especialidade,
        )
        bloco.pack(side="left", padx=(0, 8))
        bloco, _combo = componentes.campo_combobox(
            filtros, "Pagamento", valores=[TODOS, financeiro.AGUARDANDO, financeiro.PAGO],
            variavel=self.var_pagamento,
        )
        bloco.pack(side="left", padx=(0, 8))

        acoes = ctk.CTkFrame(filtros, fg_color="transparent")
        acoes.pack(side="left", anchor="s")
        componentes.botao(acoes, "Filtrar", self.atualizar_lista, largura=90).pack(side="left")
        componentes.botao(
            acoes, "Limpar", self._limpar_filtros, estilo="secundario", largura=80
        ).pack(side="left", padx=(8, 0))

        # --- botões de ação
        botoes = ctk.CTkFrame(aba, fg_color="transparent")
        botoes.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.botao_pagar = componentes.botao(
            botoes, "Registrar pagamento", self.registrar_pagamento, largura=190, state="disabled"
        )
        self.botao_pagar.pack(side="left")
        self.botao_desfazer = componentes.botao(
            botoes, "Desfazer pagamento", self.desfazer_pagamento, estilo="secundario",
            largura=180, state="disabled",
        )
        self.botao_desfazer.pack(side="left", padx=8)
        self.botao_valor = componentes.botao(
            botoes, "Alterar valor da consulta", self.alterar_valor_consulta,
            estilo="secundario", largura=210, state="disabled",
        )
        self.botao_valor.pack(side="left")

        quadro, self.tabela = componentes.criar_tabela(aba, self.COLUNAS_PAGAMENTOS, altura=6)
        quadro.grid(row=3, column=0, sticky="nsew")
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar_consulta)
        self.rotulo_total = ctk.CTkLabel(
            aba, text="", font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE, anchor="w"
        )
        self.rotulo_total.grid(row=4, column=0, sticky="w", pady=(6, 0))

    def _painel(self, master, titulo, cor):
        quadro = ctk.CTkFrame(
            master, fg_color=tema.COR_FUNDO, corner_radius=tema.RAIO_CARTAO,
            border_width=1, border_color=tema.COR_BORDA,
        )
        quadro.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(
            quadro, text=titulo, font=tema.fonte(12, True), text_color=tema.COR_TEXTO_SUAVE
        ).pack(anchor="w", padx=18, pady=(10, 0))
        valor = ctk.CTkLabel(quadro, text="R$ 0,00", font=tema.fonte(24, True), text_color=cor)
        valor.pack(anchor="w", padx=18, pady=(0, 10))
        detalhe = ctk.CTkLabel(
            quadro, text="", font=tema.fonte(11), text_color=tema.COR_TEXTO_SUAVE
        )
        detalhe.pack(anchor="w", padx=18, pady=(0, 10))
        valor.detalhe = detalhe
        return valor

    # ================================================ aba Valores/Especialidade
    def _montar_valores(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(aba, fg_color="transparent")
        form.grid(row=0, column=0, sticky="ew", pady=(6, 10))
        self.rotulo_esp = ctk.CTkLabel(
            form, text="Selecione uma especialidade na lista.", font=tema.fonte(13, True),
            text_color=tema.COR_TEXTO,
        )
        self.rotulo_esp.pack(side="left", padx=(0, 16))
        bloco, self.entrada_valor_esp = componentes.campo_texto(
            form, "Valor da consulta", self.var_valor_esp, dica="R$ — ex.: 150,00"
        )
        bloco.pack(side="left", padx=(0, 12))
        self.botao_salvar_valor = componentes.botao(
            form, "Salvar valor", self.salvar_valor_especialidade, largura=130, state="disabled"
        )
        self.botao_salvar_valor.pack(side="left", anchor="s")

        quadro, self.tabela_esp = componentes.criar_tabela(
            aba, (("id", "ID", 50), ("nome", "Especialidade", 300), ("valor", "Valor da consulta", 160)),
            altura=6,
        )
        quadro.grid(row=1, column=0, sticky="nsew")
        self.tabela_esp.bind("<<TreeviewSelect>>", self._ao_selecionar_especialidade)
        ctk.CTkLabel(
            aba, text="O novo valor vale para os próximos agendamentos; consultas já agendadas "
            "mantêm o valor delas (ajustável na aba Pagamentos).",
            font=tema.fonte(11), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

    # ===================================================== aba Histórico
    def _montar_historico(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        aba.grid_rowconfigure(0, weight=1)
        quadro, self.tabela_hist = componentes.criar_tabela(
            aba, (("data", "Quando", 140), ("usuario", "Quem alterou", 200), ("descricao", "O que mudou", 480)),
            altura=8,
        )
        quadro.grid(row=0, column=0, sticky="nsew", pady=(6, 0))

    # =================================================================== dados
    def recarregar_opcoes(self):
        """Atualiza os menus de médico e especialidade dos filtros."""
        try:
            self.mapa_medicos = {TODOS: None}
            for p in profissionais.listar():
                self.mapa_medicos[f"{p['nome']} - {p['especialidade']}"] = p["id"]
            self.mapa_especialidades = {TODOS: None}
            for e in especialidades.listar():
                self.mapa_especialidades[e["nome"]] = e["id"]
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível carregar os filtros: {erro}")
            return
        self.combo_medico.configure(values=list(self.mapa_medicos))
        self.combo_especialidade.configure(values=list(self.mapa_especialidades))
        if self.var_medico.get() not in self.mapa_medicos:
            self.var_medico.set(TODOS)
        if self.var_especialidade.get() not in self.mapa_especialidades:
            self.var_especialidade.set(TODOS)

    def _filtros(self):
        """Lê os filtros da tela. Devolve None (e avisa) se alguma data estiver errada."""
        datas = []
        for variavel, nome in ((self.var_de, "inicial"), (self.var_ate, "final")):
            texto = variavel.get().strip()
            if not texto:
                datas.append(None)
                continue
            try:
                datas.append(data_br_para_date(texto).isoformat())
            except ErroValidacao:
                messagebox.showwarning("Verifique o filtro", f"Data {nome} inválida. Use DD/MM/AAAA.")
                return None
        if datas[0] and datas[1] and datas[0] > datas[1]:
            messagebox.showwarning("Verifique o filtro", "A data inicial é depois da data final.")
            return None
        pagamento = self.var_pagamento.get()
        return dict(
            data_inicio_iso=datas[0], data_fim_iso=datas[1],
            profissional_id=self.mapa_medicos.get(self.var_medico.get()),
            especialidade_id=self.mapa_especialidades.get(self.var_especialidade.get()),
        ), (None if pagamento == TODOS else pagamento)

    def atualizar_lista(self):
        """Recarrega as três abas (chamado pelo App ao abrir a tela e pelos botões)."""
        lido = self._filtros()
        if lido is None:
            return
        filtros, pagamento = lido
        uid = self.usuario["id"]
        try:
            resumo = financeiro.resumo(uid, **filtros)
            lista = financeiro.listar_consultas(uid, pagamento=pagamento, **filtros)
            lista_esp = especialidades.listar()
            historico = financeiro.historico(uid)
        except ErroValidacao as erro:
            messagebox.showwarning("Acesso negado", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível carregar: {erro}")
            return

        self.rotulo_recebido.configure(text=brl(resumo["recebido"]))
        self.rotulo_recebido.detalhe.configure(text=f"{resumo['qtd_pagas']} consulta(s) paga(s)")
        self.rotulo_pendente.configure(text=brl(resumo["pendente"]))
        self.rotulo_pendente.detalhe.configure(
            text=f"{resumo['qtd_pendentes']} consulta(s) aguardando (canceladas não contam)"
        )

        self._limpar_tabela(self.tabela)
        for c in lista:
            self.tabela.insert(
                "", "end", iid=str(c["id"]),
                values=(
                    c["id"], iso_para_data_br(c["data"]), c["paciente_nome"],
                    c["profissional_nome"], c["especialidade_nome"], brl(c["valor_centavos"]),
                    c["situacao"], c["pagamento_status"],
                ),
            )
        self.rotulo_total.configure(text=f"{len(lista)} consulta(s) no filtro.")
        self.id_consulta = None
        self._atualizar_botoes()

        self._limpar_tabela(self.tabela_esp)
        for e in lista_esp:
            self.tabela_esp.insert(
                "", "end", iid=str(e["id"]), values=(e["id"], e["nome"], brl(e["valor_consulta"]))
            )
        self._limpar_tabela(self.tabela_hist)
        for h in historico:
            self.tabela_hist.insert(
                "", "end", iid=str(h["id"]),
                values=(self._data_hora(h["data_hora"]), h["usuario_nome"], h["descricao"]),
            )

    @staticmethod
    def _data_hora(texto):
        """'2026-10-21 19:37:00' -> '21/10/2026 19:37'."""
        try:
            return f"{iso_para_data_br(texto[:10])} {texto[11:16]}"
        except ValueError:
            return texto

    @staticmethod
    def _limpar_tabela(tabela):
        for item in tabela.get_children():
            tabela.delete(item)

    def _limpar_filtros(self):
        self.var_de.set("")
        self.var_ate.set("")
        self.var_medico.set(TODOS)
        self.var_especialidade.set(TODOS)
        self.var_pagamento.set(TODOS)
        self.atualizar_lista()

    # ========================================================= seleção/botões
    def _ao_selecionar_consulta(self, _evento):
        selecionados = self.tabela.selection()
        self.id_consulta = int(selecionados[0]) if selecionados else None
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        if self.id_consulta is None:
            for b in (self.botao_pagar, self.botao_desfazer, self.botao_valor):
                b.configure(state="disabled")
            return
        _id, _data, _pac, _med, _esp, _valor, situacao, pagamento = self.tabela.item(
            str(self.id_consulta), "values"
        )
        pago = pagamento == financeiro.PAGO
        cancelada = situacao == "Cancelada"
        self.botao_pagar.configure(state="normal" if not pago and not cancelada else "disabled")
        self.botao_desfazer.configure(state="normal" if pago else "disabled")
        self.botao_valor.configure(state="normal" if not pago and not cancelada else "disabled")

    def _executar(self, acao, mensagem_ok):
        """Roda uma ação do financeiro mostrando os erros de forma amigável."""
        try:
            acao()
        except ErroValidacao as erro:
            messagebox.showwarning("Aviso", str(erro))
            return False
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível concluir: {erro}")
            return False
        if mensagem_ok:
            messagebox.showinfo("Sucesso", mensagem_ok)
        self.atualizar_lista()
        return True

    # ================================================================= ações
    def registrar_pagamento(self):
        if self.id_consulta is None:
            return
        valores = self.tabela.item(str(self.id_consulta), "values")
        if not messagebox.askyesno(
            "Registrar pagamento",
            f"Confirmar que a consulta #{self.id_consulta} ({valores[2]}) foi paga?\n"
            f"Valor: {valores[5]}",
        ):
            return
        self._executar(
            lambda: financeiro.registrar_pagamento(self.usuario["id"], self.id_consulta),
            "Pagamento registrado. A consulta já pode ser confirmada.",
        )

    def desfazer_pagamento(self):
        if self.id_consulta is None:
            return
        if not messagebox.askyesno(
            "Desfazer pagamento",
            f"Tem certeza que deseja desfazer o pagamento da consulta #{self.id_consulta}?",
        ):
            return
        self._executar(
            lambda: financeiro.desfazer_pagamento(self.usuario["id"], self.id_consulta),
            "Pagamento desfeito.",
        )

    def alterar_valor_consulta(self):
        if self.id_consulta is None:
            return
        atual = self.tabela.item(str(self.id_consulta), "values")[5]
        texto = simpledialog.askstring(
            "Alterar valor", f"Novo valor da consulta #{self.id_consulta} (atual: {atual}):"
        )
        if texto is None:
            return
        try:
            centavos = valor_para_centavos(texto)
        except ErroValidacao as erro:
            messagebox.showwarning("Valor inválido", str(erro))
            return
        self._executar(
            lambda: financeiro.alterar_valor_consulta(self.usuario["id"], self.id_consulta, centavos),
            "Valor da consulta atualizado.",
        )

    def _ao_selecionar_especialidade(self, _evento):
        selecionados = self.tabela_esp.selection()
        if not selecionados:
            return
        self.id_especialidade = int(selecionados[0])
        _id, nome, valor = self.tabela_esp.item(selecionados[0], "values")
        esp = especialidades.obter(self.id_especialidade)
        self.rotulo_esp.configure(text=nome)
        self.var_valor_esp.set(centavos_para_campo(esp["valor_consulta"]) if esp else "")
        self.botao_salvar_valor.configure(state="normal")

    def salvar_valor_especialidade(self):
        if self.id_especialidade is None:
            return
        try:
            centavos = valor_para_centavos(self.var_valor_esp.get())
        except ErroValidacao as erro:
            messagebox.showwarning("Valor inválido", str(erro))
            return
        self._executar(
            lambda: financeiro.alterar_valor_especialidade(
                self.usuario["id"], self.id_especialidade, centavos
            ),
            "Valor da especialidade atualizado.",
        )
