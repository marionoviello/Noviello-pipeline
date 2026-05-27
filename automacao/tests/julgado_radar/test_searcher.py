"""Testes do searcher — busca FTS5 + filtros + ranking."""

import pytest

from src.julgado_radar import db, indexer, searcher
from src.julgado_radar.models import Julgado


def _abrir(tmp_path):
    return db.abrir(tmp_path)


def _seed(conn):
    """Popula DB com julgados variados pra exercitar filtros e FTS."""
    julgados = [
        Julgado(
            tribunal="STJ", processo_id="REsp 100", area="imobiliario",
            tese="Usucapiao ordinaria com recibo de compra basta como justo titulo",
            ementa="trata de usucapiao ordinaria, recibo de compra serve",
            classe="Recurso Especial", data_julgamento="2024-03-10",
        ),
        Julgado(
            tribunal="STJ", processo_id="REsp 200", area="sucessorio",
            tese="Holding familiar nao caracteriza fraude por si so",
            ementa="planejamento sucessorio via holding e licito",
            classe="Recurso Especial", data_julgamento="2024-08-15",
        ),
        Julgado(
            tribunal="TJ-SP", processo_id="1234567-89.2024.8.26.0100",
            area="imobiliario",
            tese="ITBI nao incide sobre integralizacao de capital com imoveis",
            ementa="ITBI integralizacao de capital",
            classe="Apelacao Civel", data_julgamento="2024-04-22",
        ),
        Julgado(
            tribunal="TJ-SP", processo_id="9999999-99.2023.8.26.0100",
            area="urbanistico",
            tese="REURB-E sem regularizacao previa do parcelamento e nula",
            ementa="REURB regularizacao fundiaria parcelamento solo",
            classe="Apelacao Civel", data_julgamento="2023-11-05",
        ),
    ]
    indexer.indexar_batch(conn, julgados)


# ===== buscas basicas =====

def test_buscar_termo_simples(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "usucapiao")
    assert len(hits) == 1
    assert hits[0].processo_id == "REsp 100"


def test_buscar_ignora_acentos(tmp_path):
    """Tokenize unicode61 + remove_diacritics=2 normaliza."""
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "usucapião")
    assert len(hits) == 1


def test_buscar_caso_real_ITBI(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "ITBI")
    assert len(hits) == 1
    assert "ITBI" in hits[0].tese


def test_buscar_termo_composto_AND_implicito(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "holding familiar")
    assert len(hits) == 1
    assert "holding" in hits[0].tese.lower()


def test_buscar_termo_inexistente(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "criptomoeda")
    assert hits == []


def test_buscar_termo_vazio_devolve_top_por_data(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "")
    assert len(hits) == 4
    # mais novo primeiro
    assert hits[0].data_julgamento == "2024-08-15"


def test_buscar_aplica_limit(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "", limit=2)
    assert len(hits) == 2


# ===== filtros combinados =====

def test_buscar_filtra_por_area(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "", area="imobiliario")
    assert {h.area for h in hits} == {"imobiliario"}
    assert len(hits) == 2


def test_buscar_filtra_por_tribunal(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "", tribunal="TJ-SP")
    assert {h.tribunal for h in hits} == {"TJ-SP"}


def test_buscar_filtra_por_ano(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "", ano=2023)
    assert len(hits) == 1
    assert hits[0].data_julgamento == "2023-11-05"


def test_buscar_combina_termo_e_filtros(tmp_path):
    """Termo 'usucapiao' + area imobiliario + STJ — encontra REsp 100."""
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "usucapiao", area="imobiliario", tribunal="STJ")
    assert len(hits) == 1
    assert hits[0].processo_id == "REsp 100"


def test_buscar_combina_termo_e_filtros_sem_match(tmp_path):
    """Termo 'usucapiao' + area sucessorio = vazio."""
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "usucapiao", area="sucessorio")
    assert hits == []


def test_buscar_filtra_por_classe(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    hits = searcher.buscar(conn, "", classe="Apelacao")
    assert all("apela" in h.classe.lower() for h in hits)
    assert len(hits) == 2


# ===== robustez do sanitizer FTS =====

def test_buscar_sanitiza_aspas_que_quebrariam_fts(tmp_path):
    """Aspas no termo nao devem quebrar a query."""
    conn = _abrir(tmp_path)
    _seed(conn)
    # nao explode mesmo com chars problematicos
    hits = searcher.buscar(conn, 'ITBI "(*)')
    # busca por 'ITBI' funciona; resto e sanitizado
    assert any("ITBI" in h.tese for h in hits)


def test_buscar_termo_curto_descartado(tmp_path):
    """Tokens de 1 letra sao descartados pelo sanitizer."""
    conn = _abrir(tmp_path)
    _seed(conn)
    # 'a usucapiao b' — a e b sao descartados, sobra 'usucapiao'
    hits = searcher.buscar(conn, "a usucapiao b")
    assert len(hits) == 1


# ===== contar e get_por_id =====

def test_contar_total(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    assert searcher.contar(conn) == 4


def test_contar_por_area(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    assert searcher.contar(conn, area="imobiliario") == 2
    assert searcher.contar(conn, area="urbanistico") == 1


def test_contar_por_tribunal_e_area(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    assert searcher.contar(conn, tribunal="STJ", area="imobiliario") == 1
    assert searcher.contar(conn, tribunal="TJ-SP", area="imobiliario") == 1


def test_get_por_id(tmp_path):
    conn = _abrir(tmp_path)
    _seed(conn)
    julgado = searcher.get_por_id(conn, 1)
    assert julgado is not None
    assert julgado.processo_id == "REsp 100"


def test_get_por_id_inexistente(tmp_path):
    conn = _abrir(tmp_path)
    assert searcher.get_por_id(conn, 9999) is None
