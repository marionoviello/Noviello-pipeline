"""Searcher — API de busca full-text + filtros sobre julgados_radar.db.

Funcao principal: buscar(termo, area, tribunal, ano, classe, limit) -> list[Julgado].
"""

from __future__ import annotations

import re
import sqlite3
from typing import Optional

from src.julgado_radar.models import Julgado


# Caracteres especiais do FTS5 que precisam ser escapados/quoted.
_FTS5_ESPECIAIS = re.compile(r"[\"\(\)\*\:]")


def _sanitizar_termo_fts(termo: str) -> str:
    """Escapa termo pra MATCH do FTS5 (evita quebra de sintaxe).

    Estrategia: tokeniza por whitespace, quota cada token (envolvendo em "), une com espaco
    (AND implicito do FTS5). Tokens muito curtos sao descartados.
    """
    if not termo or not termo.strip():
        return ""
    tokens: list[str] = []
    for raw in re.split(r"\s+", termo.strip()):
        # remove caracteres especiais do FTS5 do token
        limpo = _FTS5_ESPECIAIS.sub("", raw).strip()
        if len(limpo) >= 2:
            tokens.append(f'"{limpo}"')
    return " ".join(tokens)


def buscar(
    conn: sqlite3.Connection,
    termo: str = "",
    *,
    area: Optional[str] = None,
    tribunal: Optional[str] = None,
    ano: Optional[int] = None,
    classe: Optional[str] = None,
    limit: int = 20,
) -> list[Julgado]:
    """Busca julgados combinando FTS5 (full-text) com filtros simples.

    - termo: string de busca livre (case-insensitive, acentos ignorados).
            Quando vazio, devolve TOP N julgados por data_julgamento desc.
    - area: 'urbanistico' | 'imobiliario' | 'sucessorio'
    - tribunal: 'STJ' | 'TJ-SP'
    - ano: filtra por data_julgamento startswith 'AAAA-MM' ou 'DD/MM/AAAA'
    - classe: substring case-insensitive no campo classe
    - limit: <= 200
    """
    limit = max(1, min(200, limit))

    where: list[str] = []
    params: list = []

    termo_fts = _sanitizar_termo_fts(termo)

    if termo_fts:
        sql_base = (
            "SELECT j.* FROM julgados j JOIN julgados_fts f ON j.id=f.rowid "
            "WHERE julgados_fts MATCH ? "
        )
        params.append(termo_fts)
    else:
        sql_base = "SELECT j.* FROM julgados j WHERE 1=1 "

    if area:
        where.append("j.area = ?")
        params.append(area)
    if tribunal:
        where.append("j.tribunal = ?")
        params.append(tribunal)
    if ano:
        # data_julgamento pode estar em "2024-01-15" ou "15/01/2024" — cobre os 2
        where.append("(j.data_julgamento LIKE ? OR j.data_julgamento LIKE ?)")
        params.extend([f"{ano}%", f"%/{ano}"])
    if classe:
        where.append("LOWER(j.classe) LIKE ?")
        params.append(f"%{classe.lower()}%")

    if where:
        sql_base += " AND " + " AND ".join(where)

    if termo_fts:
        # BM25 ranking padrao do FTS5 — quanto menor, melhor
        sql_base += " ORDER BY bm25(julgados_fts) ASC, j.data_julgamento DESC"
    else:
        sql_base += " ORDER BY j.data_julgamento DESC, j.id DESC"

    sql_base += " LIMIT ?"
    params.append(limit)

    cur = conn.execute(sql_base, params)
    return [Julgado.from_row(dict(row)) for row in cur.fetchall()]


def contar(
    conn: sqlite3.Connection,
    *,
    area: Optional[str] = None,
    tribunal: Optional[str] = None,
) -> int:
    """Conta julgados aplicando filtros simples (sem FTS)."""
    where: list[str] = []
    params: list = []
    if area:
        where.append("area = ?")
        params.append(area)
    if tribunal:
        where.append("tribunal = ?")
        params.append(tribunal)
    sql = "SELECT COUNT(*) AS n FROM julgados"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return conn.execute(sql, params).fetchone()["n"]


def get_por_id(conn: sqlite3.Connection, julgado_id: int) -> Optional[Julgado]:
    cur = conn.execute("SELECT * FROM julgados WHERE id=?", (julgado_id,))
    row = cur.fetchone()
    return Julgado.from_row(dict(row)) if row else None
