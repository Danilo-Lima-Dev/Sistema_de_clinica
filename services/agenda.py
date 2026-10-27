"""Agenda do médico: horários disponíveis, reservados e indisponíveis.

Cada horário tem 30 minutos e pertence sempre a UM médico. Os três estados são:

  * disponível   - dentro do expediente, sem consulta e sem bloqueio: pode ser agendado;
  * reservado    - já existe uma consulta ativa (não cancelada) nesse horário;
  * indisponível - não aceita agendamento: fora do expediente, folga/bloqueio cadastrado
                   ou (opcionalmente) horário que já passou.

PARA MUDAR O EXPEDIENTE, altere as constantes logo abaixo (valem para todos os médicos).
Folgas e bloqueios de um médico específico ficam na tabela `bloqueio_agenda`.
"""
from datetime import date, datetime

import database
from services.validacoes import ErroValidacao, calcular_hora_fim

# ---- expediente da clínica (EDITE AQUI) -------------------------------------
EXPEDIENTE_INICIO = "08:00"
EXPEDIENTE_FIM = "18:00"
PASSO_MINUTOS = 30
DIAS_ATENDIMENTO = (0, 1, 2, 3, 4)  # 0 = segunda ... 6 = domingo (aqui: segunda a sexta)

DISPONIVEL = "disponivel"
RESERVADO = "reservado"
INDISPONIVEL = "indisponivel"

NOMES_ESTADO = {DISPONIVEL: "Disponível", RESERVADO: "Reservado", INDISPONIVEL: "Indisponível"}


def _minutos(hora):
    h, m = map(int, hora.split(":"))
    return h * 60 + m


def _hora(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def horas_do_expediente():
    """Lista de (hora_inicio, hora_fim) de cada horário do expediente."""
    fim = _minutos(EXPEDIENTE_FIM)
    atual = _minutos(EXPEDIENTE_INICIO)
    horarios = []
    while atual + PASSO_MINUTOS <= fim:
        horarios.append((_hora(atual), _hora(atual + PASSO_MINUTOS)))
        atual += PASSO_MINUTOS
    return horarios


def _para_data(data):
    """Aceita date ou 'AAAA-MM-DD'."""
    if isinstance(data, date):
        return data
    try:
        return date.fromisoformat(data)
    except (TypeError, ValueError):
        raise ErroValidacao("Data inválida.") from None


def _dentro_do_expediente(data, hora_inicio, hora_fim):
    if data.weekday() not in DIAS_ATENDIMENTO:
        return False
    return _minutos(hora_inicio) >= _minutos(EXPEDIENTE_INICIO) and \
        _minutos(hora_fim) <= _minutos(EXPEDIENTE_FIM)


def motivo_indisponivel(con, profissional_id, data_iso, hora_inicio, hora_fim):
    """Texto do motivo se o horário NÃO aceita agendamento (fora do expediente ou bloqueado)."""
    data = _para_data(data_iso)
    if not _dentro_do_expediente(data, hora_inicio, hora_fim):
        return "fora do expediente do médico"
    bloqueio = con.execute(
        "SELECT motivo FROM bloqueio_agenda WHERE profissional_id = ? AND data = ? "
        "AND hora_inicio < ? AND hora_fim > ?",
        (profissional_id, data.isoformat(), hora_fim, hora_inicio),
    ).fetchone()
    if bloqueio:
        return bloqueio["motivo"] or "horário bloqueado (folga ou bloqueio)"
    return None


def horarios_do_dia(profissional_id, data, considerar_passado=False):
    """Os horários do médico no dia, cada um com seu estado.

    Devolve uma lista de dicionários: hora_inicio, hora_fim, estado, motivo, consulta_id
    e bloqueio_id (preenchido quando o horário está indisponível por bloqueio cadastrado).
    Com `considerar_passado=True`, horários que já passaram contam como indisponíveis.
    """
    data = _para_data(data)
    agora = datetime.now()
    with database.transacao() as con:
        consultas_ativas = con.execute(
            "SELECT id, hora_inicio, hora_fim FROM consulta WHERE profissional_id = ? "
            "AND data = ? AND situacao != 'Cancelada'",
            (profissional_id, data.isoformat()),
        ).fetchall()
        bloqueios = con.execute(
            "SELECT id, hora_inicio, hora_fim, motivo FROM bloqueio_agenda "
            "WHERE profissional_id = ? AND data = ?",
            (profissional_id, data.isoformat()),
        ).fetchall()

    resultado = []
    for inicio, fim in horas_do_expediente():
        item = {
            "hora_inicio": inicio, "hora_fim": fim, "estado": DISPONIVEL,
            "motivo": "", "consulta_id": None, "bloqueio_id": None,
        }
        consulta = next(
            (c for c in consultas_ativas if c["hora_inicio"] < fim and c["hora_fim"] > inicio), None
        )
        bloqueio = next(
            (b for b in bloqueios if b["hora_inicio"] < fim and b["hora_fim"] > inicio), None
        )
        if data.weekday() not in DIAS_ATENDIMENTO:
            item.update(estado=INDISPONIVEL, motivo="Fora do expediente (dia sem atendimento)")
        elif consulta:
            item.update(estado=RESERVADO, motivo="Já existe uma consulta neste horário",
                        consulta_id=consulta["id"])
        elif bloqueio:
            item.update(estado=INDISPONIVEL, motivo=bloqueio["motivo"] or "Horário bloqueado",
                        bloqueio_id=bloqueio["id"])
        elif considerar_passado and datetime.combine(data, datetime.min.time()).replace(
            hour=int(inicio[:2]), minute=int(inicio[3:])
        ) < agora:
            item.update(estado=INDISPONIVEL, motivo="Horário que já passou")
        resultado.append(item)
    return resultado


def horarios_disponiveis(profissional_id, data, considerar_passado=True):
    """Só os horários livres do dia (os que podem ser escolhidos no agendamento)."""
    return [
        h for h in horarios_do_dia(profissional_id, data, considerar_passado)
        if h["estado"] == DISPONIVEL
    ]


# ---------------------------------------------------------------- bloqueios
def _exigir_profissional(con, profissional_id):
    if not profissional_id or not con.execute(
        "SELECT 1 FROM profissional WHERE id = ?", (profissional_id,)
    ).fetchone():
        raise ErroValidacao("Selecione um médico.")


def bloquear_horario(profissional_id, data, hora_inicio, motivo=""):
    """Marca um horário do médico como indisponível (folga, reunião, etc.)."""
    data = _para_data(data)
    hora_fim = calcular_hora_fim(hora_inicio, PASSO_MINUTOS)
    motivo = (motivo or "").strip() or None
    with database.transacao() as con:
        _exigir_profissional(con, profissional_id)
        if not _dentro_do_expediente(data, hora_inicio, hora_fim):
            raise ErroValidacao("Este horário já está fora do expediente do médico.")
        if con.execute(
            "SELECT 1 FROM consulta WHERE profissional_id = ? AND data = ? "
            "AND situacao != 'Cancelada' AND hora_inicio < ? AND hora_fim > ?",
            (profissional_id, data.isoformat(), hora_fim, hora_inicio),
        ).fetchone():
            raise ErroValidacao(
                "Este horário está reservado por uma consulta. Cancele a consulta antes de bloqueá-lo."
            )
        existente = con.execute(
            "SELECT 1 FROM bloqueio_agenda WHERE profissional_id = ? AND data = ? AND hora_inicio = ?",
            (profissional_id, data.isoformat(), hora_inicio),
        ).fetchone()
        if existente:
            raise ErroValidacao("Este horário já está indisponível.")
        con.execute(
            "INSERT INTO bloqueio_agenda (profissional_id, data, hora_inicio, hora_fim, motivo) "
            "VALUES (?, ?, ?, ?, ?)",
            (profissional_id, data.isoformat(), hora_inicio, hora_fim, motivo),
        )


def liberar_horario(profissional_id, data, hora_inicio):
    """Remove o bloqueio de um horário (volta a ficar disponível)."""
    data = _para_data(data)
    with database.transacao() as con:
        cursor = con.execute(
            "DELETE FROM bloqueio_agenda WHERE profissional_id = ? AND data = ? AND hora_inicio = ?",
            (profissional_id, data.isoformat(), hora_inicio),
        )
        if cursor.rowcount == 0:
            raise ErroValidacao("Este horário não tem bloqueio para ser liberado.")


def bloquear_dia(profissional_id, data, motivo=""):
    """Bloqueia todos os horários livres do dia (folga). Devolve (bloqueados, mantidos)."""
    data = _para_data(data)
    if data.weekday() not in DIAS_ATENDIMENTO:
        raise ErroValidacao("Este dia já está fora do expediente do médico.")
    bloqueados = mantidos = 0
    for item in horarios_do_dia(profissional_id, data):
        if item["estado"] == DISPONIVEL:
            bloquear_horario(profissional_id, data, item["hora_inicio"], motivo or "Folga")
            bloqueados += 1
        elif item["estado"] == RESERVADO:
            mantidos += 1
    return bloqueados, mantidos


def liberar_dia(profissional_id, data):
    """Remove todos os bloqueios do dia. Devolve quantos horários foram liberados."""
    data = _para_data(data)
    with database.transacao() as con:
        _exigir_profissional(con, profissional_id)
        cursor = con.execute(
            "DELETE FROM bloqueio_agenda WHERE profissional_id = ? AND data = ?",
            (profissional_id, data.isoformat()),
        )
        return cursor.rowcount
