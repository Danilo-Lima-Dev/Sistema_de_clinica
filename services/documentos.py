"""Documentos emitidos (atestados e receituários) guardados no banco, por paciente.

Todo atestado/receituário gerado na tela de consultas é SALVO aqui automaticamente, com o
texto, a página para impressão, quem emitiu e quando.

Quem pode o quê (a permissão é conferida no back-end, com `autenticacao.exigir_papel`):
  - EMITIR (criar o documento): só o Médico, e só de consultas dele.
  - VER o conteúdo: o Médico (documentos das suas consultas) e o Atendente (só leitura).
  - LISTAR (tipo, data, médico; sem o conteúdo): Administrador, Atendente e Médico.
  - 2ª via pela recepção: só o Atendente, e SEMPRE com o registro de entrega (para quem foi).
  - Registro de entregas (auditoria): só o Administrador.
"""
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

import database
from services import autenticacao
from services.autenticacao import PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO
from services.validacoes import ErroValidacao

ATESTADO = "Atestado"
RECEITUARIO = "Receituário"

FORMAS_ENTREGA = ("Impressão", "PDF")
VINCULOS = ("Próprio paciente", "Responsável legal", "Autorizado pelo paciente")

MSG_SO_MEDICO_EMITE = "Somente o médico pode emitir atestados e receituários."
MSG_SEM_ACESSO = "Você não tem permissão para ver os documentos dos pacientes."
MSG_SEM_ACESSO_CONTEUDO = "Você não tem permissão para ver o conteúdo deste documento."
MSG_SO_MEDICO_REIMPRIME = "Somente o médico reimprime direto. A recepção entrega a 2ª via com registro."
MSG_SO_RECEPCAO_ENTREGA = "Somente a recepção entrega a 2ª via com registro de entrega."
MSG_SO_ADMIN_AUDITORIA = "Somente o administrador vê o registro de entregas."
MSG_DOC_DE_OUTRO = "Este documento é de uma consulta de outro profissional."


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _nome_do_usuario(con, usuario_id):
    linha = con.execute("SELECT nome FROM usuario WHERE id = ?", (usuario_id,)).fetchone()
    return linha["nome"] if linha else "(não informado)"


# ------------------------------------------------------------------ emitir
def salvar(tipo, id_consulta, texto, html, usuario=None):
    """Grava um documento emitido, ligado ao paciente da consulta. Devolve o id.

    Só o Médico emite, e só de consultas dele.
    """
    if tipo not in (ATESTADO, RECEITUARIO):
        raise ErroValidacao("Tipo de documento inválido.")
    usuario = usuario or {}
    medico = autenticacao.exigir_papel(
        usuario.get("id"), PAPEL_MEDICO, mensagem=MSG_SO_MEDICO_EMITE
    )
    with database.transacao() as con:
        c = con.execute(
            "SELECT c.paciente_id, c.profissional_id, pr.nome AS medico FROM consulta c "
            "JOIN profissional pr ON c.profissional_id = pr.id WHERE c.id = ?",
            (id_consulta,),
        ).fetchone()
        if c is None:
            raise ErroValidacao("Consulta não encontrada.")
        if c["profissional_id"] != medico["profissional_id"]:
            raise ErroValidacao("O médico só emite documentos das suas próprias consultas.")
        cursor = con.execute(
            "INSERT INTO documento_emitido (paciente_id, consulta_id, tipo, data_hora, "
            "profissional_nome, emitido_por_id, emitido_por_nome, texto, html) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c["paciente_id"], id_consulta, tipo, _agora(), c["medico"],
             medico["id"], _nome_do_usuario(con, medico["id"]), texto, html),
        )
        return cursor.lastrowid


# ------------------------------------------------------------------ consultar
def listar(executor_id, paciente_id):
    """Documentos salvos de UM paciente (mais recentes primeiro), SEM o conteúdo.

    Administrador, Atendente e Médico podem listar. O Médico só enxerga os documentos
    das consultas dele.
    """
    quem = autenticacao.exigir_papel(
        executor_id, PAPEL_ADMIN, PAPEL_ATENDENTE, PAPEL_MEDICO, mensagem=MSG_SEM_ACESSO
    )
    sql = (
        "SELECT id, tipo, data_hora, consulta_id, profissional_nome, emitido_por_nome "
        "FROM documento_emitido WHERE paciente_id = ?"
    )
    parametros = [paciente_id]
    if quem["papel"] == PAPEL_MEDICO:
        sql += " AND consulta_id IN (SELECT id FROM consulta WHERE profissional_id = ?)"
        parametros.append(quem["profissional_id"])
    sql += " ORDER BY id DESC"
    with database.transacao() as con:
        return [dict(linha) for linha in con.execute(sql, parametros)]


def obter(executor_id, id_documento):
    """Documento completo (com texto e página). Atendente (só leitura) e Médico (os seus)."""
    quem = autenticacao.exigir_papel(
        executor_id, PAPEL_ATENDENTE, PAPEL_MEDICO, mensagem=MSG_SEM_ACESSO_CONTEUDO
    )
    with database.transacao() as con:
        linha = con.execute(
            "SELECT d.*, c.profissional_id AS prof_da_consulta FROM documento_emitido d "
            "LEFT JOIN consulta c ON c.id = d.consulta_id WHERE d.id = ?",
            (id_documento,),
        ).fetchone()
    if linha is None:
        raise ErroValidacao("Documento não encontrado.")
    if quem["papel"] == PAPEL_MEDICO and linha["prof_da_consulta"] != quem["profissional_id"]:
        raise ErroValidacao(MSG_DOC_DE_OUTRO)
    doc = dict(linha)
    doc.pop("prof_da_consulta")
    return doc


# ------------------------------------------------------------------ 2ª via
def _abrir_no_navegador(doc):
    pasta = Path(tempfile.gettempdir()) / "sistema_clinica_salvos"
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / f"{doc['tipo'].lower().replace('á', 'a')}_{doc['id']:06d}.html"
    arquivo.write_text(doc["html"], encoding="utf-8")
    if not webbrowser.open(arquivo.as_uri()):
        raise ErroValidacao(f"Não foi possível abrir o navegador. Abra o arquivo: {arquivo}")
    return arquivo


def reimprimir(executor_id, id_documento):
    """O próprio médico abre de novo um documento seu (janela de impressão)."""
    autenticacao.exigir_papel(executor_id, PAPEL_MEDICO, mensagem=MSG_SO_MEDICO_REIMPRIME)
    return _abrir_no_navegador(obter(executor_id, id_documento))


def entregar_segunda_via(executor_id, id_documento, forma, destinatario_nome,
                         vinculo, destinatario_documento):
    """A recepção entrega a 2ª via, idêntica à original, e o sistema REGISTRA a entrega.

    `forma` é 'Impressão' ou 'PDF' (no navegador: Imprimir > Salvar como PDF).
    Exige o nome de quem recebe, o vínculo com o paciente e o CPF/RG dessa pessoa.
    O registro é gravado antes de abrir o documento.
    """
    quem = autenticacao.exigir_papel(
        executor_id, PAPEL_ATENDENTE, mensagem=MSG_SO_RECEPCAO_ENTREGA
    )
    destinatario_nome = (destinatario_nome or "").strip()
    destinatario_documento = (destinatario_documento or "").strip()
    if forma not in FORMAS_ENTREGA:
        raise ErroValidacao("Escolha a forma de entrega: Impressão ou PDF.")
    if vinculo not in VINCULOS:
        raise ErroValidacao(
            "Informe o vínculo: próprio paciente, responsável legal ou autorizado pelo paciente."
        )
    if not destinatario_nome:
        raise ErroValidacao("Informe o nome de quem vai receber o documento.")
    if len(destinatario_documento) < 5:
        raise ErroValidacao("Informe o CPF ou RG de quem vai receber o documento.")

    doc = obter(executor_id, id_documento)
    with database.transacao() as con:
        con.execute(
            "INSERT INTO entrega_documento (documento_id, forma, destinatario_nome, "
            "destinatario_vinculo, destinatario_documento, usuario_id, usuario_nome, data_hora) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (id_documento, forma, destinatario_nome, vinculo, destinatario_documento,
             quem["id"], _nome_do_usuario(con, quem["id"]), _agora()),
        )
    return _abrir_no_navegador(doc)


def listar_entregas(executor_id, limite=300):
    """Registro de entregas de 2ª via (auditoria). Só o Administrador; sem o conteúdo clínico."""
    autenticacao.exigir_papel(executor_id, PAPEL_ADMIN, mensagem=MSG_SO_ADMIN_AUDITORIA)
    with database.transacao() as con:
        return [
            dict(linha) for linha in con.execute(
                "SELECT e.id, e.data_hora, e.forma, e.destinatario_nome, e.destinatario_vinculo, "
                "e.destinatario_documento, e.usuario_nome, d.tipo, p.nome AS paciente_nome "
                "FROM entrega_documento e "
                "JOIN documento_emitido d ON d.id = e.documento_id "
                "JOIN paciente p ON p.id = d.paciente_id "
                "ORDER BY e.id DESC LIMIT ?",
                (limite,),
            )
        ]