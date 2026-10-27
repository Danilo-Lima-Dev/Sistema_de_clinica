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

Regras novas:
  * horário indisponível (fora do expediente ou bloqueado) não aceita agendamento (services/agenda.py);
  * paciente desativado não pode ser agendado;
  * a consulta nasce como 'Agendada' + 'Aguardando pagamento', com o valor da especialidade;
  * só vira 'Confirmada' depois que o pagamento é registrado como 'Pago' (conferido aqui e no banco).
"""
import sqlite3

import database
from services import agenda
from services.validacoes import (
    ErroValidacao,
    calcular_hora_fim,
    data_br_para_date,
    hora_valida,
    normalizar,
    validar_data_hora_futura,
)


def _validar(con, paciente_id, profissional_id, data_br, hora_inicio, observacoes="",
             ignorar_id_consulta=None, validar_futuro=True, checar_paciente_ativo=True):
    """Valida os campos de agendamento e checa agenda e conflito de horários (RN01, RN05)."""
    if not paciente_id:
        raise ErroValidacao("Selecione um paciente para a consulta.")
    paciente = con.execute("SELECT id, ativo FROM paciente WHERE id = ?", (paciente_id,)).fetchone()
    if not paciente:
        raise ErroValidacao("Paciente selecionado não foi encontrado no sistema.")
    if checar_paciente_ativo and not paciente["ativo"]:
        raise ErroValidacao(
            "Este paciente está desativado e não pode ser agendado. Reative o cadastro dele."
        )

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

    # Horário indisponível (fora do expediente, folga ou bloqueio) não aceita agendamento.
    motivo = agenda.motivo_indisponivel(con, profissional_id, data_iso, hora_inicio, hora_fim)
    if motivo:
        raise ErroValidacao(f"Horário indisponível: {motivo}. Escolha um horário disponível.")

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


def _valor_da_especialidade(con, profissional_id):
    linha = con.execute(
        "SELECT e.valor_consulta FROM profissional p "
        "JOIN especialidade e ON p.especialidade_id = e.id WHERE p.id = ?",
        (profissional_id,),
    ).fetchone()
    return linha["valor_consulta"] if linha else 0


def agendar(paciente_id, profissional_id, data_br, hora_inicio, observacoes="", validar_futuro=True):
    """Realiza o agendamento de uma nova consulta (RF05)."""
    try:
        with database.transacao() as con:
            dados = _validar(
                con, paciente_id, profissional_id, data_br, hora_inicio,
                observacoes=observacoes, validar_futuro=validar_futuro,
            )
            dados["situacao"] = "Agendada"
            # Nasce 'Aguardando pagamento', com o valor atual da especialidade do médico.
            dados["valor_centavos"] = _valor_da_especialidade(con, profissional_id)
            cursor = con.execute(
                "INSERT INTO consulta (paciente_id, profissional_id, data, hora_inicio, "
                "hora_fim, situacao, observacoes, valor_centavos, pagamento_status) "
                "VALUES (:paciente_id, :profissional_id, :data, :hora_inicio, "
                ":hora_fim, :situacao, :observacoes, :valor_centavos, 'Aguardando pagamento')",
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
            atual = con.execute(
                "SELECT situacao, paciente_id, profissional_id, pagamento_status "
                "FROM consulta WHERE id = ?", (id_consulta,),
            ).fetchone()
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
                # só barra paciente desativado se o paciente da consulta foi TROCADO
                checar_paciente_ativo=(paciente_id != atual["paciente_id"]),
            )
            dados["id"] = id_consulta
            con.execute(
                "UPDATE consulta SET paciente_id = :paciente_id, profissional_id = :profissional_id, "
                "data = :data, hora_inicio = :hora_inicio, hora_fim = :hora_fim, observacoes = :observacoes "
                "WHERE id = :id",
                dados,
            )
            # Trocou de médico e a consulta ainda não foi paga: usa o valor da nova especialidade.
            if profissional_id != atual["profissional_id"] and atual["pagamento_status"] != "Pago":
                con.execute(
                    "UPDATE consulta SET valor_centavos = ? WHERE id = ?",
                    (_valor_da_especialidade(con, profissional_id), id_consulta),
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


def confirmar(id_consulta):
    """Confirma a consulta. SÓ é permitido se o pagamento estiver registrado como 'Pago'.

    A regra vale aqui (back-end) e também no banco (gatilho `tg_confirmar_so_pago_update`),
    então não depende de a tela esconder ou desabilitar o botão.
    """
    with database.transacao() as con:
        atual = con.execute(
            "SELECT situacao, pagamento_status FROM consulta WHERE id = ?", (id_consulta,)
        ).fetchone()
        if not atual:
            raise ErroValidacao("Consulta não encontrada.")
        if atual["situacao"] == "Confirmada":
            raise ErroValidacao("Esta consulta já está confirmada.")
        if atual["situacao"] == "Cancelada":
            raise ErroValidacao("Uma consulta cancelada não pode ser confirmada.")
        if atual["situacao"] == "Realizada":
            raise ErroValidacao("Esta consulta já foi realizada.")
        if atual["pagamento_status"] != "Pago":
            raise ErroValidacao(
                "Não é possível confirmar: o pagamento ainda não foi registrado "
                "(Aguardando pagamento). O super usuário registra o pagamento no módulo Financeiro."
            )
        con.execute("UPDATE consulta SET situacao = 'Confirmada' WHERE id = ?", (id_consulta,))


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
               c.valor_centavos, c.pagamento_status, c.pago_em,
               p.nome AS paciente_nome, p.cpf AS paciente_cpf, p.telefone AS paciente_telefone,
               p.data_nascimento AS paciente_nascimento,
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
        # (sem_acento: ignora maiúsculas e acentos, "joao" encontra "João")
        condicoes = [
            "sem_acento(p.nome) LIKE ?", "sem_acento(pr.nome) LIKE ?",
            "sem_acento(e.nome) LIKE ?", "sem_acento(c.observacoes) LIKE ?",
        ]
        valores = [f"%{normalizar(busca)}%"] * 4
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
               c.valor_centavos, c.pagamento_status, c.pago_em,
               p.nome AS paciente_nome, p.cpf AS paciente_cpf, p.telefone AS paciente_telefone,
               p.data_nascimento AS paciente_nascimento,
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
