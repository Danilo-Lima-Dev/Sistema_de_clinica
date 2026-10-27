"""Acesso ao banco de dados SQLite do Sistema de Clínica.

Este módulo cuida somente da conexão e da criação das tabelas.
As regras de negócio ficam na pasta `services/`.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from services.validacoes import normalizar

# O arquivo do banco fica na mesma pasta do projeto.
DB_PATH = Path(__file__).resolve().parent / "clinica.db"

ESPECIALIDADES_INICIAIS = [
    "Clínica Geral",
    "Pediatria",
    "Cardiologia",
    "Dermatologia",
    "Ortopedia",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS especialidade (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    -- valor da consulta em CENTAVOS (ex.: R$ 150,00 = 15000). Só o super usuário altera.
    valor_consulta INTEGER NOT NULL DEFAULT 0 CHECK (valor_consulta >= 0)
);

-- Usuários que podem entrar no sistema (tela de login).
-- A senha NUNCA é guardada em texto puro: fica só o hash ("salt$hash").
CREATE TABLE IF NOT EXISTS usuario (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    login      TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    ativo      INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    -- 1 = super usuário: pode cadastrar e alterar os outros usuários
    superusuario INTEGER NOT NULL DEFAULT 0 CHECK (superusuario IN (0, 1))
);

CREATE TABLE IF NOT EXISTS paciente (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    cpf             TEXT NOT NULL UNIQUE,      -- somente os 11 números
    data_nascimento TEXT NOT NULL,             -- guardada como AAAA-MM-DD
    telefone        TEXT,                      -- somente números
    email           TEXT,
    -- 0 = desativado (exclusão lógica): some das buscas do agendamento, mas o histórico fica
    ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS profissional (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT NOT NULL,
    registro         TEXT NOT NULL UNIQUE,     -- ex.: CRM
    especialidade_id INTEGER NOT NULL,
    telefone         TEXT,
    ativo            INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    FOREIGN KEY (especialidade_id) REFERENCES especialidade (id)
);

-- Horários que o médico NÃO atende (folga, bloqueio). Cada linha é um horário de 30 min
-- sempre ligado a um médico. Horários fora do expediente ficam em services/agenda.py.
CREATE TABLE IF NOT EXISTS bloqueio_agenda (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    profissional_id INTEGER NOT NULL,
    data            TEXT NOT NULL,             -- AAAA-MM-DD
    hora_inicio     TEXT NOT NULL,             -- HH:MM
    hora_fim        TEXT NOT NULL,             -- HH:MM
    motivo          TEXT,
    UNIQUE (profissional_id, data, hora_inicio),
    FOREIGN KEY (profissional_id) REFERENCES profissional (id) ON DELETE CASCADE
);

-- Atestados e receituários emitidos, guardados por paciente (só o super usuário vê).
CREATE TABLE IF NOT EXISTS documento_emitido (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id       INTEGER NOT NULL,
    consulta_id       INTEGER,
    tipo              TEXT NOT NULL CHECK (tipo IN ('Atestado', 'Receituário')),
    data_hora         TEXT NOT NULL,           -- AAAA-MM-DD HH:MM:SS
    profissional_nome TEXT NOT NULL,
    emitido_por_id    INTEGER,
    emitido_por_nome  TEXT NOT NULL,
    texto             TEXT NOT NULL,           -- conteúdo em texto
    html              TEXT NOT NULL,           -- página pronta para reimprimir
    FOREIGN KEY (paciente_id) REFERENCES paciente (id)
);

-- Histórico do financeiro: quem alterou valor ou pagamento, e quando.
CREATE TABLE IF NOT EXISTS financeiro_historico (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora     TEXT NOT NULL,               -- AAAA-MM-DD HH:MM:SS
    usuario_id    INTEGER,
    usuario_nome  TEXT NOT NULL,
    tipo          TEXT NOT NULL,               -- valor_especialidade, valor_consulta, pagamento
    consulta_id   INTEGER,
    especialidade_id INTEGER,
    descricao     TEXT NOT NULL,
    valor_antigo  INTEGER,                     -- centavos
    valor_novo    INTEGER                      -- centavos
);
"""


# Tabela de consultas. Fica separada do SCHEMA porque bancos antigos precisam ser
# reconstruídos (o CHECK da situação ganhou 'Confirmada'): ver _migrar_consulta().
CONSULTA_DDL = """
CREATE TABLE IF NOT EXISTS consulta (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id         INTEGER NOT NULL,
    profissional_id     INTEGER NOT NULL,
    data                TEXT NOT NULL,         -- guardada como AAAA-MM-DD
    hora_inicio         TEXT NOT NULL,         -- HH:MM
    hora_fim            TEXT NOT NULL,         -- HH:MM
    situacao            TEXT NOT NULL DEFAULT 'Agendada'
                        CHECK (situacao IN ('Agendada', 'Confirmada', 'Realizada', 'Cancelada')),
    motivo_cancelamento TEXT,
    observacoes         TEXT,
    -- registro financeiro da consulta (valor em centavos, copiado da especialidade ao agendar)
    valor_centavos      INTEGER NOT NULL DEFAULT 0 CHECK (valor_centavos >= 0),
    pagamento_status    TEXT NOT NULL DEFAULT 'Aguardando pagamento'
                        CHECK (pagamento_status IN ('Aguardando pagamento', 'Pago')),
    pago_em             TEXT,                  -- AAAA-MM-DD HH:MM:SS
    FOREIGN KEY (paciente_id)     REFERENCES paciente (id),
    FOREIGN KEY (profissional_id) REFERENCES profissional (id)
);
"""

COLUNAS_CONSULTA = (
    "id", "paciente_id", "profissional_id", "data", "hora_inicio", "hora_fim", "situacao",
    "motivo_cancelamento", "observacoes", "valor_centavos", "pagamento_status", "pago_em",
)

# Item 5 também garantido pelo banco: uma consulta só vira 'Confirmada' se estiver paga.
GATILHOS = """
CREATE TRIGGER IF NOT EXISTS tg_confirmar_so_pago_insert
BEFORE INSERT ON consulta
WHEN NEW.situacao = 'Confirmada' AND NEW.pagamento_status != 'Pago'
BEGIN
    SELECT RAISE(ABORT, 'Consulta so pode ser confirmada apos o pagamento');
END;

CREATE TRIGGER IF NOT EXISTS tg_confirmar_so_pago_update
BEFORE UPDATE ON consulta
WHEN NEW.situacao = 'Confirmada' AND NEW.pagamento_status != 'Pago'
BEGIN
    SELECT RAISE(ABORT, 'Consulta so pode ser confirmada apos o pagamento');
END;
"""


# RN01 também garantida pelo banco: o mesmo profissional não pode ter duas
# consultas NÃO canceladas no mesmo dia e horário de início. Consultas
# canceladas ficam de fora do índice, então liberam o horário.
INDICE_CONFLITO_HORARIO = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_consulta_profissional_horario
ON consulta (profissional_id, data, hora_inicio)
WHERE situacao != 'Cancelada'
"""


def conectar():
    """Abre uma conexão com chaves estrangeiras ativadas."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # Permite buscar ignorando maiúsculas e acentos:  WHERE sem_acento(nome) LIKE ?
    con.create_function("sem_acento", 1, normalizar, deterministic=True)
    return con


@contextmanager
def transacao():
    """Entrega uma conexão; confirma (commit) no fim ou desfaz (rollback) se der erro."""
    con = conectar()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def criar_tabelas():
    """Cria as tabelas (se ainda não existirem) e as especialidades iniciais."""
    with transacao() as con:
        con.executescript(SCHEMA)
        con.executescript(CONSULTA_DDL)
    # Bancos antigos recebem as colunas novas ANTES de gravar qualquer dado.
    _migrar_usuario()
    _migrar_colunas_novas()
    _migrar_consulta()
    with transacao() as con:
        con.executescript(GATILHOS)
        con.executemany(
            "INSERT OR IGNORE INTO especialidade (nome) VALUES (?)",
            [(nome,) for nome in ESPECIALIDADES_INICIAIS],
        )
    # O índice fica em uma transação à parte: se um banco antigo já tiver dois
    # agendamentos conflitantes, o índice não é criado, mas o sistema abre normalmente
    # (a regra RN01 continua valendo pela verificação em services/consultas.py).
    try:
        with transacao() as con:
            con.execute(INDICE_CONFLITO_HORARIO)
    except sqlite3.IntegrityError:
        pass


def _migrar_usuario():
    """Bancos criados antes do super usuário não têm a coluna `superusuario`: adiciona."""
    with transacao() as con:
        colunas = [linha["name"] for linha in con.execute("PRAGMA table_info(usuario)")]
        if "superusuario" not in colunas:
            con.execute(
                "ALTER TABLE usuario ADD COLUMN superusuario INTEGER NOT NULL DEFAULT 0 "
                "CHECK (superusuario IN (0, 1))"
            )


def _colunas(con, tabela):
    return [linha["name"] for linha in con.execute(f"PRAGMA table_info({tabela})")]


def _migrar_colunas_novas():
    """Bancos antigos: adiciona `valor_consulta` na especialidade e `ativo` no paciente."""
    with transacao() as con:
        if "valor_consulta" not in _colunas(con, "especialidade"):
            con.execute(
                "ALTER TABLE especialidade ADD COLUMN valor_consulta INTEGER NOT NULL DEFAULT 0 "
                "CHECK (valor_consulta >= 0)"
            )
        if "ativo" not in _colunas(con, "paciente"):
            con.execute(
                "ALTER TABLE paciente ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1 "
                "CHECK (ativo IN (0, 1))"
            )


def _migrar_consulta():
    """Bancos antigos: reconstrói a tabela `consulta` com a situação 'Confirmada' e o financeiro.

    O SQLite não permite mudar o CHECK de uma coluna, então a tabela é recriada e os dados
    são copiados (consultas antigas ficam como 'Aguardando pagamento', com valor 0,00).
    """
    with transacao() as con:
        linha = con.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'consulta'"
        ).fetchone()
        if linha is None or "'Confirmada'" in linha["sql"]:
            return  # banco novo ou já migrado
        antigas = set(_colunas(con, "consulta"))
        con.execute("DROP INDEX IF EXISTS ux_consulta_profissional_horario")
        con.execute("ALTER TABLE consulta RENAME TO consulta_antiga")
        con.execute(CONSULTA_DDL)
        comuns = ", ".join(c for c in COLUNAS_CONSULTA if c in antigas)
        con.execute(f"INSERT INTO consulta ({comuns}) SELECT {comuns} FROM consulta_antiga")
        con.execute("DROP TABLE consulta_antiga")
