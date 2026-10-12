"""Regras de negócio e acesso ao banco para o cadastro de pacientes.

Regras aplicadas (ver documento da Etapa 1):
  RN01  nome, CPF e data de nascimento são obrigatórios
  RN02  CPF válido e único (digitado só com números)
  RN03  data de nascimento não pode ser futura
  RN12  paciente com consultas vinculadas não pode ser excluído
"""
import sqlite3
from datetime import date

import database
from services.validacoes import (
    ErroValidacao,
    cpf_valido,
    data_br_para_date,
    email_valido,
    somente_digitos,
    telefone_valido,
)


def _validar(nome, cpf, nascimento, telefone, email):
    """Valida os campos e devolve os dados limpos, prontos para gravar."""
    nome = (nome or "").strip()
    if not nome:
        raise ErroValidacao("O nome é obrigatório.")

    cpf = somente_digitos(cpf)
    if not cpf:
        raise ErroValidacao("O CPF é obrigatório.")
    if not cpf_valido(cpf):
        raise ErroValidacao("CPF inválido. Digite os 11 números, sem pontos nem traço.")

    if not (nascimento or "").strip():
        raise ErroValidacao("A data de nascimento é obrigatória.")
    data_nasc = data_br_para_date(nascimento)
    if data_nasc > date.today():
        raise ErroValidacao("A data de nascimento não pode ser futura.")

    telefone = somente_digitos(telefone)
    if telefone and not telefone_valido(telefone):
        raise ErroValidacao("Telefone inválido. Digite o DDD e o número (10 ou 11 dígitos).")

    email = (email or "").strip()
    if email and not email_valido(email):
        raise ErroValidacao("E-mail inválido. Exemplo: nome@exemplo.com")

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
    """Exclui um paciente, se ele não tiver consultas vinculadas (RN12)."""
    with database.transacao() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM consulta WHERE paciente_id = ?", (id_paciente,)
        ).fetchone()[0]
        if total > 0:
            raise ErroValidacao(
                f"Não é possível excluir: o paciente tem {total} consulta(s) vinculada(s). "
                "O histórico de atendimentos é preservado."
            )
        cursor = con.execute("DELETE FROM paciente WHERE id = ?", (id_paciente,))
        if cursor.rowcount == 0:
            raise ErroValidacao("Paciente não encontrado. Atualize a lista e tente de novo.")


def listar(busca=""):
    """Lista pacientes por ordem de nome. `busca` filtra por nome ou CPF."""
    busca = (busca or "").strip()
    sql = "SELECT * FROM paciente"
    parametros = []
    if busca:
        condicoes = ["nome LIKE ?"]
        parametros.append(f"%{busca}%")
        digitos = somente_digitos(busca)
        if digitos:  # permite buscar o CPF digitado com ou sem pontuação
            condicoes.append("cpf LIKE ?")
            parametros.append(f"%{digitos}%")
        sql += " WHERE " + " OR ".join(condicoes)
    sql += " ORDER BY nome COLLATE NOCASE"
    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]
