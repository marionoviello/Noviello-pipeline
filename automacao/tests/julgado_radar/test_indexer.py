"""Testes do indexer — upsert, dedup, fetch_log, descartados."""

from src.julgado_radar import db, indexer
from src.julgado_radar.models import Descartado, Julgado


def _abrir(tmp_path):
    return db.abrir(tmp_path)


def _julgado(tribunal="STJ", processo="REsp X", area="imobiliario", tese="Tese"):
    return Julgado(tribunal=tribunal, processo_id=processo, area=area, tese=tese)


def test_upsert_insere_quando_novo(tmp_path):
    conn = _abrir(tmp_path)
    id_, novo = indexer.upsert_julgado(conn, _julgado())
    assert novo is True
    assert id_ > 0


def test_upsert_atualiza_quando_existe(tmp_path):
    conn = _abrir(tmp_path)
    j = _julgado(tese="Tese antiga")
    id1, novo1 = indexer.upsert_julgado(conn, j)
    assert novo1 is True

    j2 = _julgado(tese="Tese nova")
    id2, novo2 = indexer.upsert_julgado(conn, j2)
    assert novo2 is False
    assert id2 == id1  # mesmo id (update, nao insert)

    row = conn.execute("SELECT tese FROM julgados WHERE id=?", (id1,)).fetchone()
    assert row["tese"] == "Tese nova"


def test_upsert_preenche_indexado_em(tmp_path):
    conn = _abrir(tmp_path)
    j = _julgado()
    j.indexado_em = ""  # forca preenchimento
    indexer.upsert_julgado(conn, j)
    assert j.indexado_em != ""


def test_registrar_descartado(tmp_path):
    conn = _abrir(tmp_path)
    d = Descartado(
        tribunal="STJ", processo_id="X", motivo="area_fora_escopo",
        payload={"area": "penal"},
    )
    id_ = indexer.registrar_descartado(conn, d)
    assert id_ > 0
    row = conn.execute("SELECT * FROM descartados WHERE id=?", (id_,)).fetchone()
    assert row["motivo"] == "area_fora_escopo"


def test_registrar_fetch_e_marcacao_ok(tmp_path):
    conn = _abrir(tmp_path)
    indexer.registrar_fetch(conn, "stj-informativo-789", "ok", itens_inseridos=5)
    assert indexer.fetch_ja_feito(conn, "stj-informativo-789") is True
    assert indexer.fetch_ja_feito(conn, "stj-informativo-800") is False


def test_registrar_fetch_status_erro_nao_marca_feito(tmp_path):
    conn = _abrir(tmp_path)
    indexer.registrar_fetch(conn, "x", "erro", erro="timeout")
    assert indexer.fetch_ja_feito(conn, "x") is False


def test_registrar_fetch_e_idempotente(tmp_path):
    """Re-registrar com a mesma fonte atualiza (sem duplicar linha)."""
    conn = _abrir(tmp_path)
    indexer.registrar_fetch(conn, "y", "erro", erro="timeout")
    indexer.registrar_fetch(conn, "y", "ok", itens_inseridos=3)
    cur = conn.execute("SELECT * FROM fetch_log WHERE fonte=?", ("y",))
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["itens_inseridos"] == 3


def test_indexar_batch_estatistica(tmp_path):
    conn = _abrir(tmp_path)
    julgados = [
        _julgado(processo="A"),
        _julgado(processo="B"),
        _julgado(processo="A", tese="atualizado"),  # mesmo (STJ, A) — atualiza
    ]
    stats = indexer.indexar_batch(conn, julgados)
    assert stats["inseridos"] == 2
    assert stats["atualizados"] == 1


def test_contar_por_tribunal_area(tmp_path):
    conn = _abrir(tmp_path)
    julgados = [
        _julgado(tribunal="STJ", processo="A", area="imobiliario"),
        _julgado(tribunal="STJ", processo="B", area="imobiliario"),
        _julgado(tribunal="STJ", processo="C", area="sucessorio"),
        _julgado(tribunal="TJ-SP", processo="D", area="urbanistico"),
    ]
    indexer.indexar_batch(conn, julgados)
    stats = indexer.contar_por_tribunal_area(conn)
    assert stats[("STJ", "imobiliario")] == 2
    assert stats[("STJ", "sucessorio")] == 1
    assert stats[("TJ-SP", "urbanistico")] == 1
