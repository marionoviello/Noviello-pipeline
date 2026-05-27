"""Testes do schema SQLite + FTS5 + triggers."""

import sqlite3

import pytest

from src.julgado_radar import db
from src.julgado_radar.models import Julgado


def _abrir(tmp_path):
    return db.abrir(tmp_path)


def test_aplicar_schema_cria_tabelas(tmp_path):
    conn = _abrir(tmp_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    )
    nomes = [r["name"] for r in cur.fetchall()]
    assert "julgados" in nomes
    assert "descartados" in nomes
    assert "fetch_log" in nomes
    # FTS cria varias tabelas auxiliares com prefixo julgados_fts
    assert any(n.startswith("julgados_fts") for n in nomes)


def test_aplicar_schema_idempotente(tmp_path):
    """Re-aplicar o schema nao quebra."""
    conn = _abrir(tmp_path)
    db.aplicar_schema(conn)  # 2x
    db.aplicar_schema(conn)  # 3x
    # tudo ok, sem excecao


def test_path_db_default(tmp_path):
    p = db.path_db(tmp_path)
    assert p == tmp_path / "julgados_radar.db"


def test_inserir_julgado_e_recuperar(tmp_path):
    conn = _abrir(tmp_path)
    julgado = Julgado(
        tribunal="STJ", processo_id="REsp 2.215.421/SE",
        area="imobiliario", tese="Recibo basta como justo titulo",
        relator="Min. Nancy Andrighi", indexado_em="2026-05-26T08:30:00",
    )
    row = julgado.to_row()
    cols = [k for k in row if k != "id"]
    placeholders = ",".join(":" + c for c in cols)
    conn.execute(
        f"INSERT INTO julgados ({','.join(cols)}) VALUES ({placeholders})",
        row,
    )
    conn.commit()

    cur = conn.execute("SELECT * FROM julgados WHERE tribunal=? AND processo_id=?",
                       (julgado.tribunal, julgado.processo_id))
    found = cur.fetchone()
    assert found is not None
    assert found["tese"] == "Recibo basta como justo titulo"
    assert found["relator"] == "Min. Nancy Andrighi"


def test_unique_constraint_tribunal_processo(tmp_path):
    """Mesmo (tribunal, processo_id) bate constraint UNIQUE."""
    conn = _abrir(tmp_path)
    j1 = Julgado(tribunal="STJ", processo_id="REsp X", area="imobiliario",
                 tese="T1", indexado_em="2026-05-26")
    j2 = Julgado(tribunal="STJ", processo_id="REsp X", area="imobiliario",
                 tese="T2", indexado_em="2026-05-26")
    row1 = j1.to_row()
    cols = [k for k in row1 if k != "id"]
    sql = f"INSERT INTO julgados ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})"
    conn.execute(sql, row1)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, j2.to_row())
        conn.commit()


def test_fts_busca_basica(tmp_path):
    """Insere 2 julgados; FTS5 acha por palavra."""
    conn = _abrir(tmp_path)
    julgados = [
        Julgado(tribunal="STJ", processo_id="A", area="imobiliario",
                tese="Usucapiao ordinaria com recibo de compra",
                ementa="trata de usucapiao", indexado_em="2026-05-26"),
        Julgado(tribunal="TJ-SP", processo_id="B", area="sucessorio",
                tese="Holding familiar e planejamento sucessorio",
                ementa="trata de holding", indexado_em="2026-05-26"),
    ]
    for j in julgados:
        row = j.to_row()
        cols = [k for k in row if k != "id"]
        conn.execute(
            f"INSERT INTO julgados ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})",
            row,
        )
    conn.commit()

    # busca por 'usucapiao'
    cur = conn.execute(
        "SELECT j.* FROM julgados j JOIN julgados_fts f ON j.id=f.rowid "
        "WHERE julgados_fts MATCH ?",
        ("usucapiao",),
    )
    hits = cur.fetchall()
    assert len(hits) == 1
    assert hits[0]["processo_id"] == "A"

    # busca por 'holding'
    cur = conn.execute(
        "SELECT j.* FROM julgados j JOIN julgados_fts f ON j.id=f.rowid "
        "WHERE julgados_fts MATCH ?",
        ("holding",),
    )
    hits = cur.fetchall()
    assert len(hits) == 1
    assert hits[0]["processo_id"] == "B"


def test_fts_normaliza_acentos(tmp_path):
    """tokenize='unicode61 remove_diacritics 2' faz busca sem acento bater com acento."""
    conn = _abrir(tmp_path)
    j = Julgado(tribunal="STJ", processo_id="X", area="imobiliario",
                tese="Usucapião ordinária na sucessão",
                indexado_em="2026-05-26")
    row = j.to_row()
    cols = [k for k in row if k != "id"]
    conn.execute(
        f"INSERT INTO julgados ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})",
        row,
    )
    conn.commit()

    # busca sem acento bate
    cur = conn.execute(
        "SELECT j.* FROM julgados j JOIN julgados_fts f ON j.id=f.rowid "
        "WHERE julgados_fts MATCH ?", ("usucapiao",),
    )
    assert cur.fetchone() is not None


def test_update_julgado_atualiza_fts(tmp_path):
    """Trigger AU sincroniza FTS quando linha e atualizada."""
    conn = _abrir(tmp_path)
    j = Julgado(tribunal="STJ", processo_id="X", area="imobiliario",
                tese="Tese antiga aqui", indexado_em="2026-05-26")
    row = j.to_row()
    cols = [k for k in row if k != "id"]
    conn.execute(
        f"INSERT INTO julgados ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})",
        row,
    )
    conn.commit()
    conn.execute("UPDATE julgados SET tese=? WHERE processo_id=?",
                 ("Tese nova holding", "X"))
    conn.commit()

    cur = conn.execute(
        "SELECT j.* FROM julgados j JOIN julgados_fts f ON j.id=f.rowid "
        "WHERE julgados_fts MATCH ?", ("holding",),
    )
    assert cur.fetchone() is not None  # FTS atualizou


def test_delete_julgado_remove_de_fts(tmp_path):
    """Trigger AD sincroniza FTS no delete."""
    conn = _abrir(tmp_path)
    j = Julgado(tribunal="STJ", processo_id="X", area="imobiliario",
                tese="Tese X", indexado_em="2026-05-26")
    row = j.to_row()
    cols = [k for k in row if k != "id"]
    conn.execute(
        f"INSERT INTO julgados ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})",
        row,
    )
    conn.commit()
    conn.execute("DELETE FROM julgados WHERE processo_id=?", ("X",))
    conn.commit()

    cur = conn.execute(
        "SELECT * FROM julgados_fts WHERE julgados_fts MATCH ?", ("Tese X",),
    )
    assert cur.fetchone() is None


def test_descartados_insert_e_recuperar(tmp_path):
    conn = _abrir(tmp_path)
    conn.execute(
        "INSERT INTO descartados (tribunal, processo_id, motivo, payload_json, descartado_em) "
        "VALUES (?,?,?,?,?)",
        ("STJ", "X", "area_fora_escopo", '{"area":"penal"}', "2026-05-26"),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM descartados WHERE processo_id=?", ("X",))
    found = cur.fetchone()
    assert found["motivo"] == "area_fora_escopo"


def test_fetch_log_unique_constraint(tmp_path):
    conn = _abrir(tmp_path)
    conn.execute(
        "INSERT INTO fetch_log (fonte, fetched_em, status, itens_inseridos) "
        "VALUES (?,?,?,?)",
        ("stj-informativo-789", "2026-05-26", "ok", 5),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO fetch_log (fonte, fetched_em, status, itens_inseridos) "
            "VALUES (?,?,?,?)",
            ("stj-informativo-789", "2026-05-27", "ok", 10),
        )
        conn.commit()


def test_julgado_from_row_roundtrip(tmp_path):
    """Insere via Julgado.to_row, recupera via Julgado.from_row."""
    conn = _abrir(tmp_path)
    original = Julgado(
        tribunal="STJ", processo_id="REsp 999", area="sucessorio",
        tese="Holding familiar valida",
        fundamentos=[{"fonte": "Art. 974 CC", "texto": "Empresarial"}],
        indexado_em="2026-05-26",
    )
    row = original.to_row()
    cols = [k for k in row if k != "id"]
    conn.execute(
        f"INSERT INTO julgados ({','.join(cols)}) VALUES ({','.join(':'+c for c in cols)})",
        row,
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM julgados WHERE processo_id=?", ("REsp 999",))
    found = dict(cur.fetchone())
    recuperado = Julgado.from_row(found)
    assert recuperado.tese == "Holding familiar valida"
    assert recuperado.fundamentos == [{"fonte": "Art. 974 CC", "texto": "Empresarial"}]
    assert recuperado.tribunal == "STJ"
