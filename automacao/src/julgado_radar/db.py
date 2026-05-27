"""Conexao SQLite + schema (FTS5 + triggers) + migrations idempotentes.

Arquivo: state/julgados_radar.db. Single-file, sem infra.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILENAME = "julgados_radar.db"


SCHEMA_SQL = """
-- Tabela principal de julgados (1 linha por acordao)
CREATE TABLE IF NOT EXISTS julgados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tribunal TEXT NOT NULL,
    processo_id TEXT NOT NULL,
    relator TEXT DEFAULT '',
    orgao TEXT DEFAULT '',
    data_julgamento TEXT DEFAULT '',
    data_publicacao TEXT DEFAULT '',
    area TEXT NOT NULL,
    classe TEXT DEFAULT '',
    tese TEXT NOT NULL,
    ementa TEXT DEFAULT '',
    citacao_voto TEXT DEFAULT '',
    fundamentos_json TEXT DEFAULT '[]',
    url_fonte TEXT DEFAULT '',
    pdf_local TEXT DEFAULT '',
    info_origem TEXT DEFAULT '',
    score_relevancia INTEGER DEFAULT 50,
    usado_em_post TEXT DEFAULT '',
    indexado_em TEXT NOT NULL,
    UNIQUE(tribunal, processo_id)
);

-- Full-text search (FTS5) — indexa tese + ementa + citacao_voto + relator
-- tokenize='unicode61 remove_diacritics 2' normaliza acentos (busca 'usucapiao'
-- bate 'usucapião'). Porter desabilitado: linguagem portuguesa nao tem stemmer
-- nativo bom no FTS5; preferir buscas literais + LIKE como fallback.
CREATE VIRTUAL TABLE IF NOT EXISTS julgados_fts USING fts5(
    tese, ementa, citacao_voto, relator,
    content='julgados', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

-- Triggers para manter FTS sincronizado com a tabela base
CREATE TRIGGER IF NOT EXISTS julgados_ai AFTER INSERT ON julgados BEGIN
    INSERT INTO julgados_fts(rowid, tese, ementa, citacao_voto, relator)
    VALUES (new.id, new.tese, new.ementa, new.citacao_voto, new.relator);
END;

CREATE TRIGGER IF NOT EXISTS julgados_au AFTER UPDATE ON julgados BEGIN
    INSERT INTO julgados_fts(julgados_fts, rowid, tese, ementa, citacao_voto, relator)
    VALUES('delete', old.id, old.tese, old.ementa, old.citacao_voto, old.relator);
    INSERT INTO julgados_fts(rowid, tese, ementa, citacao_voto, relator)
    VALUES (new.id, new.tese, new.ementa, new.citacao_voto, new.relator);
END;

CREATE TRIGGER IF NOT EXISTS julgados_ad AFTER DELETE ON julgados BEGIN
    INSERT INTO julgados_fts(julgados_fts, rowid, tese, ementa, citacao_voto, relator)
    VALUES('delete', old.id, old.tese, old.ementa, old.citacao_voto, old.relator);
END;

-- Indices auxiliares pra filtros
CREATE INDEX IF NOT EXISTS idx_julgados_area ON julgados(area);
CREATE INDEX IF NOT EXISTS idx_julgados_tribunal ON julgados(tribunal);
CREATE INDEX IF NOT EXISTS idx_julgados_data ON julgados(data_julgamento);

-- Auditoria de itens descartados (fora das areas-alvo ou invalidos)
CREATE TABLE IF NOT EXISTS descartados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tribunal TEXT DEFAULT '',
    processo_id TEXT DEFAULT '',
    motivo TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    descartado_em TEXT NOT NULL
);

-- Tracking idempotente do backfill (1 linha por unidade de fetch)
CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte TEXT NOT NULL UNIQUE,
    fetched_em TEXT NOT NULL,
    status TEXT NOT NULL,
    itens_inseridos INTEGER DEFAULT 0,
    erro TEXT DEFAULT ''
);
"""


def conectar(db_path: Path) -> sqlite3.Connection:
    """Abre conexao SQLite com row_factory dict-like e foreign keys ON."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def aplicar_schema(conn: sqlite3.Connection) -> None:
    """Aplica o schema completo. Idempotente (todos os CREATE sao IF NOT EXISTS)."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def path_db(state_dir: Path) -> Path:
    """Caminho canonico do banco do radar dentro de state_dir."""
    return Path(state_dir) / DB_FILENAME


def abrir(state_dir: Path) -> sqlite3.Connection:
    """Helper completo: conecta + aplica schema. Devolve conn pronta."""
    conn = conectar(path_db(state_dir))
    aplicar_schema(conn)
    return conn
