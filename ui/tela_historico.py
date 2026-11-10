"""Histórico clínico por paciente (SÓ para o papel Médico).

Escolha o paciente; a lista mostra as anotações dele (da mais recente para a mais antiga).
Ao lado, o texto da anotação escolhida. O médico pode escrever novas anotações, ligá-las a uma
consulta e corrigir as que ele mesmo escreveu (a versão anterior fica guardada). As anotações
de outros médicos podem ser lidas, mas não alteradas.

A permissão é conferida de novo no back-end (`services/historico_clinico.py`).
"""
import sqlite3
from tkinter import messagebox

import customtkinter as ctk

from services import historico_clinico, pacientes
from services.validacoes import ErroValidacao, formatar_cpf, iso_para_data_br
from ui import componentes, tema
from ui.dialogos import DialogoRevisoes

SEM_CONSULTA = "(sem consulta específica)"


def _data_hora(texto):
    """'2026-11-10 14:35:00' -> '10/11/2026 14:35'."""
    return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]} {texto[11:16]}" if texto else ""


class TelaHistoricoClinico(ctk.CTkFrame):
    NOME_MENU = "Histórico clínico"
    PRECISA_USUARIO = True  # o App entrega o usuário logado
    COLUNAS = (
        ("id", "ID", 40),
        ("data", "Escrita em", 125),
        ("consulta", "Consulta", 120),
        ("autor", "Médico", 130),
    )

    def __init__(self, master, usuario_logado):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario_logado
        self.paciente = None
        self.anotacao = None          # dicionário da anotação selecionada (None = nova)
        self.anotacoes = {}           # id -> anotação do paciente escolhido
        self.consultas = {}           # texto do combobox -> id da consulta
        self.var_consulta = ctk.StringVar(value=SEM_CONSULTA)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        componentes.cabecalho(
            self, "Histórico clínico",
            "Anotações do médico sobre cada paciente. Só médicos veem e alteram.",
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        cartao = componentes.cartao(self)
        cartao.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.campo_paciente = componentes.CampoComSugestoes(
            cartao, "Paciente", self._buscar,
            lambda p: f"{p['nome']} (CPF: {formatar_cpf(p['cpf'])})"
                      + ("" if p["ativo"] else " [desativado]"),
            self._ao_escolher, dica="nome, CPF ou telefone", ao_limpar=self._ao_limpar,
        )
        self.campo_paciente.pack(fill="x", padx=20, pady=18)

        corpo = componentes.cartao(self)
        corpo.grid(row=2, column=0, sticky="nsew")
        corpo.grid_columnconfigure(0, weight=2)
        corpo.grid_columnconfigure(1, weight=3)
        corpo.grid_rowconfigure(0, weight=1)

        # --- lista de anotações
        esquerda = ctk.CTkFrame(corpo, fg_color="transparent")
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=(18, 14))
        esquerda.grid_columnconfigure(0, weight=1)
        esquerda.grid_rowconfigure(0, weight=1)
        quadro, self.tabela = componentes.criar_tabela(esquerda, self.COLUNAS, altura=8)
        quadro.grid(row=0, column=0, sticky="nsew")
        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self.rotulo_total = ctk.CTkLabel(
            esquerda, text="", font=tema.fonte(12), text_color=tema.COR_TEXTO_SUAVE, anchor="w"
        )
        self.rotulo_total.grid(row=1, column=0, sticky="w", pady=(8, 0))

        # --- anotação (ver / escrever / alterar)
        direita = ctk.CTkFrame(corpo, fg_color="transparent")
        direita.grid(row=0, column=1, sticky="nsew", padx=(10, 20), pady=(18, 14))
        direita.grid_columnconfigure(0, weight=1)
        direita.grid_rowconfigure(2, weight=1)
        self.titulo = ctk.CTkLabel(
            direita, text="Nova anotação", font=tema.fonte(15, True),
            text_color=tema.COR_TEXTO, anchor="w",
        )
        self.titulo.grid(row=0, column=0, sticky="ew")
        bloco, self.combo_consulta = componentes.campo_combobox(
            direita, "Consulta", valores=[SEM_CONSULTA], variavel=self.var_consulta,
            dica="opcional",
        )
        bloco.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        self.texto = ctk.CTkTextbox(
            direita, corner_radius=tema.RAIO_BOTAO, border_width=1, border_color=tema.COR_BORDA,
            fg_color=tema.COR_CARTAO, text_color=tema.COR_TEXTO, font=tema.fonte(13), wrap="word",
        )
        self.texto.grid(row=2, column=0, sticky="nsew")
        self.texto.bind("<KeyRelease>", lambda _e: self._atualizar_contador())
        self.rotulo_info = ctk.CTkLabel(
            direita, text="", font=tema.fonte(11), text_color=tema.COR_TEXTO_SUAVE,
            anchor="w", justify="left", wraplength=460,
        )
        self.rotulo_info.grid(row=3, column=0, sticky="ew", pady=(6, 6))
        botoes = ctk.CTkFrame(direita, fg_color="transparent")
        botoes.grid(row=4, column=0, sticky="ew")
        self.botao_salvar = componentes.botao(botoes, "Adicionar anotação", self.salvar, largura=170)
        self.botao_salvar.pack(side="left")
        self.botao_nova = componentes.botao(
            botoes, "Nova anotação", self._nova, estilo="secundario", largura=140
        )
        self.botao_nova.pack(side="left", padx=8)
        self.botao_versoes = componentes.botao(
            botoes, "Versões anteriores", self.ver_versoes, estilo="secundario",
            largura=160, state="disabled",
        )
        self.botao_versoes.pack(side="left")

        self._nova()

    # ------------------------------------------------------------- busca
    @staticmethod
    def _buscar(texto, limite):
        return pacientes.listar(texto, incluir_inativos=True, limite=limite)

    def _ao_escolher(self, paciente):
        self.paciente = paciente
        self.atualizar_lista()

    def _ao_limpar(self):
        self.paciente = None
        self.atualizar_lista()

    # ------------------------------------------------------------- dados
    def atualizar_lista(self):
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        self._nova()
        if self.paciente is None:
            self.rotulo_total.configure(text="Escolha um paciente para ver o histórico.")
            self._definir_edicao(False)
            return
        try:
            lista = historico_clinico.listar(self.usuario["id"], self.paciente["id"])
            consultas_pac = historico_clinico.consultas_do_paciente(
                self.usuario["id"], self.paciente["id"]
            )
        except ErroValidacao as erro:
            messagebox.showwarning("Acesso negado", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível listar: {erro}")
            return
        self.anotacoes = {a["id"]: a for a in lista}
        self.consultas = {
            f"{iso_para_data_br(c['data'])} {c['hora_inicio']} - {c['medico']} ({c['situacao']})": c["id"]
            for c in consultas_pac
        }
        self.combo_consulta.configure(values=[SEM_CONSULTA, *self.consultas])
        for a in lista:
            consulta = (
                f"{iso_para_data_br(a['consulta_data'])} {a['consulta_hora']}"
                if a["consulta_id"] else "—"
            )
            self.tabela.insert(
                "", "end", iid=str(a["id"]),
                values=(a["id"], _data_hora(a["criado_em"]), consulta, a["autor_nome"]),
            )
        self.rotulo_total.configure(
            text=f"{len(lista)} anotação(ões)." if lista else "Nenhuma anotação para este paciente."
        )
        self._definir_edicao(True)

    # --------------------------------------------------------- formulário
    def _definir_edicao(self, pode):
        """Liga/desliga o texto e os botões de salvar."""
        estado = "normal" if pode else "disabled"
        self.texto.configure(state=estado)
        self.combo_consulta.configure(state="normal" if pode and self.anotacao is None else "disabled")
        self.botao_salvar.configure(state=estado)
        self.botao_nova.configure(state="normal" if self.paciente else "disabled")

    def _escrever(self, texto):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", texto)
        self._atualizar_contador()

    def _atualizar_contador(self):
        if self.anotacao is None and self.paciente is None:
            return
        n = len(self.texto.get("1.0", "end").strip())
        base = self.rotulo_info.cget("text").split("\n")[0] if self.anotacao else ""
        contador = f"{n}/{historico_clinico.LIMITE_TEXTO} caracteres"
        self.rotulo_info.configure(text=f"{base}\n{contador}" if base else contador)

    def _nova(self):
        """Prepara o formulário para uma nova anotação."""
        self.anotacao = None
        if self.tabela.selection():
            self.tabela.selection_remove(self.tabela.selection())
        self.titulo.configure(text="Nova anotação")
        self.var_consulta.set(SEM_CONSULTA)
        self._escrever("")
        self.botao_salvar.configure(text="Adicionar anotação")
        self.botao_versoes.configure(state="disabled")
        self._definir_edicao(self.paciente is not None)
        self.rotulo_info.configure(text="")

    def _ao_selecionar(self, _evento):
        selecionados = self.tabela.selection()
        if not selecionados:
            return
        a = self.anotacoes.get(int(selecionados[0]))
        if a is None:
            return
        self.anotacao = a
        minha = a["autor_id"] == self.usuario["id"]
        self.titulo.configure(
            text=f"Anotação #{a['id']}" + ("" if minha else " (somente leitura)")
        )
        consulta = SEM_CONSULTA
        if a["consulta_id"]:
            consulta = f"{iso_para_data_br(a['consulta_data'])} {a['consulta_hora']} - {a['consulta_medico']}"
        self.combo_consulta.configure(state="normal")
        self.var_consulta.set(consulta)
        self.combo_consulta.configure(state="disabled")
        self._escrever(a["texto"])
        info = f"Escrita por {a['autor_nome']} em {_data_hora(a['criado_em'])}."
        if a["atualizado_em"]:
            info += f" Alterada por {a['atualizado_por']} em {_data_hora(a['atualizado_em'])}."
        if not minha:
            info += " Só o autor pode alterar."
        self.rotulo_info.configure(text=info)
        self._atualizar_contador()
        self.botao_salvar.configure(
            text="Salvar alteração", state="normal" if minha else "disabled"
        )
        self.texto.configure(state="normal" if minha else "disabled")
        self.botao_versoes.configure(state="normal" if a["atualizado_em"] else "disabled")
        self.botao_nova.configure(state="normal")

    # ------------------------------------------------------------ ações
    def salvar(self):
        if self.paciente is None:
            return
        texto = self.texto.get("1.0", "end")
        try:
            if self.anotacao is None:
                consulta_id = self.consultas.get(self.var_consulta.get())
                historico_clinico.adicionar(
                    self.usuario["id"], self.paciente["id"], texto, consulta_id
                )
                mensagem = "Anotação adicionada ao histórico."
            else:
                texto_limpo = historico_clinico.validar_texto(texto)  # valida antes de perguntar
                if texto_limpo == self.anotacao["texto"]:
                    messagebox.showinfo("Histórico clínico", "Nenhuma alteração para salvar.")
                    return
                if not messagebox.askyesno(
                    "Confirmar alteração",
                    "Salvar a alteração desta anotação?\nA versão anterior fica guardada em "
                    "\"Versões anteriores\".",
                ):
                    return
                historico_clinico.alterar(self.usuario["id"], self.anotacao["id"], texto)
                mensagem = "Anotação alterada. A versão anterior foi guardada."
        except ErroValidacao as erro:
            messagebox.showwarning("Verifique os dados", str(erro))
            return
        except sqlite3.Error as erro:
            messagebox.showerror("Erro no banco de dados", f"Não foi possível salvar: {erro}")
            return
        messagebox.showinfo("Sucesso", mensagem)
        self.atualizar_lista()

    def ver_versoes(self):
        if self.anotacao is None:
            return
        try:
            versoes = historico_clinico.revisoes(self.usuario["id"], self.anotacao["id"])
        except (ErroValidacao, sqlite3.Error) as erro:
            messagebox.showwarning("Aviso", str(erro))
            return
        dialogo = DialogoRevisoes(self.winfo_toplevel(), self.anotacao["id"], versoes)
        self.wait_window(dialogo)
