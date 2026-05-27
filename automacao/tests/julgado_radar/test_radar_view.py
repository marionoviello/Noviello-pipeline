"""Testes do radar_view — busca pra view + materializar julgado na pasta."""

import datetime as _dt
import json
from pathlib import Path

import pytest

from src.julgado_radar import db, indexer, radar_view
from src.julgado_radar.models import Julgado


def _seed_db(tmp_path):
    conn = db.abrir(tmp_path)
    julgados = [
        Julgado(
            tribunal="STJ", processo_id="REsp 100", area="imobiliario",
            tese="ITBI nao incide na integralizacao", ementa="Detalhes ITBI...",
            classe="Recurso Especial", data_julgamento="2024-03-10",
            relator="Min. X",
        ),
        Julgado(
            tribunal="TJ-SP", processo_id="1234-2024", area="urbanistico",
            tese="REURB exige laudo previo",
            classe="Apelacao", data_julgamento="2023-08-12",
            relator="Des. Y",
        ),
    ]
    indexer.indexar_batch(conn, julgados)
    conn.close()


# ===== buscar_para_view =====

def test_buscar_para_view_sem_filtros(tmp_path):
    _seed_db(tmp_path)
    ctx = radar_view.buscar_para_view(tmp_path)
    assert ctx["total"] == 2
    assert len(ctx["resultados"]) == 2
    assert ctx["areas_validas"] == ["urbanistico", "imobiliario", "sucessorio"]
    assert "STJ" in ctx["tribunais_validos"]
    assert "TJ-SP" in ctx["tribunais_validos"]


def test_buscar_para_view_termo_filtra(tmp_path):
    _seed_db(tmp_path)
    ctx = radar_view.buscar_para_view(tmp_path, termo="ITBI")
    assert ctx["total"] == 1
    assert "ITBI" in ctx["resultados"][0]["tese"]


def test_buscar_para_view_anos_disponiveis(tmp_path):
    _seed_db(tmp_path)
    ctx = radar_view.buscar_para_view(tmp_path)
    assert 2024 in ctx["anos_validos"]
    assert 2023 in ctx["anos_validos"]
    # ordenado desc
    assert ctx["anos_validos"][0] == 2024


def test_buscar_para_view_filtros_combinados(tmp_path):
    _seed_db(tmp_path)
    ctx = radar_view.buscar_para_view(
        tmp_path, area="urbanistico", tribunal="TJ-SP",
    )
    assert ctx["total"] == 1
    assert ctx["resultados"][0]["tribunal"] == "TJ-SP"


def test_buscar_para_view_resultado_tem_ementa_resumida(tmp_path):
    _seed_db(tmp_path)
    ctx = radar_view.buscar_para_view(tmp_path, termo="ITBI")
    item = ctx["resultados"][0]
    assert "ementa_resumida" in item
    assert "tese" in item
    assert "processo_id" in item


def test_buscar_para_view_ementa_longa_truncada(tmp_path):
    """Ementa > 300 chars vira preview + '...'."""
    conn = db.abrir(tmp_path)
    longa = "ementa muito longa aqui " * 50  # ~1200 chars
    indexer.upsert_julgado(conn, Julgado(
        tribunal="STJ", processo_id="X", area="imobiliario",
        tese="T", ementa=longa,
    ))
    conn.close()
    ctx = radar_view.buscar_para_view(tmp_path)
    assert ctx["resultados"][0]["ementa_resumida"].endswith("...")
    assert len(ctx["resultados"][0]["ementa_resumida"]) < 320


# ===== semana_iso_atual =====

def test_semana_iso_atual_data_conhecida():
    """26/05/2026 e semana ISO 22 de 2026."""
    ano, sem = radar_view.semana_iso_atual(_dt.date(2026, 5, 26))
    assert ano == 2026
    assert sem == 22


def test_semana_iso_atual_sem_arg_usa_hoje():
    """Sem argumento, devolve algo consistente."""
    ano, sem = radar_view.semana_iso_atual()
    assert 2020 <= ano <= 2050
    assert 1 <= sem <= 53


# ===== materializar_julgado =====

def test_materializar_julgado_cria_pasta_e_arquivos(tmp_path):
    _seed_db(tmp_path)
    julgado_dir = tmp_path / "producao" / "julgados"
    resultado = radar_view.materializar_julgado(
        tmp_path, julgado_id=1, julgado_dir=julgado_dir,
        hoje=_dt.date(2026, 5, 26),
    )
    assert Path(resultado["pasta"]).exists()
    assert Path(resultado["pdf_path"]).exists()
    assert Path(resultado["json_path"]).exists()
    assert resultado["semana_iso"] == 22
    assert resultado["ano_iso"] == 2026


def test_materializar_julgado_json_tem_campos_corretos(tmp_path):
    _seed_db(tmp_path)
    julgado_dir = tmp_path / "producao" / "julgados"
    resultado = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
    )
    dados = json.loads(Path(resultado["json_path"]).read_text(encoding="utf-8"))
    assert dados["tribunal"] == "STJ"
    assert dados["processo_id"] == "REsp 100"
    assert dados["area"] == "imobiliario"
    assert dados["tese"] == "ITBI nao incide na integralizacao"


def test_materializar_julgado_marca_usado(tmp_path):
    _seed_db(tmp_path)
    julgado_dir = tmp_path / "producao" / "julgados"
    radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
    )
    # Re-abre e confere
    conn = db.abrir(tmp_path)
    cur = conn.execute("SELECT usado_em_post FROM julgados WHERE id=?", (1,))
    row = cur.fetchone()
    conn.close()
    assert row["usado_em_post"] == "radar-sem-2026-S22"


def test_materializar_julgado_pasta_correta_por_semana(tmp_path):
    _seed_db(tmp_path)
    julgado_dir = tmp_path / "producao" / "julgados"
    # semana 1 de 2025 (dezembro 2024 cai na sem-01 de 2025 dependendo do dia)
    resultado = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2025, 1, 6),  # segunda-feira
    )
    assert Path(resultado["pasta"]).name == "sem-02"  # ISO week 2 of 2025


def test_materializar_julgado_id_inexistente_levanta(tmp_path):
    _seed_db(tmp_path)
    with pytest.raises(radar_view.RadarViewError):
        radar_view.materializar_julgado(
            tmp_path, 99999, tmp_path / "x",
            hoje=_dt.date(2026, 5, 26),
        )


def test_materializar_julgado_usa_pdf_local_quando_existe(tmp_path):
    """Se julgado tem pdf_local valido, copia esse arquivo."""
    pdf_origem = tmp_path / "origem.pdf"
    pdf_origem.write_bytes(b"%PDF-1.4 origem")

    conn = db.abrir(tmp_path)
    indexer.upsert_julgado(conn, Julgado(
        tribunal="STJ", processo_id="X", area="imobiliario", tese="T",
        pdf_local=str(pdf_origem),
    ))
    conn.close()

    julgado_dir = tmp_path / "producao" / "julgados"
    resultado = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
    )
    assert Path(resultado["pdf_path"]).read_bytes() == b"%PDF-1.4 origem"


def test_materializar_julgado_placeholder_quando_sem_pdf(tmp_path):
    """Sem pdf_local nem url_fonte, gera texto placeholder."""
    _seed_db(tmp_path)
    julgado_dir = tmp_path / "producao" / "julgados"
    resultado = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
    )
    conteudo = Path(resultado["pdf_path"]).read_text(encoding="utf-8")
    assert "JULGADO: STJ REsp 100" in conteudo
    assert "ITBI" in conteudo  # tese


def test_materializar_julgado_baixa_pdf_quando_dado(tmp_path):
    """baixar_pdf injetavel é usado quando ha url_fonte e nao ha pdf_local."""
    conn = db.abrir(tmp_path)
    indexer.upsert_julgado(conn, Julgado(
        tribunal="STJ", processo_id="X", area="imobiliario", tese="T",
        url_fonte="https://stj/x.pdf",
    ))
    conn.close()

    def fake_download(url, pasta):
        destino = pasta / "x-baixado.pdf"
        destino.write_bytes(b"%PDF baixado")
        return destino

    julgado_dir = tmp_path / "producao" / "julgados"
    resultado = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
        baixar_pdf=fake_download,
    )
    assert Path(resultado["pdf_path"]).read_bytes() == b"%PDF baixado"


def test_materializar_julgado_idempotente(tmp_path):
    """Materializar 2x — preserva o PDF da primeira vez."""
    _seed_db(tmp_path)
    julgado_dir = tmp_path / "producao" / "julgados"
    r1 = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
    )
    conteudo_original = Path(r1["pdf_path"]).read_bytes()

    r2 = radar_view.materializar_julgado(
        tmp_path, 1, julgado_dir, hoje=_dt.date(2026, 5, 26),
    )
    assert r2["ja_existia"] is True
    # PDF NAO foi sobrescrito
    assert Path(r2["pdf_path"]).read_bytes() == conteudo_original
