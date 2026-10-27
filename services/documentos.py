"""Documentos emitidos (atestados e receituários) guardados no banco, por paciente.

Todo atestado/receituário gerado na tela de consultas é SALVO aqui automaticamente, com o
texto, a página para impressão, quem emitiu e quando. Gravar é permitido a qualquer usuário
que emite o documento; já VER e reimprimir é só do super usuário: a permissão é conferida
no back-end (`autenticacao.exigir_superusuario`), não apenas escondendo a tela.
"""
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

import database
from services import autenticacao
from services.validacoes import ErroValidacao

ATESTADO = "Atestado"
RECEITUARIO = "Receituário"
MSG_SO_SUPER = "Somente o super usuário pode ver os documentos salvos dos pacientes."


def salvar(tipo, id_consulta, texto, html, usuario=None):
    """Grava um documento emitido, ligado ao paciente da consulta. Devolve o id."""
    if tipo not in (ATESTADO, RECEITUARIO):
        raise ErroValidacao("Tipo de documento inválido.")
    usuario = usuario or {}
    with database.transacao() as con:
        c = con.execute(
            "SELECT c.paciente_id, pr.nome AS medico FROM consulta c "
            "JOIN profissional pr ON c.profissional_id = pr.id WHERE c.id = ?",
            (id_consulta,),
        ).fetchone()
        if c is None:
            raise ErroValidacao("Consulta não encontrada.")
        cursor = con.execute(
            "INSERT INTO documento_emitido (paciente_id, consulta_id, tipo, data_hora, "
            "profissional_nome, emitido_por_id, emitido_por_nome, texto, html) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c["paciente_id"], id_consulta, tipo, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             c["medico"], usuario.get("id"), usuario.get("nome") or "(não informado)", texto, html),
        )
        return cursor.lastrowid


def listar(executor_id, paciente_id):
    """Documentos salvos de UM paciente (mais recentes primeiro). Só super usuário."""
    autenticacao.exigir_superusuario(executor_id, MSG_SO_SUPER)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT id, tipo, data_hora, consulta_id, profissional_nome, emitido_por_nome "
                "FROM documento_emitido WHERE paciente_id = ? ORDER BY id DESC",
                (paciente_id,),
            )
        ]


def obter(executor_id, id_documento):
    """Documento completo (com texto e página). Só super usuário."""
    autenticacao.exigir_superusuario(executor_id, MSG_SO_SUPER)
    with database.transacao() as con:
        linha = con.execute(
            "SELECT * FROM documento_emitido WHERE id = ?", (id_documento,)
        ).fetchone()
    if linha is None:
        raise ErroValidacao("Documento não encontrado.")
    return dict(linha)


def reimprimir(executor_id, id_documento):
    """Abre de novo o documento salvo no navegador (janela de impressão)."""
    doc = obter(executor_id, id_documento)
    pasta = Path(tempfile.gettempdir()) / "sistema_clinica_salvos"
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"{doc['tipo'].lower().replace('á', 'a')}_{doc['id']:06d}.html"
    arquivo.write_text(doc["html"], encoding="utf-8")
    if not webbrowser.open(arquivo.as_uri()):
        raise ErroValidacao(f"Não foi possível abrir o navegador. Abra o arquivo: {arquivo}")
    return arquivo
