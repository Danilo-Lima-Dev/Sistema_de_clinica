"""Histórico clínico do paciente (prontuário de atendimento), um registro por consulta.

Cada registro guarda a queixa/anamnese, o diagnóstico e a conduta de UMA consulta.

Quem pode o quê (conferido aqui, no back-end, com `autenticacao.exigir_papel`):
  - VER o histórico: SOMENTE o Médico. Ele vê todos os registros do paciente (de qualquer
    médico), para ter a continuidade do atendimento. Administrador e Atendente não acessam.
  - REGISTRAR: somente o Médico da consulta, em consulta dele, não cancelada e que já chegou
    (data da consulta até hoje).
  - ALTERAR: somente o Médico que fez o registro (o médico da consulta).
  - Nada é apagado: a cada alteração, a versão anterior é guardada em
    `historico_clinico_versao` (quem substituiu e quando).
"""
from datetime import date, datetime

import database
from services import autenticacao
from services.autenticacao import PAPEL_MEDICO
from services.validacoes import ErroValidacao, exigir_alteracao, validar_texto_livre

MAXIMO_CARACTERES = 4000
CAMPOS = ("queixa", "diagnostico", "conduta")

MSG_SO_MEDICO = "Somente o médico tem acesso ao histórico clínico dos pacientes."
MSG_SO_AUTOR = "Somente o médico que atendeu a consulta pode alterar este registro."
MSG_CONSULTA_DE_OUTRO = "O médico só registra o histórico das suas próprias consultas."


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _medico(executor_id):
    """Confere no banco que quem pede é um Médico ativo e ligado a um profissional."""
    quem = autenticacao.exigir_papel(executor_id, PAPEL_MEDICO, mensagem=MSG_SO_MEDICO)
    if not quem["profissional_id"]:
        raise ErroValidacao("Este usuário médico não está ligado a um profissional.")
    return quem


def _validar_campos(queixa, diagnostico, conduta):
    """Limpa os três textos; pelo menos um deve ser preenchido."""
    dados = {
        "queixa": validar_texto_livre(queixa, "queixa / anamnese", MAXIMO_CARACTERES),
        "diagnostico": validar_texto_livre(diagnostico, "diagnóstico", MAXIMO_CARACTERES),
        "conduta": validar_texto_livre(conduta, "conduta / evolução", MAXIMO_CARACTERES),
    }
    if not any(dados.values()):
        raise ErroValidacao("Preencha pelo menos um campo: queixa, diagnóstico ou conduta.")
    return {chave: valor or None for chave, valor in dados.items()}


_SELECT = """
    SELECT h.id, h.paciente_id, h.consulta_id, h.profissional_id,
           h.queixa, h.diagnostico, h.conduta,
           h.criado_em, h.alterado_em,
           c.data AS data_consulta, c.hora_inicio,
           pr.nome AS medico_nome, pr.registro AS medico_registro,
           e.nome AS especialidade_nome,
           (SELECT COUNT(*) FROM historico_clinico_versao v WHERE v.historico_id = h.id) AS versoes
    FROM historico_clinico h
    JOIN consulta c ON c.id = h.consulta_id
    JOIN profissional pr ON pr.id = h.profissional_id
    JOIN especialidade e ON e.id = pr.especialidade_id
"""


def _com_permissao(linha, quem):
    registro = dict(linha)
    registro["pode_alterar"] = registro["profissional_id"] == quem["profissional_id"]
    return registro


# ------------------------------------------------------------------ consultar
def listar(executor_id, paciente_id):
    """Histórico do paciente (consultas mais recentes primeiro). Só o Médico."""
    quem = _medico(executor_id)
    with database.transacao() as con:
        linhas = con.execute(
            _SELECT + " WHERE h.paciente_id = ? ORDER BY c.data DESC, c.hora_inicio DESC",
            (paciente_id,),
        ).fetchall()
    return [_com_permissao(linha, quem) for linha in linhas]


def obter(executor_id, id_historico):
    """Um registro completo do histórico. Só o Médico."""
    quem = _medico(executor_id)
    with database.transacao() as con:
        linha = con.execute(_SELECT + " WHERE h.id = ?", (id_historico,)).fetchone()
    if linha is None:
        raise ErroValidacao("Registro do histórico não encontrado.")
    return _com_permissao(linha, quem)


def listar_versoes(executor_id, id_historico):
    """Versões anteriores de um registro (mais recentes primeiro). Só o Médico."""
    _medico(executor_id)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT v.id, v.queixa, v.diagnostico, v.conduta, v.substituido_em, "
                "u.nome AS substituido_por FROM historico_clinico_versao v "
                "LEFT JOIN usuario u ON u.id = v.substituido_por_id "
                "WHERE v.historico_id = ? ORDER BY v.id DESC",
                (id_historico,),
            )
        ]


def consultas_para_registrar(executor_id, paciente_id):
    """Consultas DESTE médico com o paciente que ainda não têm registro (e já chegaram)."""
    quem = _medico(executor_id)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT c.id, c.data, c.hora_inicio, c.situacao FROM consulta c "
                "WHERE c.paciente_id = ? AND c.profissional_id = ? "
                "AND c.situacao != 'Cancelada' AND c.data <= ? "
                "AND NOT EXISTS (SELECT 1 FROM historico_clinico h WHERE h.consulta_id = c.id) "
                "ORDER BY c.data DESC, c.hora_inicio DESC",
                (paciente_id, quem["profissional_id"], date.today().isoformat()),
            )
        ]


# ------------------------------------------------------------------ gravar
def registrar(executor_id, id_consulta, queixa="", diagnostico="", conduta=""):
    """Cria o registro clínico de uma consulta do próprio médico. Devolve o id."""
    quem = _medico(executor_id)
    dados = _validar_campos(queixa, diagnostico, conduta)
    with database.transacao() as con:
        c = con.execute(
            "SELECT paciente_id, profissional_id, situacao, data FROM consulta WHERE id = ?",
            (id_consulta,),
        ).fetchone()
        if c is None:
            raise ErroValidacao("Consulta não encontrada.")
        if c["profissional_id"] != quem["profissional_id"]:
            raise ErroValidacao(MSG_CONSULTA_DE_OUTRO)
        if c["situacao"] == "Cancelada":
            raise ErroValidacao("Não é possível registrar histórico de uma consulta cancelada.")
        if c["data"] > date.today().isoformat():
            raise ErroValidacao("Esta consulta ainda não aconteceu. Registre no dia do atendimento.")
        if con.execute(
            "SELECT 1 FROM historico_clinico WHERE consulta_id = ?", (id_consulta,)
        ).fetchone():
            raise ErroValidacao("Esta consulta já tem registro no histórico. Selecione-o para alterar.")
        cursor = con.execute(
            "INSERT INTO historico_clinico (paciente_id, consulta_id, profissional_id, queixa, "
            "diagnostico, conduta, criado_em, criado_por_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (c["paciente_id"], id_consulta, c["profissional_id"], dados["queixa"],
             dados["diagnostico"], dados["conduta"], _agora(), quem["id"]),
        )
        return cursor.lastrowid


def alterar(executor_id, id_historico, queixa="", diagnostico="", conduta=""):
    """Altera um registro. Só o médico da consulta; a versão anterior fica guardada."""
    quem = _medico(executor_id)
    dados = _validar_campos(queixa, diagnostico, conduta)
    with database.transacao() as con:
        atual = con.execute(
            "SELECT * FROM historico_clinico WHERE id = ?", (id_historico,)
        ).fetchone()
        if atual is None:
            raise ErroValidacao("Registro do histórico não encontrado.")
        if atual["profissional_id"] != quem["profissional_id"]:
            raise ErroValidacao(MSG_SO_AUTOR)
        exigir_alteracao(dict(atual), dados, CAMPOS)
        agora = _agora()
        con.execute(
            "INSERT INTO historico_clinico_versao (historico_id, queixa, diagnostico, conduta, "
            "substituido_em, substituido_por_id) VALUES (?, ?, ?, ?, ?, ?)",
            (id_historico, atual["queixa"], atual["diagnostico"], atual["conduta"],
             agora, quem["id"]),
        )
        con.execute(
            "UPDATE historico_clinico SET queixa = ?, diagnostico = ?, conduta = ?, "
            "alterado_em = ?, alterado_por_id = ? WHERE id = ?",
            (dados["queixa"], dados["diagnostico"], dados["conduta"], agora, quem["id"],
             id_historico),
        )
