"""Regras de negócio e acesso ao banco para o cadastro de pacientes.

Regras aplicadas (numeração igual à do relatório, seção 3):
  RN02  nome, CPF (11 números) e data de nascimento são obrigatórios e validados
  RN04  paciente com consultas vinculadas não pode ser excluído (use "Desativar": exclusão lógica)
  RN05  data de nascimento em formato válido e não pode ser futura
  RN06  o CPF não pode se repetir no sistema
"""
import sqlite3
from datetime import date

import database
from services.validacoes import (
    MSG_EMAIL,
    ErroValidacao,
    cpf_valido,
    data_br_para_date,
    email_valido,
    motivo_telefone_invalido,
    normalizar,
    somente_digitos,
)


# MODO DE TESTE: False = aceita CPFs não verdadeiros (só exige 11 números).
# Para voltar a conferir os dígitos verificadores, troque para True.
VALIDAR_CPF = False


def _validar(nome, cpf, nascimento, telefone, email):
    """Valida os campos e devolve os dados limpos, prontos para gravar."""
    nome = (nome or "").strip()
    if not nome:
        raise ErroValidacao("O nome é obrigatório.")

    cpf = somente_digitos(cpf)
    if not cpf:
        raise ErroValidacao("O CPF é obrigatório.")
    if len(cpf) != 11:
        raise ErroValidacao("CPF inválido. Digite os 11 números, sem pontos nem traço.")
    if VALIDAR_CPF and not cpf_valido(cpf):
        raise ErroValidacao("CPF inválido. Confira os números digitados.")

    if not (nascimento or "").strip():
        raise ErroValidacao("A data de nascimento é obrigatória.")
    data_nasc = data_br_para_date(nascimento)
    if data_nasc > date.today():
        raise ErroValidacao("A data de nascimento não pode ser futura.")

    telefone = somente_digitos(telefone)
    if telefone:
        motivo = motivo_telefone_invalido(telefone)
        if motivo:
            raise ErroValidacao(motivo)

    email = (email or "").strip()
    if email and not email_valido(email):
        raise ErroValidacao(MSG_EMAIL)

    return {
        "nome": nome,
        "cpf": cpf,
        "data_nascimento": data_nasc.isoformat(),
        "telefone": telefone or None,
        "email": email or None,
    }


def cadastrar(nome, cpf, nascimento, telefone="", email=""):
    """Cadastra um paciente e devolve o id criado."""
    dados = _validar(nome, cpf, nascimento, telefone, email)
    try:
        with database.transacao() as con:
            cursor = con.execute(
                "INSERT INTO paciente (nome, cpf, data_nascimento, telefone, email) "
                "VALUES (:nome, :cpf, :data_nascimento, :telefone, :email)",
                dados,
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe um paciente cadastrado com este CPF.")


def atualizar(id_paciente, nome, cpf, nascimento, telefone="", email=""):
    """Altera os dados de um paciente existente."""
    dados = _validar(nome, cpf, nascimento, telefone, email)
    dados["id"] = id_paciente
    try:
        with database.transacao() as con:
            cursor = con.execute(
                "UPDATE paciente SET nome = :nome, cpf = :cpf, "
                "data_nascimento = :data_nascimento, telefone = :telefone, "
                "email = :email WHERE id = :id",
                dados,
            )
            if cursor.rowcount == 0:
                raise ErroValidacao("Paciente não encontrado. Atualize a lista e tente de novo.")
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe outro paciente cadastrado com este CPF.")


def excluir(id_paciente):
    """Exclui um paciente, se ele não tiver consultas vinculadas (RN04)."""
    with database.transacao() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM consulta WHERE paciente_id = ?", (id_paciente,)
        ).fetchone()[0]
        if total > 0:
            raise ErroValidacao(
                f"Não é possível excluir: o paciente tem {total} consulta(s) vinculada(s). "
                "Para preservar o histórico, use 'Desativar' (o paciente sai das buscas "
                "do agendamento, mas os dados continuam guardados)."
            )
        cursor = con.execute("DELETE FROM paciente WHERE id = ?", (id_paciente,))
        if cursor.rowcount == 0:
            raise ErroValidacao("Paciente não encontrado. Atualize a lista e tente de novo.")


def alternar_ativo(id_paciente):
    """Desativa (exclusão lógica) ou reativa um paciente. Devolve a nova situação (1 ou 0)."""
    with database.transacao() as con:
        linha = con.execute("SELECT ativo FROM paciente WHERE id = ?", (id_paciente,)).fetchone()
        if not linha:
            raise ErroValidacao("Paciente não encontrado. Atualize a lista e tente de novo.")
        novo = 0 if linha["ativo"] == 1 else 1
        con.execute("UPDATE paciente SET ativo = ? WHERE id = ?", (novo, id_paciente))
        return novo


def obter(id_paciente):
    with database.transacao() as con:
        linha = con.execute("SELECT * FROM paciente WHERE id = ?", (id_paciente,)).fetchone()
        return dict(linha) if linha else None


def listar(busca="", incluir_inativos=True, limite=None, offset=0):
    """Lista pacientes por ordem de nome.

    `busca` filtra por nome (sem diferenciar maiúsculas nem acentos, aceita parte do nome),
    CPF ou telefone. `incluir_inativos=False` esconde os desativados (usado no agendamento).
    `limite`/`offset` fazem a paginação no banco, para bases grandes.
    """
    busca = (busca or "").strip()
    filtros, parametros = [], []
    if busca:
        condicoes = ["sem_acento(nome) LIKE ?"]
        parametros.append(f"%{normalizar(busca)}%")
        digitos = somente_digitos(busca)
        if digitos:  # permite buscar CPF ou telefone digitado com ou sem pontuação
            condicoes.append("cpf LIKE ?")
            parametros.append(f"%{digitos}%")
            condicoes.append("telefone LIKE ?")
            parametros.append(f"%{digitos}%")
        filtros.append("(" + " OR ".join(condicoes) + ")")
    if not incluir_inativos:
        filtros.append("ativo = 1")
    sql = "SELECT * FROM paciente"
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY nome COLLATE NOCASE"
    if limite is not None:
        sql += " LIMIT ? OFFSET ?"
        parametros.extend([int(limite), int(offset)])
    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]
