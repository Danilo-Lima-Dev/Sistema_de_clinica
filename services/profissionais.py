"""Regras de negócio e acesso ao banco para o cadastro de profissionais de saúde.

Regras aplicadas (ver documento de requisitos):
  RF03  cadastro, listagem, alteração e exclusão de profissionais
  RF04  busca de profissionais pelo nome ou pela especialidade
  RN02  nome, registro e especialidade são obrigatórios
  RN04  profissional com consultas vinculadas não pode ser excluído
  RN06  registro profissional (CRM, CREFITO etc.) único no sistema
"""
import sqlite3

import database
from services.validacoes import (
    ErroValidacao,
    motivo_telefone_invalido,
    normalizar,
    somente_digitos,
)


def listar_especialidades():
    """Devolve a lista de especialidades cadastradas no banco."""
    with database.transacao() as con:
        linhas = con.execute("SELECT id, nome FROM especialidade ORDER BY nome").fetchall()
        return [dict(linha) for linha in linhas]


def _resolver_especialidade_id(con, especialidade):
    """Devolve o id da especialidade, buscando por id ou nome."""
    if isinstance(especialidade, int):
        linha = con.execute("SELECT id FROM especialidade WHERE id = ?", (especialidade,)).fetchone()
        if linha:
            return linha["id"]
    elif isinstance(especialidade, str) and especialidade.strip():
        nome = especialidade.strip()
        linha = con.execute(
            "SELECT id FROM especialidade WHERE nome = ? COLLATE NOCASE", (nome,)
        ).fetchone()
        if linha:
            return linha["id"]
        # Se for uma especialidade nova digitada, cadastra automaticamente
        cursor = con.execute("INSERT INTO especialidade (nome) VALUES (?)", (nome,))
        return cursor.lastrowid

    raise ErroValidacao("A especialidade é obrigatória.")


def _validar(con, nome, registro, especialidade, telefone=""):
    """Valida os campos de profissional e devolve os dados tratados."""
    nome = (nome or "").strip()
    if not nome:
        raise ErroValidacao("O nome do profissional é obrigatório.")

    registro = (registro or "").strip()
    if not registro:
        raise ErroValidacao("O registro profissional (CRM, CREFITO etc.) é obrigatório.")

    esp_id = _resolver_especialidade_id(con, especialidade)

    telefone = somente_digitos(telefone)
    if telefone:
        motivo = motivo_telefone_invalido(telefone)
        if motivo:
            raise ErroValidacao(motivo)

    return {
        "nome": nome,
        "registro": registro,
        "especialidade_id": esp_id,
        "telefone": telefone or None,
    }


def cadastrar(nome, registro, especialidade, telefone=""):
    """Cadastra um novo profissional de saúde e devolve o id gerado."""
    try:
        with database.transacao() as con:
            dados = _validar(con, nome, registro, especialidade, telefone)
            dados["ativo"] = 1
            cursor = con.execute(
                "INSERT INTO profissional (nome, registro, especialidade_id, telefone, ativo) "
                "VALUES (:nome, :registro, :especialidade_id, :telefone, :ativo)",
                dados,
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe um profissional cadastrado com este registro profissional.")


def atualizar(id_profissional, nome, registro, especialidade, telefone="", ativo=1):
    """Atualiza os dados de um profissional de saúde cadastrado."""
    try:
        with database.transacao() as con:
            dados = _validar(con, nome, registro, especialidade, telefone)
            dados["id"] = id_profissional
            dados["ativo"] = 1 if ativo else 0
            cursor = con.execute(
                "UPDATE profissional SET nome = :nome, registro = :registro, "
                "especialidade_id = :especialidade_id, telefone = :telefone, ativo = :ativo "
                "WHERE id = :id",
                dados,
            )
            if cursor.rowcount == 0:
                raise ErroValidacao("Profissional não encontrado. Atualize a lista e tente de novo.")
    except sqlite3.IntegrityError:
        raise ErroValidacao("Já existe outro profissional cadastrado com este registro profissional.")


def alternar_ativo(id_profissional):
    """Alterna o status do profissional entre Ativo e Inativo."""
    with database.transacao() as con:
        linha = con.execute(
            "SELECT ativo FROM profissional WHERE id = ?", (id_profissional,)
        ).fetchone()
        if not linha:
            raise ErroValidacao("Profissional não encontrado.")
        novo_status = 0 if linha["ativo"] == 1 else 1
        con.execute(
            "UPDATE profissional SET ativo = ? WHERE id = ?",
            (novo_status, id_profissional),
        )
        return novo_status


def excluir(id_profissional):
    """Exclui o profissional se não houver consultas vinculadas a ele (RN04)."""
    with database.transacao() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM consulta WHERE profissional_id = ?",
            (id_profissional,),
        ).fetchone()[0]
        if total > 0:
            raise ErroValidacao(
                f"Não é possível excluir: o profissional tem {total} consulta(s) vinculada(s). "
                "Para desativar novos agendamentos sem perder o histórico, use 'Inativar'."
            )
        cursor = con.execute("DELETE FROM profissional WHERE id = ?", (id_profissional,))
        if cursor.rowcount == 0:
            raise ErroValidacao("Profissional não encontrado. Atualize a lista e tente de novo.")


def listar(busca="", apenas_ativos=False, limite=None, offset=0):
    """Lista profissionais em ordem alfabética.

    RF04: A busca pesquisa pelo nome do profissional, pelo registro ou pelo nome da
    especialidade, sem diferenciar maiúsculas nem acentos e aceitando parte do texto.
    `limite`/`offset` fazem a paginação no banco, para bases grandes.
    """
    busca = (busca or "").strip()
    sql = """
        SELECT p.id, p.nome, p.registro, p.especialidade_id,
               e.nome AS especialidade, e.valor_consulta, p.telefone, p.ativo
        FROM profissional p
        JOIN especialidade e ON p.especialidade_id = e.id
    """
    filtros = []
    parametros = []

    if busca:
        filtros.append(
            "(sem_acento(p.nome) LIKE ? OR sem_acento(p.registro) LIKE ? OR sem_acento(e.nome) LIKE ?)"
        )
        parametros.extend([f"%{normalizar(busca)}%"] * 3)

    if apenas_ativos:
        filtros.append("p.ativo = 1")

    if filtros:
        sql += " WHERE " + " AND ".join(filtros)

    sql += " ORDER BY p.nome COLLATE NOCASE"
    if limite is not None:
        sql += " LIMIT ? OFFSET ?"
        parametros.extend([int(limite), int(offset)])

    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]


def obter(id_profissional):
    """Retorna os dados completos de um único profissional."""
    sql = """
        SELECT p.id, p.nome, p.registro, p.especialidade_id,
               e.nome AS especialidade, e.valor_consulta, p.telefone, p.ativo
        FROM profissional p
        JOIN especialidade e ON p.especialidade_id = e.id
        WHERE p.id = ?
    """
    with database.transacao() as con:
        linha = con.execute(sql, (id_profissional,)).fetchone()
        return dict(linha) if linha else None
