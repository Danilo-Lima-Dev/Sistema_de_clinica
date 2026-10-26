"""Acesso ao banco de dados SQLite do Sistema de Clínica.

Este módulo cuida somente da conexão e da criação das tabelas.
As regras de negócio ficam na pasta `services/`.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

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
    nome TEXT NOT NULL UNIQUE
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
    email           TEXT
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

CREATE TABLE IF NOT EXISTS consulta (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id         INTEGER NOT NULL,
    profissional_id     INTEGER NOT NULL,
    data                TEXT NOT NULL,         -- guardada como AAAA-MM-DD
    hora_inicio         TEXT NOT NULL,         -- HH:MM
    hora_fim            TEXT NOT NULL,         -- HH:MM
    situacao            TEXT NOT NULL DEFAULT 'Agendada'
                        CHECK (situacao IN ('Agendada', 'Realizada', 'Cancelada')),
    motivo_cancelamento TEXT,
    observacoes         TEXT,
    FOREIGN KEY (paciente_id)     REFERENCES paciente (id),
    FOREIGN KEY (profissional_id) REFERENCES profissional (id)
);
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
        con.executemany(
            "INSERT OR IGNORE INTO especialidade (nome) VALUES (?)",
            [(nome,) for nome in ESPECIALIDADES_INICIAIS],
        )
    _migrar_usuario()
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
