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
