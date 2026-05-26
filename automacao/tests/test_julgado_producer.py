"""Testes do julgado_producer — orquestracao completa.

Calendar, Anthropic e renders sao mockados. Testes nao tocam rede nem
disparam Playwright real.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.julgado_producer import (
    detectar_e_extrair,
    main_julgado,
    montar_peca,
    pasta_da_semana,
    processar_revisao,
    processo_slug,
    semana_iso_de_iso_string,
)
from src.julgado_state import EstadoJulgado, JulgadoState, JulgadoStore


def _cfg(tmp_path) -> Config:
    """Config minima pra testar producer (paths reais, credentials fake)."""
    cfg = Config(
        project_root=tmp_path,
        automacao_dir=tmp_path / "automacao",
        producao_dir=tmp_path / "producao",
        publicado_dir=tmp_path / "publicado",
        state_dir=tmp_path / "state",
        logs_dir=tmp_path / "logs",
        templates_dir=tmp_path / "templates",
        enabled_channels=["instagram", "linkedin"],
        dry_run=True,
        email_aprovador="teste@teste.com",
        julgado_dir=tmp_path / "producao" / "julgados",
    )
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _dados_extraidos():
    return {
        "area": "Direito Imobiliario",
        "orgao": "STJ",
        "orgao_completo": "Terceira Turma do STJ",
        "turma": "3a Turma",
        "processo_id": "REsp 2.215.421/SE",
        "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi",
        "relator_curto": "Min. Nancy",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve...",
        "carimbo": "Unanimidade",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "Usucapiao..."}],
    }


# ===== Helpers puros =====

def test_semana_iso_de_iso_string_data_conhecida():
    # 26/05/2026 (terca) — semana ISO 22
    assert semana_iso_de_iso_string("2026-05-26T08:30:00-03:00") == (2026, 22)


def test_semana_iso_de_iso_string_so_data():
    assert semana_iso_de_iso_string("2026-05-26") == (2026, 22)


def test_pasta_da_semana_formato():
    base = Path("/tmp/julgados")
    assert pasta_da_semana(base, 22) == base / "sem-22"
    assert pasta_da_semana(base, 1) == base / "sem-01"


def test_processo_slug_normaliza():
    assert processo_slug("REsp 2.215.421/SE") == "resp-2-215-421-se"
    assert processo_slug("RE 1.234.567") == "re-1-234-567"
    assert processo_slug("AgRg em REsp 999/RJ") == "agrg-em-resp-999-rj"


# ===== Etapa A — detectar_e_extrair =====

def test_detectar_e_extrair_sem_eventos_no_op(tmp_path):
    cfg = _cfg(tmp_path)
    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = []
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    logger = MagicMock()
    detectar_e_extrair(cfg, cal, cli, store, logger)
    assert store.list_all() == []


def test_detectar_e_extrair_evento_ja_processado_skip(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = [{
        "id": "evt-1", "summary": "[NOV-MKT] LI 08h30 — Julgado",
        "start_iso": "2026-05-26T08:30:00-03:00", "end_iso": "",
    }]
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    store.save(JulgadoState(event_id="evt-1", semana_iso=22, ano_iso=2026))
    logger = MagicMock()
    detectar_e_extrair(cfg, cal, cli, store, logger)
    # Anthropic nao deve ser chamado
    cli.extrair_dados_julgado.assert_not_called()


def test_detectar_e_extrair_sem_pdf_grava_erro(tmp_path):
    cfg = _cfg(tmp_path)
    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = [{
        "id": "evt-1", "summary": "[NOV-MKT] LI 08h30 — Julgado",
        "start_iso": "2026-05-26T08:30:00-03:00", "end_iso": "",
    }]
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    logger = MagicMock()
    # NAO cria pasta sem-22 — deve gravar estado em ERRO
    detectar_e_extrair(cfg, cal, cli, store, logger)
    pecas = store.list_all()
    assert len(pecas) == 1
    assert pecas[0].status == EstadoJulgado.ERRO
    assert pecas[0].erro_mensagem  # nao vazio
    cli.extrair_dados_julgado.assert_not_called()


def test_detectar_e_extrair_pipeline_completo(tmp_path, monkeypatch):
    """Calendar -> PDF localizado -> parse mockado -> copy gerada -> state OK."""
    cfg = _cfg(tmp_path)
    pasta_sem = cfg.julgado_dir / "sem-22"
    pasta_sem.mkdir(parents=True)
    pdf = pasta_sem / "acordao.pdf"
    # PDF dummy (em branco) — extrair_texto_pdf vai devolver "" mas mockamos
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    with open(pdf, "wb") as f:
        w.write(f)

    # Mocka _extrair_texto_pdf pra devolver texto nao-vazio
    monkeypatch.setattr(
        "src.julgado_parser._extrair_texto_pdf",
        lambda p: "TEXTO COMPLETO DO ACORDAO STJ REsp 2.215.421",
    )

    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = [{
        "id": "evt-1", "summary": "[NOV-MKT] LI 08h30 — Julgado",
        "start_iso": "2026-05-26T08:30:00-03:00", "end_iso": "",
    }]

    cli = MagicMock()
    cli.extrair_dados_julgado.return_value = _dados_extraidos()
    cli.gerar_carrossel_julgado.return_value = {
        "slides": [{"titulo": "Capa", "corpo": "STJ"}],
        "legenda": "legenda", "hashtags": ["#x"], "_ai_tells": [],
    }
    cli.gerar_linkedin_julgado.return_value = "Post LinkedIn"

    store = JulgadoStore(cfg.state_dir)
    logger = MagicMock()

    detectar_e_extrair(cfg, cal, cli, store, logger)

    pecas = store.list_all()
    assert len(pecas) == 1
    estado = pecas[0]
    assert estado.event_id == "evt-1"
    assert estado.semana_iso == 22
    assert estado.ano_iso == 2026
    assert estado.status == EstadoJulgado.AGUARDANDO_REVISAO
    assert estado.dados_julgado["processo_id"] == "REsp 2.215.421/SE"
    assert estado.copy_carrossel["legenda"] == "legenda"
    assert estado.texto_linkedin == "Post LinkedIn"
    assert estado.pdf_path == str(pdf)


# ===== Etapa B — processar_revisao =====

def test_processar_revisao_aguardando_sem_decisao_no_op(tmp_path):
    cfg = _cfg(tmp_path)
    cli = MagicMock()
    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={"processo_id": "REsp X", "tese": "T"},
    )
    store.save(estado)
    logger = MagicMock()
    processar_revisao(estado, cfg, cli, store, logger)
    cli.gerar_carrossel_julgado.assert_not_called()


def test_processar_revisao_ajustar_regenera(tmp_path):
    cfg = _cfg(tmp_path)
    cli = MagicMock()
    cli.gerar_carrossel_julgado.return_value = {
        "slides": [{"titulo": "X", "corpo": "Y"}],
        "legenda": "nova legenda", "hashtags": [], "_ai_tells": [],
    }
    cli.gerar_linkedin_julgado.return_value = "novo linkedin"

    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={"processo_id": "REsp X", "tese": "T", "fundamentos": []},
        decisao="ajustar", ajuste_texto="trocar slide 1",
    )
    store.save(estado)
    logger = MagicMock()

    processar_revisao(estado, cfg, cli, store, logger)

    cli.gerar_carrossel_julgado.assert_called_once()
    cli.gerar_linkedin_julgado.assert_called_once()
    recarregado = store.load("x")
    assert recarregado.decisao == ""
    assert recarregado.ajuste_texto == ""
    assert recarregado.tentativas_ajuste == 1
    assert recarregado.copy_carrossel["legenda"] == "nova legenda"
    assert recarregado.texto_linkedin == "novo linkedin"


# ===== montar_peca =====

def _setup_renders_mockados(monkeypatch, jpgs_carrossel, jpg_card):
    """Mocka carousel_render.renderizar e julgado_card_render.renderizar_card."""
    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar",
        lambda slides, pasta, templates, script, **kw: jpgs_carrossel,
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda dados, pasta, templates, script, **kw: jpg_card,
    )


def test_montar_peca_escreve_manifest_correto(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    pasta_peca = cfg.producao_dir / "2026-S22" / "julgado-resp-2-215-421-se"
    pasta_peca.mkdir(parents=True)
    jpg_card = pasta_peca / "card-li.jpg"
    jpg_card.write_bytes(b"fake-jpg")
    jpgs_carrossel = []
    for i in range(1, 4):
        p = pasta_peca / f"slide{i:02d}.jpg"
        p.write_bytes(b"fake-jpg")
        jpgs_carrossel.append(p)

    _setup_renders_mockados(monkeypatch, jpgs_carrossel, jpg_card)

    estado = JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.APROVADO,
        dados_julgado={
            "area": "Direito Imobiliario", "orgao": "STJ",
            "processo_id": "REsp 2.215.421/SE", "tese": "T",
            "fundamentos": [],
        },
        copy_carrossel={
            "slides": [
                {"titulo": "Capa", "corpo": "C"},
                {"titulo": "S2", "corpo": "C2"},
                {"titulo": "CTA", "corpo": "C3"},
            ],
            "legenda": "legenda do post",
            "hashtags": ["#x", "#y"],
        },
        texto_linkedin="Post LinkedIn aqui",
    )
    logger = MagicMock()
    pasta = montar_peca(estado, cfg, logger)

    manifest_path = pasta / "MANIFEST.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["tipo"] == "julgado"
    assert manifest["pilar"] == "Julgado da Semana"
    assert manifest["peca_id"] == "julgado-2026-S22-resp-2-215-421-se"
    assert manifest["status"] == "pronta_para_aprovacao"
    assert manifest["validacoes"]["oab_205"] == "aprovado"
    assert manifest["validacoes"]["marca"] == "v2-conforme"

    ig = manifest["ativos"]["instagram"]
    assert len(ig["imagens"]) == 3
    assert ig["tipo_post"] == "carrossel"
    assert ig["hashtags"] == ["#x", "#y"]
    assert Path(ig["legenda"]).exists()
    assert "legenda do post" in Path(ig["legenda"]).read_text(encoding="utf-8")

    li = manifest["ativos"]["linkedin"]
    assert Path(li["imagem"]).exists()
    assert Path(li["texto"]).exists()
    assert "Post LinkedIn aqui" in Path(li["texto"]).read_text(encoding="utf-8")

    # NAO tem wordpress (Mario faz blog manual)
    assert "wordpress" not in manifest["ativos"]


def test_montar_peca_slides_recebem_4_campos(tmp_path, monkeypatch):
    """carousel_render.renderizar e chamado com slides ja contendo
    area/selo_tribunal/processo_id/carimbo (mapeados do dados_julgado)."""
    cfg = _cfg(tmp_path)
    pasta_peca = cfg.producao_dir / "2026-S22" / "julgado-resp-x"
    pasta_peca.mkdir(parents=True)
    jpg_card = pasta_peca / "card-li.jpg"
    jpg_card.write_bytes(b"x")
    jpgs = [pasta_peca / "slide01.jpg"]
    jpgs[0].write_bytes(b"x")

    slides_capturados = {"slides": None}

    def fake_renderizar(slides, pasta, templates, script, **kw):
        slides_capturados["slides"] = slides
        return jpgs

    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar", fake_renderizar,
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda *a, **kw: jpg_card,
    )

    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.APROVADO,
        dados_julgado={
            "area": "Direito Imobiliario", "orgao": "STJ",
            "processo_id": "REsp X", "carimbo": "Unanimidade",
            "tese": "T", "fundamentos": [],
        },
        copy_carrossel={
            # IA nao incluiu os 4 campos no slide — montar_peca injeta do dados
            "slides": [{"titulo": "Capa", "corpo": "C"}],
            "legenda": "L", "hashtags": [],
        },
        texto_linkedin="LI",
    )
    montar_peca(estado, cfg, MagicMock())

    s = slides_capturados["slides"][0]
    assert s["area"] == "Direito Imobiliario"
    assert s["selo_tribunal"] == "STJ"  # orgao -> selo_tribunal no slide
    assert s["processo_id"] == "REsp X"
    assert s["carimbo"] == "Unanimidade"


def test_montar_peca_preserva_campos_quando_ia_ja_preencheu(tmp_path, monkeypatch):
    """Se a IA ja preencheu, montar_peca nao sobrescreve."""
    cfg = _cfg(tmp_path)
    pasta_peca = cfg.producao_dir / "2026-S22" / "julgado-resp-y"
    pasta_peca.mkdir(parents=True)
    jpgs = [pasta_peca / "slide01.jpg"]
    jpgs[0].write_bytes(b"x")
    jpg_card = pasta_peca / "card-li.jpg"
    jpg_card.write_bytes(b"x")

    slides_capturados = {"slides": None}
    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar",
        lambda slides, *a, **kw: (slides_capturados.__setitem__("slides", slides) or jpgs),
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda *a, **kw: jpg_card,
    )

    estado = JulgadoState(
        event_id="y", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.APROVADO,
        dados_julgado={
            "area": "Direito A", "orgao": "STJ",
            "processo_id": "REsp Y", "carimbo": "Unanimidade",
            "tese": "T", "fundamentos": [],
        },
        copy_carrossel={
            "slides": [{
                "titulo": "Capa", "corpo": "C",
                "area": "Direito B (preferido)",
                "selo_tribunal": "STF",
                "processo_id": "RE Y (preferido)",
                "carimbo": "Maioria",
            }],
            "legenda": "L", "hashtags": [],
        },
        texto_linkedin="LI",
    )
    montar_peca(estado, cfg, MagicMock())

    s = slides_capturados["slides"][0]
    assert s["area"] == "Direito B (preferido)"
    assert s["selo_tribunal"] == "STF"
    assert s["processo_id"] == "RE Y (preferido)"
    assert s["carimbo"] == "Maioria"


def test_processar_revisao_aprovar_chama_montar_peca(tmp_path, monkeypatch):
    """decisao=aprovar dispara montar_peca e estado vira PECA_MONTADA."""
    cfg = _cfg(tmp_path)
    pasta_alvo = cfg.producao_dir / "2026-S22" / "julgado-resp-x"
    pasta_alvo.mkdir(parents=True)
    (pasta_alvo / "card-li.jpg").write_bytes(b"x")
    (pasta_alvo / "slide01.jpg").write_bytes(b"x")

    monkeypatch.setattr(
        "src.julgado_producer.carousel_render.renderizar",
        lambda *a, **kw: [pasta_alvo / "slide01.jpg"],
    )
    monkeypatch.setattr(
        "src.julgado_producer.julgado_card_render.renderizar_card",
        lambda *a, **kw: pasta_alvo / "card-li.jpg",
    )

    store = JulgadoStore(cfg.state_dir)
    estado = JulgadoState(
        event_id="x", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        decisao="aprovar",
        dados_julgado={
            "area": "X", "orgao": "STJ", "processo_id": "REsp X",
            "carimbo": "Unanimidade", "tese": "T", "fundamentos": [],
        },
        copy_carrossel={"slides": [{"titulo": "Capa", "corpo": "C"}], "legenda": "L", "hashtags": []},
        texto_linkedin="LI",
    )
    store.save(estado)
    cli = MagicMock()

    processar_revisao(estado, cfg, cli, store, MagicMock())

    recarregado = store.load("x")
    assert recarregado.status == EstadoJulgado.PECA_MONTADA


# ===== main_julgado =====

def test_main_julgado_orquestra_etapa_b_depois_a(tmp_path):
    """Etapa B (revisao) corre antes da Etapa A (detectar)."""
    cfg = _cfg(tmp_path)
    store = JulgadoStore(cfg.state_dir)
    store.save(JulgadoState(
        event_id="velho", semana_iso=20, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
    ))

    cal = MagicMock()
    cal.listar_eventos_futuros.return_value = []
    cli = MagicMock()
    logger = MagicMock()

    main_julgado(cfg, cli, cal, store, logger)

    # Estado intacto (sem decisao -> no-op em Etapa B; sem evento -> no-op em A)
    assert store.load("velho").status == EstadoJulgado.AGUARDANDO_REVISAO


def test_main_julgado_calendar_quebrado_nao_explode(tmp_path):
    """Se calendar levanta, main_julgado segue (log de erro) — nao trava o producer."""
    cfg = _cfg(tmp_path)
    store = JulgadoStore(cfg.state_dir)

    cal = MagicMock()
    cal.listar_eventos_futuros.side_effect = RuntimeError("calendar down")
    cli = MagicMock()
    logger = MagicMock()

    # nao levanta
    main_julgado(cfg, cli, cal, store, logger)
