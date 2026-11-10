"""Histórico clínico por paciente: anotações do médico sobre as consultas.

Quem pode o quê (conferido no BACK-END, a tela só esconde o menu):
  * LER, ADICIONAR e ALTERAR: somente usuários com papel de MÉDICO. Atendente e
    Administrador não têm acesso.
  * ALTERAR uma anotação: só o médico que a escreveu. Os outros médicos podem ler.
  * Nada é apagado: toda alteração guarda o texto anterior em `historico_clinico_revisao`
    (data, hora e quem alterou), como exige a boa prática de registro clínico.

Uma anotação pertence a um paciente e, opcionalmente, a uma de suas consultas.
"""
from datetime import datetime

import database
from services import autenticacao
from services.autenticacao import PAPEL_MEDICO
from services.validacoes import ErroValidacao

MSG_SO_MEDICO = "Somente médicos podem acessar ou alterar o histórico clínico dos pacientes."
LIMITE_TEXTO = 5000
MINIMO_TEXTO = 3


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _exigir(executor_id):
    """Médico ativo (devolve os dados dele) ou ErroValidacao."""
    quem = autenticacao.exigir_papel(executor_id, PAPEL_MEDICO, mensagem=MSG_SO_MEDICO)
    with database.transacao() as con:
        nome = con.execute("SELECT nome FROM usuario WHERE id = ?", (executor_id,)).fetchone()["nome"]
    return {"id": quem["id"], "nome": nome, "profissional_id": quem["profissional_id"]}


def validar_texto(texto):
    """Texto da anotação limpo (sem espaços nas pontas). Levanta ErroValidacao se for inválido."""
    texto = (texto or "").strip()
    if not texto:
        raise ErroValidacao("Escreva a anotação do histórico clínico.")
    if len(texto) < MINIMO_TEXTO:
        raise ErroValidacao(f"A anotação deve ter pelo menos {MINIMO_TEXTO} caracteres.")
    if len(texto) > LIMITE_TEXTO:
        raise ErroValidacao(
            f"A anotação é longa demais ({len(texto)} caracteres; o máximo é {LIMITE_TEXTO})."
        )
    return texto


def listar(executor_id, paciente_id):
    """Anotações de UM paciente, da mais recente para a mais antiga (com a consulta, se houver)."""
    _exigir(executor_id)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT h.id, h.paciente_id, h.consulta_id, h.texto, h.autor_id, h.autor_nome, "
                "h.criado_em, h.atualizado_em, h.atualizado_por, "
                "c.data AS consulta_data, c.hora_inicio AS consulta_hora, "
                "pr.nome AS consulta_medico "
                "FROM historico_clinico h "
                "LEFT JOIN consulta c ON h.consulta_id = c.id "
                "LEFT JOIN profissional pr ON c.profissional_id = pr.id "
                "WHERE h.paciente_id = ? ORDER BY h.criado_em DESC, h.id DESC",
                (paciente_id,),
            )
        ]


def consultas_do_paciente(executor_id, paciente_id):
    """Consultas não canceladas do paciente (para ligar a anotação a uma consulta)."""
    _exigir(executor_id)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT c.id, c.data, c.hora_inicio, c.situacao, pr.nome AS medico "
                "FROM consulta c JOIN profissional pr ON c.profissional_id = pr.id "
                "WHERE c.paciente_id = ? AND c.situacao != 'Cancelada' "
                "ORDER BY c.data DESC, c.hora_inicio DESC",
                (paciente_id,),
            )
        ]


def adicionar(executor_id, paciente_id, texto, consulta_id=None):
    """Nova anotação no histórico do paciente. Devolve o id."""
    medico = _exigir(executor_id)
    texto = validar_texto(texto)
    with database.transacao() as con:
        if con.execute("SELECT 1 FROM paciente WHERE id = ?", (paciente_id,)).fetchone() is None:
            raise ErroValidacao("Paciente não encontrado. Escolha o paciente de novo.")
        if consulta_id:
            c = con.execute(
                "SELECT paciente_id, situacao FROM consulta WHERE id = ?", (consulta_id,)
            ).fetchone()
            if c is None:
                raise ErroValidacao("Consulta não encontrada.")
            if c["paciente_id"] != paciente_id:
                raise ErroValidacao("Essa consulta não pertence ao paciente escolhido.")
            if c["situacao"] == "Cancelada":
                raise ErroValidacao("Não é possível anotar em uma consulta cancelada.")
        else:
            consulta_id = None
        cursor = con.execute(
            "INSERT INTO historico_clinico (paciente_id, consulta_id, texto, autor_id, "
            "autor_nome, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
            (paciente_id, consulta_id, texto, medico["id"], medico["nome"], _agora()),
        )
        return cursor.lastrowid


def alterar(executor_id, id_anotacao, texto):
    """Altera uma anotação (só o médico que a escreveu). Devolve False se o texto não mudou."""
    medico = _exigir(executor_id)
    texto = validar_texto(texto)
    with database.transacao() as con:
        atual = con.execute(
            "SELECT texto, autor_id, autor_nome FROM historico_clinico WHERE id = ?",
            (id_anotacao,),
        ).fetchone()
        if atual is None:
            raise ErroValidacao("Anotação não encontrada. Atualize a lista e tente de novo.")
        if atual["autor_id"] != medico["id"]:
            raise ErroValidacao(
                f"Somente o médico que escreveu a anotação ({atual['autor_nome']}) pode alterá-la."
            )
        if atual["texto"] == texto:
            return False  # nada mudou: não cria revisão à toa
        agora = _agora()
        con.execute(
            "INSERT INTO historico_clinico_revisao (historico_id, texto_anterior, alterado_em, "
            "alterado_por) VALUES (?, ?, ?, ?)",
            (id_anotacao, atual["texto"], agora, medico["nome"]),
        )
        con.execute(
            "UPDATE historico_clinico SET texto = ?, atualizado_em = ?, atualizado_por = ? "
            "WHERE id = ?",
            (texto, agora, medico["nome"], id_anotacao),
        )
    return True


def revisoes(executor_id, id_anotacao):
    """Versões anteriores de uma anotação (da mais recente para a mais antiga)."""
    _exigir(executor_id)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT id, texto_anterior, alterado_em, alterado_por "
                "FROM historico_clinico_revisao WHERE historico_id = ? ORDER BY id DESC",
                (id_anotacao,),
            )
        ]
