"""Testes da cadencia semanal automatica (Batch 5)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src import cadencia
from src.cadencia_state import CadenciaState
from src.config import load_config
from src.painel import alternar_cadencia, criar_app, status_cadencia
from src.wp_source import ArtigoFonte, CategoriaNaoEncontrada


# ---- helpers --------------------------------------------------------------

def _cfg(tmp_path):
    cfg = load_config()
    cfg.state_dir = tmp_path / "state"
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _artigo(post_id=1, titulo="Artigo X", cats=None):
    return ArtigoFonte(
        post_id=post_id,
        titulo=titulo,
        slug="",
        conteudo_html="",
        categorias=cats or [10],  # 10 = backlog id ficticio
        status="pending",
    )


# ---- CadenciaState --------------------------------------------------------

def test_cadencia_state_default_ativa(tmp_path):
    state = CadenciaState.carregar(tmp_path)
    assert state.ativa is True
    assert state.eventos_promovidos == {}


def test_cadencia_state_persiste(tmp_path):
    state = CadenciaState()
    state.ativa = False
    state.registrar_promocao(
        event_id="evt1",
        data_evento_iso="2026-05-28T10:00:00",
        titulo_evento="[NOV-BLOG] Publicacao",
        post_id=11750,
        post_titulo="Inventario",
    )
    state.salvar(tmp_path)

    recarregado = CadenciaState.carregar(tmp_path)
    assert recarregado.ativa is False
    assert "evt1" in recarregado.eventos_promovidos
    assert recarregado.eventos_promovidos["evt1"]["post_id"] == 11750


def test_cadencia_state_idempotencia(tmp_path):
    state = CadenciaState()
    state.registrar_promocao("evt1", "2026-01-01", "T", 1, "P")
    assert state.evento_ja_promovido("evt1")
    assert not state.evento_ja_promovido("evt2")


# ---- promover_artigo (atomico no WP) -------------------------------------

def test_promover_artigo_troca_categoria():
    wp = MagicMock()
    wp.update_post.return_value = {"id": 99, "link": "x"}
    artigo = _artigo(post_id=99, cats=[10, 50])  # 10=backlog, 50=outra
    cadencia.promover_artigo(wp, artigo, backlog_cat_id=10, fila_social_cat_id=20)
    chamada = wp.update_post.call_args
    assert chamada[0][1] == 99  # post_id
    cats_finais = chamada[0][2]["categories"]
    assert 10 not in cats_finais  # removeu backlog
    assert 20 in cats_finais       # adicionou fila social
    assert 50 in cats_finais       # preservou outra


def test_promover_artigo_nao_duplica_fila_social():
    """Se ja tem fila_social na lista, nao adiciona duas vezes."""
    wp = MagicMock()
    wp.update_post.return_value = {"id": 99, "link": "x"}
    artigo = _artigo(post_id=99, cats=[10, 20])  # ja tem fila social
    cadencia.promover_artigo(wp, artigo, backlog_cat_id=10, fila_social_cat_id=20)
    cats_finais = wp.update_post.call_args[0][2]["categories"]
    assert cats_finais.count(20) == 1


# ---- painel: toggle + status ---------------------------------------------

def test_alternar_cadencia_persiste(tmp_path):
    cfg = _cfg(tmp_path)
    alternar_cadencia(cfg, False)
    state = CadenciaState.carregar(cfg.state_dir)
    assert state.ativa is False
    alternar_cadencia(cfg, True)
    assert CadenciaState.carregar(cfg.state_dir).ativa is True


def test_status_cadencia_estrutura(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.cadencia_ativa = True
    cfg.cadencia_calendario = "Cal Test"
    cfg.cadencia_janela_horas = 24
    cfg.cadencia_filtro_titulo = "[X]"
    cfg.wp_categoria_backlog = "Backlog Teste"

    status = status_cadencia(cfg)
    assert status["ativa_painel"] is True  # default
    assert status["ativa_env"] is True
    assert status["calendario"] == "Cal Test"
    assert status["janela_horas"] == 24
    assert status["categoria_backlog"] == "Backlog Teste"
    assert status["historico"] == []
    assert status["total_promovidos"] == 0


def test_status_cadencia_com_historico(tmp_path):
    cfg = _cfg(tmp_path)
    state = CadenciaState()
    state.registrar_promocao("e1", "2026-05-28T10:00:00", "[NOV-BLOG] P", 1, "T1")
    state.registrar_promocao("e2", "2026-06-04T10:00:00", "[NOV-BLOG] P", 2, "T2")
    state.salvar(cfg.state_dir)

    status = status_cadencia(cfg)
    assert status["total_promovidos"] == 2
    assert len(status["historico"]) == 2


def test_rota_painel_renderiza_cadencia(tmp_path):
    cfg = _cfg(tmp_path)
    cliente = criar_app(cfg).test_client()
    resp = cliente.get("/")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "Cadência semanal" in corpo
    # botao de toggle aparece quando .env nao desativa
    assert "cadência" in corpo.lower()


def test_rota_toggle_alterna(tmp_path):
    cfg = _cfg(tmp_path)
    cliente = criar_app(cfg).test_client()
    # default = ativa
    resp = cliente.post("/cadencia/toggle", data={"ativa": "false"})
    assert resp.status_code in (302, 303)
    assert CadenciaState.carregar(cfg.state_dir).ativa is False
    # retoma
    resp = cliente.post("/cadencia/toggle", data={"ativa": "true"})
    assert CadenciaState.carregar(cfg.state_dir).ativa is True


# ---- cadencia.main: kill switches ----------------------------------------

def test_main_skipa_quando_env_desativado(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cfg.cadencia_ativa = False
    monkeypatch.setattr("src.cadencia.load_config", lambda: cfg)
    monkeypatch.setattr("src.cadencia.setup_logging", lambda _d: None)
    # nao deve nem instanciar CalendarClient
    monkeypatch.setattr(
        "src.cadencia.CalendarClient",
        lambda _g: pytest.fail("CalendarClient nao deveria ser chamado"),
    )
    assert cadencia.main() == 0


def test_main_skipa_quando_painel_desativado(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    cfg.cadencia_ativa = True
    state = CadenciaState()
    state.ativa = False
    state.salvar(cfg.state_dir)

    monkeypatch.setattr("src.cadencia.load_config", lambda: cfg)
    monkeypatch.setattr("src.cadencia.setup_logging", lambda _d: None)
    monkeypatch.setattr(
        "src.cadencia.CalendarClient",
        lambda _g: pytest.fail("CalendarClient nao deveria ser chamado"),
    )
    assert cadencia.main() == 0
    # marcou run mesmo desativado
    assert CadenciaState.carregar(cfg.state_dir).ultimo_run_iso != ""
