"""Indexer — insere julgados no DB com dedup e log de fetch.

Usa INSERT OR IGNORE pra dedup por (tribunal, processo_id). Mantem fetch_log
populado pra idempotencia do backfill.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from src.julgado_radar.models import Descartado, Julgado
from src.state import agora_iso


# Colunas insertaveis (id e auto)
_COLS_JULGADO = (
    "tribunal", "processo_id", "relator", "orgao",
    "data_julgamento", "data_publicacao", "area", "classe",
    "tese", "ementa", "citacao_voto", "fundamentos_json",
    "url_fonte", "pdf_local", "info_origem", "score_relevancia",
    "usado_em_post", "indexado_em",
)


def upsert_julgado(conn: sqlite3.Connection, julgado: Julgado) -> tuple[int, bool]:
    """Insere ou atualiza um julgado. Devolve (id, inserido_novo).

    Politica: se (tribunal, processo_id) ja existe, UPDATE com os dados novos.
    """
    if not julgado.indexado_em:
        julgado.indexado_em = agora_iso()
    row = julgado.to_row()
    valores = {c: row.get(c, "") for c in _COLS_JULGADO}

    cur = conn.execute(
        "SELECT id FROM julgados WHERE tribunal=? AND processo_id=?",
        (julgado.tribunal, julgado.processo_id),
    )
    existente = cur.fetchone()

    if existente is None:
        placeholders = ",".join(":" + c for c in _COLS_JULGADO)
        conn.execute(
            f"INSERT INTO julgados ({','.join(_COLS_JULGADO)}) VALUES ({placeholders})",
            valores,
        )
        conn.commit()
        cur = conn.execute(
            "SELECT id FROM julgados WHERE tribunal=? AND processo_id=?",
            (julgado.tribunal, julgado.processo_id),
        )
        return cur.fetchone()["id"], True

    id_existente = existente["id"]
    sets = ", ".join(f"{c}=:{c}" for c in _COLS_JULGADO)
    valores["_id"] = id_existente
    conn.execute(f"UPDATE julgados SET {sets} WHERE id=:_id", valores)
    conn.commit()
    return id_existente, False


def registrar_descartado(conn: sqlite3.Connection, descartado: Descartado) -> int:
    """Registra um item descartado e devolve o id criado."""
    if not descartado.descartado_em:
        descartado.descartado_em = agora_iso()
    row = descartado.to_row()
    cur = conn.execute(
        "INSERT INTO descartados (tribunal, processo_id, motivo, payload_json, descartado_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            row.get("tribunal", ""),
            row.get("processo_id", ""),
            row.get("motivo", ""),
            row.get("payload_json", "{}"),
            row.get("descartado_em", ""),
        ),
    )
    conn.commit()
    return cur.lastrowid


def registrar_fetch(
    conn: sqlite3.Connection,
    fonte: str,
    status: str,
    itens_inseridos: int = 0,
    erro: str = "",
) -> None:
    """INSERT OR REPLACE em fetch_log (idempotente — re-rodar atualiza)."""
    conn.execute(
        "INSERT INTO fetch_log (fonte, fetched_em, status, itens_inseridos, erro) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(fonte) DO UPDATE SET fetched_em=excluded.fetched_em, "
        "  status=excluded.status, itens_inseridos=excluded.itens_inseridos, "
        "  erro=excluded.erro",
        (fonte, agora_iso(), status, itens_inseridos, erro),
    )
    conn.commit()


def fetch_ja_feito(conn: sqlite3.Connection, fonte: str) -> bool:
    """Devolve True se ja temos um fetch_log com status=ok pra essa fonte."""
    cur = conn.execute(
        "SELECT status FROM fetch_log WHERE fonte=?", (fonte,),
    )
    row = cur.fetchone()
    return row is not None and row["status"] == "ok"


def indexar_batch(conn: sqlite3.Connection, julgados: Iterable[Julgado]) -> dict:
    """Indexa uma lista de Julgados. Devolve estatistica."""
    inseridos = 0
    atualizados = 0
    for j in julgados:
        _, novo = upsert_julgado(conn, j)
        if novo:
            inseridos += 1
        else:
            atualizados += 1
    return {"inseridos": inseridos, "atualizados": atualizados}


def contar_por_tribunal_area(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Estatistica: {(tribunal, area): count}."""
    cur = conn.execute(
        "SELECT tribunal, area, COUNT(*) as n FROM julgados GROUP BY tribunal, area"
    )
    return {(r["tribunal"], r["area"]): r["n"] for r in cur.fetchall()}
