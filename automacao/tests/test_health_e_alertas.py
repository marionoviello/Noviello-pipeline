"""Testes do healthcheck e alertas (F2)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src import alertas, health, heartbeat
from src.config import load_config


def _cfg(tmp_path):
    cfg = load_config()
    cfg.state_dir = tmp_path / "state"
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.email_aprovador = "mario@noviello.adv.br"
    return cfg


# ---- heartbeat ------------------------------------------------------------

def test_heartbeat_bate_e_le(tmp_path):
    heartbeat.bater(tmp_path, "watcher")
    iso = heartbeat.ler(tmp_path, "watcher")
    assert iso
    assert heartbeat.idade_segundos(iso) < 5


def test_heartbeat_nunca_rodou(tmp_path):
    assert heartbeat.ler(tmp_path, "watcher") is None
    assert heartbeat.idade_segundos(None) == float("inf")


def test_heartbeat_idade_de_iso_antigo():
    antigo = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    idade = heartbeat.idade_segundos(antigo)
    assert 3500 < idade < 3700


# ---- health ---------------------------------------------------------------

def test_health_componente_nunca_rodou(tmp_path):
    cfg = _cfg(tmp_path)
    status = health._status_componente(cfg.state_dir, "watcher")
    assert status["status"] == "nunca_rodou"
    assert status["ultimo_iso"] == ""


def test_health_componente_ok(tmp_path):
    cfg = _cfg(tmp_path)
    heartbeat.bater(cfg.state_dir, "watcher")
    status = health._status_componente(cfg.state_dir, "watcher")
    assert status["status"] == "ok"
    assert status["idade_segundos"] < 5


def test_health_geral_estrutura(tmp_path):
    cfg = _cfg(tmp_path)
    snapshot = health.status_geral(cfg)
    assert "ok" in snapshot
    assert "componentes" in snapshot
    assert "pecas" in snapshot
    assert "circuit" in snapshot
    assert "cadencia" in snapshot
    # 1a execucao: tudo nunca_rodou, ainda assim ok=True (nao quebra primeiro deploy)
    assert snapshot["ok"] is True


def test_health_geral_degradado_se_parado(tmp_path):
    cfg = _cfg(tmp_path)
    # simula heartbeat antigo (mais que limite warn de watcher = 600s)
    hb_dir = cfg.state_dir / "heartbeat"
    hb_dir.mkdir(parents=True, exist_ok=True)
    antigo = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    (hb_dir / "watcher.txt").write_text(antigo, encoding="utf-8")
    snapshot = health.status_geral(cfg)
    assert snapshot["componentes"]["watcher"]["status"] == "parado"
    assert snapshot["ok"] is False


# ---- alertas --------------------------------------------------------------

def test_alertas_throttle_primeira_vez(tmp_path):
    cfg = _cfg(tmp_path)
    assert alertas.deve_alertar(cfg.state_dir, "tipo_X", "k1", "critico") is True


def test_alertas_throttle_bloqueia_repeticao(tmp_path):
    cfg = _cfg(tmp_path)
    gmail = MagicMock()
    enviou = alertas.alertar(cfg, gmail, "tipo_X", "k1",
                              titulo="T", corpo="C", gravidade="critico")
    assert enviou is True
    gmail.send_message.assert_called_once()
    # 2a tentativa imediata: throttle bloqueia
    enviou2 = alertas.alertar(cfg, gmail, "tipo_X", "k1",
                               titulo="T2", corpo="C2", gravidade="critico")
    assert enviou2 is False
    assert gmail.send_message.call_count == 1  # nao chamou de novo


def test_alertas_chaves_diferentes_nao_se_bloqueiam(tmp_path):
    cfg = _cfg(tmp_path)
    gmail = MagicMock()
    alertas.alertar(cfg, gmail, "circuit_pausado", "instagram",
                    titulo="IG", corpo="x", gravidade="critico")
    alertas.alertar(cfg, gmail, "circuit_pausado", "linkedin",
                    titulo="LI", corpo="x", gravidade="critico")
    assert gmail.send_message.call_count == 2


def test_alertas_persiste_historico(tmp_path):
    cfg = _cfg(tmp_path)
    gmail = MagicMock()
    alertas.alertar(cfg, gmail, "tipo_Y", "k", "T", "C", "alto")
    dados = alertas._load(cfg.state_dir)
    assert len(dados["historico"]) == 1
    assert dados["historico"][0]["tipo"] == "tipo_Y"
    assert "tipo_Y::k" in dados["ultimos"]


def test_alertas_falha_envio_nao_persiste(tmp_path):
    cfg = _cfg(tmp_path)
    gmail = MagicMock()
    gmail.send_message.side_effect = Exception("smtp down")
    enviou = alertas.alertar(cfg, gmail, "tipo_Z", "k", "T", "C", "alto")
    assert enviou is False
    dados = alertas._load(cfg.state_dir)
    assert dados.get("historico", []) == []  # nao registrou
