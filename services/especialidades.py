"""Regras de negócio e acesso ao banco das especialidades.

Regras aplicadas:
  * Nome obrigatório e único.
  * Cada especialidade tem o "valor da consulta" (em centavos). Só o super usuário pode
    definir ou alterar esse valor: a permissão é conferida aqui, no back-end.
  * Não é possível excluir uma especialidade que tenha médicos ou consultas vinculados.
  * A busca ignora maiúsculas/minúsculas e acentos e aceita parte do nome ("card" → Cardiologia).
"""
import sqlite3

import database
from services import autenticacao, financeiro
from services.validacoes import ErroValidacao, normalizar

MSG_VALOR_SO_SUPER = "Somente o super usuário pode definir ou alterar o valor da consulta."


def _nome_valido(nome):
    nome = (nome or "").strip()
    if not nome:
        raise ErroValidacao("O nome da especialidade é obrigatório.")
    return nome


def listar(busca="", limite=None, offset=0):
    """Lista especialidades por nome, com o valor e a quantidade de médicos de cada uma."""
    sql = (
        "SELECT e.id, e.nome, e.valor_consulta, "
        "(SELECT COUNT(*) FROM profissional p WHERE p.especialidade_id = e.id) AS total_medicos "
        "FROM especialidade e"
    )
    parametros = []
    termo = normalizar((busca or "").strip())
    if termo:
        sql += " WHERE sem_acento(e.nome) LIKE ?"
        parametros.append(f"%{termo}%")
    sql += " ORDER BY e.nome COLLATE NOCASE"
    if limite is not None:
        sql += " LIMIT ? OFFSET ?"
        parametros.extend([int(limite), int(offset)])
    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]


def obter(id_especialidade):
    with database.transacao() as con:
        linha = con.execute(
            "SELECT id, nome, valor_consulta FROM especialidade WHERE id = ?",
            (id_especialidade,),
        ).fetchone()
        return dict(linha) if linha else None


def cadastrar(nome, valor_centavos=0, executor_id=None):
    """Cadastra uma especialidade. Definir um valor diferente de zero exige super usuário."""
    nome = _nome_valido(nome)
    if valor_centavos:
        autenticacao.exigir_superusuario(executor_id, MSG_VALOR_SO_SUPER)
    try:
        with database.transacao() as con:
            cursor = con.execute("INSERT INTO especialidade (nome) VALUES (?)", (nome,))
            novo_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe uma especialidade com este nome.") from None
    if valor_centavos:
        financeiro.alterar_valor_especialidade(executor_id, novo_id, valor_centavos)
    return novo_id


def atualizar(id_especialidade, nome, valor_centavos=None, executor_id=None):
    """Altera o nome e, se `valor_centavos` vier e for diferente, o valor (só super usuário)."""
    nome = _nome_valido(nome)
    atual = obter(id_especialidade)
    if atual is None:
        raise ErroValidacao("Especialidade não encontrada. Atualize a lista e tente de novo.")
    mudou_valor = valor_centavos is not None and valor_centavos != atual["valor_consulta"]
    if mudou_valor:
        autenticacao.exigir_superusuario(executor_id, MSG_VALOR_SO_SUPER)
    try:
        with database.transacao() as con:
            con.execute(
                "UPDATE especialidade SET nome = ? WHERE id = ?", (nome, id_especialidade)
            )
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe outra especialidade com este nome.") from None
    if mudou_valor:
        financeiro.alterar_valor_especialidade(executor_id, id_especialidade, valor_centavos)


def excluir(id_especialidade):
    """Exclui a especialidade se não houver médicos nem consultas ligados a ela."""
    with database.transacao() as con:
        esp = con.execute(
            "SELECT nome FROM especialidade WHERE id = ?", (id_especialidade,)
        ).fetchone()
        if esp is None:
            raise ErroValidacao("Especialidade não encontrada. Atualize a lista e tente de novo.")
        medicos = con.execute(
            "SELECT COUNT(*) FROM profissional WHERE especialidade_id = ?", (id_especialidade,)
        ).fetchone()[0]
        consultas = con.execute(
            "SELECT COUNT(*) FROM consulta c JOIN profissional p ON c.profissional_id = p.id "
            "WHERE p.especialidade_id = ?",
            (id_especialidade,),
        ).fetchone()[0]
        if medicos or consultas:
            partes = []
            if medicos:
                partes.append(f"{medicos} médico(s)")
            if consultas:
                partes.append(f"{consultas} consulta(s)")
            raise ErroValidacao(
                f"Não é possível excluir a especialidade '{esp['nome']}': "
                f"ela tem {' e '.join(partes)} vinculado(s)."
            )
        con.execute("DELETE FROM especialidade WHERE id = ?", (id_especialidade,))
