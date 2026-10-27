"""Módulo financeiro: valores, pagamentos e histórico (SOMENTE super usuário).

Toda função daqui recebe o `executor_id` (id do usuário logado) e confere NO BANCO se ele
é um super usuário ativo. Esconder o menu na tela não basta: sem esta conferência, qualquer
código que chamasse o serviço conseguiria alterar valores ou registrar pagamentos.

Regras:
  * O valor da consulta nasce da especialidade (copiado ao agendar). Mudar o valor da
    especialidade vale só para os próximos agendamentos; o valor de cada consulta pode ser
    ajustado à parte.
  * Pagamento: 'Aguardando pagamento' (padrão) ou 'Pago'. Consulta cancelada não recebe pagamento.
  * Todo ajuste de valor e de pagamento grava no histórico quem fez e quando.
  * Painel: "recebido" soma as consultas pagas; "pendente" soma as que aguardam pagamento,
    sem contar as canceladas.
"""
from datetime import datetime

import database
from services import autenticacao
from services.validacoes import ErroValidacao, VALOR_MAXIMO_CENTAVOS, brl

AGUARDANDO = "Aguardando pagamento"
PAGO = "Pago"

MSG_SO_SUPER = "Somente o super usuário pode acessar o financeiro."


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _exigir(executor_id):
    """Confere a permissão e devolve (id, nome do usuário) para o histórico."""
    autenticacao.exigir_superusuario(executor_id, MSG_SO_SUPER)
    with database.transacao() as con:
        linha = con.execute(
            "SELECT id, nome, login FROM usuario WHERE id = ?", (executor_id,)
        ).fetchone()
    return linha["id"], f"{linha['nome']} (@{linha['login']})"


def _validar_valor(valor_centavos):
    if not isinstance(valor_centavos, int) or isinstance(valor_centavos, bool):
        raise ErroValidacao("Valor inválido.")
    if valor_centavos < 0:
        raise ErroValidacao("O valor não pode ser negativo.")
    if valor_centavos > VALOR_MAXIMO_CENTAVOS:
        raise ErroValidacao("Valor muito alto. Confira o valor digitado.")


def _historico(con, usuario, tipo, descricao, consulta_id=None, especialidade_id=None,
               valor_antigo=None, valor_novo=None):
    usuario_id, usuario_nome = usuario
    con.execute(
        "INSERT INTO financeiro_historico (data_hora, usuario_id, usuario_nome, tipo, "
        "consulta_id, especialidade_id, descricao, valor_antigo, valor_novo) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (_agora(), usuario_id, usuario_nome, tipo, consulta_id, especialidade_id,
         descricao, valor_antigo, valor_novo),
    )


# ------------------------------------------------------------------ valores
def alterar_valor_especialidade(executor_id, especialidade_id, valor_centavos):
    """Define o valor da consulta de uma especialidade (vale para os próximos agendamentos)."""
    usuario = _exigir(executor_id)
    _validar_valor(valor_centavos)
    with database.transacao() as con:
        esp = con.execute(
            "SELECT nome, valor_consulta FROM especialidade WHERE id = ?", (especialidade_id,)
        ).fetchone()
        if esp is None:
            raise ErroValidacao("Especialidade não encontrada.")
        if esp["valor_consulta"] == valor_centavos:
            return False  # nada mudou: não polui o histórico
        con.execute(
            "UPDATE especialidade SET valor_consulta = ? WHERE id = ?",
            (valor_centavos, especialidade_id),
        )
        _historico(
            con, usuario, "valor_especialidade",
            f"Valor da especialidade {esp['nome']}: {brl(esp['valor_consulta'])} → {brl(valor_centavos)}",
            especialidade_id=especialidade_id,
            valor_antigo=esp["valor_consulta"], valor_novo=valor_centavos,
        )
    return True


def alterar_valor_consulta(executor_id, consulta_id, valor_centavos):
    """Ajusta o valor de UMA consulta (consulta paga ou cancelada não pode mudar de valor)."""
    usuario = _exigir(executor_id)
    _validar_valor(valor_centavos)
    with database.transacao() as con:
        c = con.execute(
            "SELECT valor_centavos, pagamento_status, situacao FROM consulta WHERE id = ?",
            (consulta_id,),
        ).fetchone()
        if c is None:
            raise ErroValidacao("Consulta não encontrada.")
        if c["situacao"] == "Cancelada":
            raise ErroValidacao("Consulta cancelada não pode ter o valor alterado.")
        if c["pagamento_status"] == PAGO:
            raise ErroValidacao("Consulta já paga: desfaça o pagamento antes de alterar o valor.")
        if c["valor_centavos"] == valor_centavos:
            return False
        con.execute(
            "UPDATE consulta SET valor_centavos = ? WHERE id = ?", (valor_centavos, consulta_id)
        )
        _historico(
            con, usuario, "valor_consulta",
            f"Valor da consulta #{consulta_id}: {brl(c['valor_centavos'])} → {brl(valor_centavos)}",
            consulta_id=consulta_id,
            valor_antigo=c["valor_centavos"], valor_novo=valor_centavos,
        )
    return True


# ---------------------------------------------------------------- pagamento
def registrar_pagamento(executor_id, consulta_id):
    """Marca a consulta como paga (libera a confirmação)."""
    usuario = _exigir(executor_id)
    with database.transacao() as con:
        c = con.execute(
            "SELECT valor_centavos, pagamento_status, situacao FROM consulta WHERE id = ?",
            (consulta_id,),
        ).fetchone()
        if c is None:
            raise ErroValidacao("Consulta não encontrada.")
        if c["situacao"] == "Cancelada":
            raise ErroValidacao("Consulta cancelada não recebe pagamento.")
        if c["pagamento_status"] == PAGO:
            raise ErroValidacao("Esta consulta já está registrada como paga.")
        con.execute(
            "UPDATE consulta SET pagamento_status = ?, pago_em = ? WHERE id = ?",
            (PAGO, _agora(), consulta_id),
        )
        _historico(
            con, usuario, "pagamento",
            f"Pagamento registrado na consulta #{consulta_id} ({brl(c['valor_centavos'])})",
            consulta_id=consulta_id, valor_novo=c["valor_centavos"],
        )


def desfazer_pagamento(executor_id, consulta_id):
    """Volta a consulta para 'Aguardando pagamento' (só antes de confirmar)."""
    usuario = _exigir(executor_id)
    with database.transacao() as con:
        c = con.execute(
            "SELECT valor_centavos, pagamento_status, situacao FROM consulta WHERE id = ?",
            (consulta_id,),
        ).fetchone()
        if c is None:
            raise ErroValidacao("Consulta não encontrada.")
        if c["pagamento_status"] != PAGO:
            raise ErroValidacao("Esta consulta não está registrada como paga.")
        if c["situacao"] in ("Confirmada", "Realizada"):
            raise ErroValidacao(
                f"Consulta {c['situacao'].lower()}: o pagamento não pode ser desfeito."
            )
        con.execute(
            "UPDATE consulta SET pagamento_status = ?, pago_em = NULL WHERE id = ?",
            (AGUARDANDO, consulta_id),
        )
        _historico(
            con, usuario, "pagamento",
            f"Pagamento desfeito na consulta #{consulta_id} ({brl(c['valor_centavos'])})",
            consulta_id=consulta_id, valor_antigo=c["valor_centavos"],
        )


# ----------------------------------------------------------- painel e listas
def _filtros(data_inicio_iso, data_fim_iso, profissional_id, especialidade_id, pagamento):
    filtros, parametros = [], []
    if data_inicio_iso:
        filtros.append("c.data >= ?")
        parametros.append(data_inicio_iso)
    if data_fim_iso:
        filtros.append("c.data <= ?")
        parametros.append(data_fim_iso)
    if profissional_id:
        filtros.append("c.profissional_id = ?")
        parametros.append(profissional_id)
    if especialidade_id:
        filtros.append("pr.especialidade_id = ?")
        parametros.append(especialidade_id)
    if pagamento in (AGUARDANDO, PAGO):
        filtros.append("c.pagamento_status = ?")
        parametros.append(pagamento)
    return filtros, parametros


_SQL_BASE = """
    FROM consulta c
    JOIN paciente p ON c.paciente_id = p.id
    JOIN profissional pr ON c.profissional_id = pr.id
    JOIN especialidade e ON pr.especialidade_id = e.id
"""


def listar_consultas(executor_id, data_inicio_iso=None, data_fim_iso=None,
                     profissional_id=None, especialidade_id=None, pagamento=None):
    """Consultas com valor e status de pagamento, filtradas por período, médico e especialidade."""
    _exigir(executor_id)
    filtros, parametros = _filtros(
        data_inicio_iso, data_fim_iso, profissional_id, especialidade_id, pagamento
    )
    sql = (
        "SELECT c.id, c.data, c.hora_inicio, c.situacao, c.valor_centavos, c.pagamento_status, "
        "c.pago_em, p.nome AS paciente_nome, pr.nome AS profissional_nome, "
        "e.nome AS especialidade_nome " + _SQL_BASE
    )
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY c.data DESC, c.hora_inicio DESC"
    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]


def resumo(executor_id, data_inicio_iso=None, data_fim_iso=None,
           profissional_id=None, especialidade_id=None):
    """Totais do painel: recebido e pendente (em centavos) e quantidade de consultas de cada um."""
    _exigir(executor_id)
    filtros, parametros = _filtros(
        data_inicio_iso, data_fim_iso, profissional_id, especialidade_id, None
    )
    sql = (
        "SELECT "
        "COALESCE(SUM(CASE WHEN c.pagamento_status = 'Pago' THEN c.valor_centavos END), 0) AS recebido, "
        "COALESCE(SUM(CASE WHEN c.pagamento_status != 'Pago' AND c.situacao != 'Cancelada' "
        "THEN c.valor_centavos END), 0) AS pendente, "
        "COALESCE(SUM(CASE WHEN c.pagamento_status = 'Pago' THEN 1 END), 0) AS qtd_pagas, "
        "COALESCE(SUM(CASE WHEN c.pagamento_status != 'Pago' AND c.situacao != 'Cancelada' "
        "THEN 1 END), 0) AS qtd_pendentes " + _SQL_BASE
    )
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    with database.transacao() as con:
        return dict(con.execute(sql, parametros).fetchone())


def historico(executor_id, limite=300):
    """Histórico de alterações de valor e de pagamento (mais recentes primeiro)."""
    _exigir(executor_id)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT id, data_hora, usuario_nome, tipo, descricao, consulta_id, especialidade_id "
                "FROM financeiro_historico ORDER BY id DESC LIMIT ?", (limite,)
            )
        ]
