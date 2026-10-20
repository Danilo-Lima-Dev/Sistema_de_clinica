"""Regras de negócio e acesso ao banco para agendamento de consultas.

Regras aplicadas (ver documento de requisitos):
  RF05  agendamento de consultas (paciente + profissional + data + horário)
  RF06  listagem e busca de consultas por paciente, profissional, data ou situação
  RF07  alteração dos dados de consulta agendada
  RF08  cancelamento de consulta agendada
  RF09  registrar consulta como realizada
  RN01  prevenção de conflito de horários para o mesmo profissional (consultas canceladas não bloqueiam)
  RN02  campos obrigatórios validados antes da gravação
  RN05  não agendar consultas em data e hora passadas
  RN07  consultas não são excluídas, mas canceladas para manter o histórico
"""
import sqlite3

import database
from services.validacoes import (
    ErroValidacao,
    calcular_hora_fim,
    data_br_para_date,
    hora_valida,
    validar_data_hora_futura,
)


def _validar(con, paciente_id, profissional_id, data_br, hora_inicio, observacoes="",
             ignorar_id_consulta=None, validar_futuro=True):
    """Valida os campos de agendamento e checa conflito de horários (RN01, RN05)."""
    if not paciente_id:
        raise ErroValidacao("Selecione um paciente para a consulta.")
    paciente = con.execute("SELECT id FROM paciente WHERE id = ?", (paciente_id,)).fetchone()
    if not paciente:
        raise ErroValidacao("Paciente selecionado não foi encontrado no sistema.")

    if not profissional_id:
        raise ErroValidacao("Selecione um profissional para a consulta.")
    profissional = con.execute("SELECT id, ativo FROM profissional WHERE id = ?", (profissional_id,)).fetchone()
    if not profissional:
        raise ErroValidacao("Profissional selecionado não foi encontrado no sistema.")
    if profissional["ativo"] == 0:
        raise ErroValidacao("Não é possível agendar consultas com profissionais inativos.")

    data_obj = data_br_para_date(data_br)
    data_iso = data_obj.isoformat()

    hora_inicio = (hora_inicio or "").strip()
    if not hora_valida(hora_inicio):
        raise ErroValidacao("Horário inválido. Digite no formato HH:MM (ex.: 09:30).")

    if validar_futuro:
        validar_data_hora_futura(data_br, hora_inicio)

    hora_fim = calcular_hora_fim(hora_inicio, 30)

    # RN01: Prevenção de conflito de horários para o mesmo profissional.
    # Consultas com situação 'Cancelada' não bloqueiam o horário.
    sql_conflito = """
        SELECT COUNT(*) FROM consulta
        WHERE profissional_id = ?
          AND data = ?
          AND hora_inicio < ?
          AND hora_fim > ?
          AND situacao != 'Cancelada'
    """
    parametros = [profissional_id, data_iso, hora_fim, hora_inicio]
    if ignorar_id_consulta is not None:
        sql_conflito += " AND id != ?"
        parametros.append(ignorar_id_consulta)

    total_conflitos = con.execute(sql_conflito, parametros).fetchone()[0]
    if total_conflitos > 0:
        raise ErroValidacao(MSG_CONFLITO)

    return {
        "paciente_id": paciente_id,
        "profissional_id": profissional_id,
        "data": data_iso,
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "observacoes": (observacoes or "").strip() or None,
    }


MSG_CONFLITO = "O profissional já possui uma consulta ativa agendada neste mesmo dia e horário."


def _erro_de_conflito(erro):
    """Se o banco recusou por causa do índice único de horário (RN01), devolve a mensagem amigável."""
    if "UNIQUE" in str(erro).upper():
        return ErroValidacao(MSG_CONFLITO)
    return None


def agendar(paciente_id, profissional_id, data_br, hora_inicio, observacoes="", validar_futuro=True):
    """Realiza o agendamento de uma nova consulta (RF05)."""
    try:
        with database.transacao() as con:
            dados = _validar(
                con, paciente_id, profissional_id, data_br, hora_inicio,
                observacoes=observacoes, validar_futuro=validar_futuro,
            )
            dados["situacao"] = "Agendada"
            cursor = con.execute(
                "INSERT INTO consulta (paciente_id, profissional_id, data, hora_inicio, "
                "hora_fim, situacao, observacoes) "
                "VALUES (:paciente_id, :profissional_id, :data, :hora_inicio, "
                ":hora_fim, :situacao, :observacoes)",
                dados,
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError as erro:
        amigavel = _erro_de_conflito(erro)
        if amigavel:
            raise amigavel from None
        raise


def alterar_dados(id_consulta, paciente_id, profissional_id, data_br, hora_inicio,
                  observacoes="", validar_futuro=True):
    """Altera dados de uma consulta agendada (remarcar, trocar paciente ou médico) (RF07)."""
    try:
        with database.transacao() as con:
            atual = con.execute("SELECT situacao FROM consulta WHERE id = ?", (id_consulta,)).fetchone()
            if not atual:
                raise ErroValidacao("Consulta não encontrada. Atualize a lista e tente de novo.")
            if atual["situacao"] == "Cancelada":
                raise ErroValidacao("Consultas canceladas não podem ser alteradas. Faça um novo agendamento.")
            if atual["situacao"] == "Realizada":
                raise ErroValidacao("Consultas já realizadas não podem ser alteradas.")

            dados = _validar(
                con, paciente_id, profissional_id, data_br, hora_inicio,
                observacoes=observacoes, ignorar_id_consulta=id_consulta,
                validar_futuro=validar_futuro,
            )
            dados["id"] = id_consulta
            con.execute(
                "UPDATE consulta SET paciente_id = :paciente_id, profissional_id = :profissional_id, "
                "data = :data, hora_inicio = :hora_inicio, hora_fim = :hora_fim, observacoes = :observacoes "
                "WHERE id = :id",
                dados,
            )
    except sqlite3.IntegrityError as erro:
        amigavel = _erro_de_conflito(erro)
        if amigavel:
            raise amigavel from None
        raise


def cancelar(id_consulta, motivo_cancelamento=""):
    """Cancela uma consulta agendada, preservando o histórico (RN07 / RF08)."""
    with database.transacao() as con:
        atual = con.execute("SELECT situacao FROM consulta WHERE id = ?", (id_consulta,)).fetchone()
        if not atual:
            raise ErroValidacao("Consulta não encontrada.")
        if atual["situacao"] == "Cancelada":
            raise ErroValidacao("Esta consulta já está cancelada.")
        if atual["situacao"] == "Realizada":
            raise ErroValidacao("Uma consulta já realizada não pode ser cancelada.")

        motivo = (motivo_cancelamento or "").strip() or None
        con.execute(
            "UPDATE consulta SET situacao = 'Cancelada', motivo_cancelamento = ? WHERE id = ?",
            (motivo, id_consulta),
        )


def marcar_realizada(id_consulta):
    """Marca uma consulta agendada como realizada (RF09)."""
    with database.transacao() as con:
        atual = con.execute("SELECT situacao FROM consulta WHERE id = ?", (id_consulta,)).fetchone()
        if not atual:
            raise ErroValidacao("Consulta não encontrada.")
        if atual["situacao"] == "Cancelada":
            raise ErroValidacao("Uma consulta cancelada não pode ser marcada como realizada.")
        if atual["situacao"] == "Realizada":
            raise ErroValidacao("Esta consulta já foi registrada como realizada.")

        con.execute(
            "UPDATE consulta SET situacao = 'Realizada' WHERE id = ?",
            (id_consulta,),
        )


def listar(busca="", situacao=None, data_iso=None, profissional_id=None, paciente_id=None):
    """Lista as consultas cadastradas com os dados do paciente e do médico (RF06)."""
    busca = (busca or "").strip()
    sql = """
        SELECT c.id, c.paciente_id, c.profissional_id, c.data, c.hora_inicio, c.hora_fim,
               c.situacao, c.motivo_cancelamento, c.observacoes,
               p.nome AS paciente_nome, p.cpf AS paciente_cpf, p.telefone AS paciente_telefone,
               pr.nome AS profissional_nome, pr.registro AS profissional_registro,
               e.nome AS especialidade_nome
        FROM consulta c
        JOIN paciente p ON c.paciente_id = p.id
        JOIN profissional pr ON c.profissional_id = pr.id
        JOIN especialidade e ON pr.especialidade_id = e.id
    """
    filtros = []
    parametros = []

    if busca:
        # RF06: a busca vale para paciente, profissional, especialidade e observações...
        condicoes = ["p.nome LIKE ?", "pr.nome LIKE ?", "e.nome LIKE ?", "c.observacoes LIKE ?"]
        valores = [f"%{busca}%"] * 4
        # ...e também para a data, quando o texto digitado for uma data DD/MM/AAAA válida.
        try:
            condicoes.append("c.data = ?")
            valores.append(data_br_para_date(busca).isoformat())
        except ErroValidacao:
            condicoes.pop()  # não era uma data: busca só pelos textos
        filtros.append("(" + " OR ".join(condicoes) + ")")
        parametros.extend(valores)

    if situacao and situacao != "Todas":
        filtros.append("c.situacao = ?")
        parametros.append(situacao)

    if data_iso:
        filtros.append("c.data = ?")
        parametros.append(data_iso)

    if profissional_id:
        filtros.append("c.profissional_id = ?")
        parametros.append(profissional_id)

    if paciente_id:
        filtros.append("c.paciente_id = ?")
        parametros.append(paciente_id)

    if filtros:
        sql += " WHERE " + " AND ".join(filtros)

    sql += " ORDER BY c.data DESC, c.hora_inicio DESC"

    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]


def obter(id_consulta):
    """Retorna os dados completos de uma consulta."""
    sql = """
        SELECT c.id, c.paciente_id, c.profissional_id, c.data, c.hora_inicio, c.hora_fim,
               c.situacao, c.motivo_cancelamento, c.observacoes,
               p.nome AS paciente_nome, p.cpf AS paciente_cpf, p.telefone AS paciente_telefone,
               pr.nome AS profissional_nome, pr.registro AS profissional_registro,
               e.nome AS especialidade_nome
        FROM consulta c
        JOIN paciente p ON c.paciente_id = p.id
        JOIN profissional pr ON c.profissional_id = pr.id
        JOIN especialidade e ON pr.especialidade_id = e.id
        WHERE c.id = ?
    """
    with database.transacao() as con:
        linha = con.execute(sql, (id_consulta,)).fetchone()
        return dict(linha) if linha else None
