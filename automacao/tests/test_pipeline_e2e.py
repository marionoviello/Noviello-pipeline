"""Testes ponta-a-ponta: watcher -> decisao do painel -> poller.

DRY_RUN ligado: os publishers simulam. Nenhuma API real e tocada.
"""

import json

from src.config import load_config
from src.logger import get_logger, setup_logging
from src.painel import registrar_decisao
from src.poller import processar_estado
from src.state import Estado, StateStore
from src.watcher import processar_manifest
from tests.helpers import FakeGmail, criar_peca_dir

PECA_ID = "2026-S20-teste"


def _ambiente(tmp_path, canais=("instagram", "wordpress", "linkedin")):
    cfg = load_config()
    cfg.producao_dir = tmp_path / "producao"
    cfg.publicado_dir = tmp_path / "producao" / "_publicado"
    cfg.state_dir = tmp_path / "state"
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir = tmp_path / "logs"
    cfg.enabled_channels = list(canais)
    cfg.dry_run = True
    cfg.google = {}  # sem Google -> arquivar pula o Calendar
    cfg.meta = {"page_token": "t", "ig_business_id": "1", "page_id": "2"}
    cfg.wordpress = {"user": "m", "app_password_noviello": "p", "app_password_imobiliario": "p"}
    cfg.linkedin = {"access_token": "t", "refresh_token": "r", "person_urn": "u"}

    setup_logging(cfg.logs_dir)
    logger = get_logger("teste-e2e")
    store = StateStore(cfg.state_dir)
    gmail = FakeGmail()
    mpath = criar_peca_dir(cfg.producao_dir / "2026-S20", canais=canais)
    return cfg, gmail, store, logger, mpath


def test_fluxo_aprovacao_completo(tmp_path):
    cfg, gmail, store, logger, mpath = _ambiente(tmp_path)

    # watcher registra a peca
    processar_manifest(mpath, cfg, gmail, store, logger)
    assert store.load(PECA_ID).status == Estado.AGUARDANDO_APROVACAO

    # painel: Mario clica Aprovar
    registrar_decisao(cfg, "final", PECA_ID, "aprovar")

    # poller le a decisao e publica
    processar_estado(store.load(PECA_ID), cfg, gmail, store, logger)

    assert store.exists(PECA_ID) is False  # estado limpo
    arquivadas = list(cfg.publicado_dir.glob(f"{PECA_ID}-*"))
    assert len(arquivadas) == 1
    assert (arquivadas[0] / "PROOF.json").exists()


def test_fluxo_ajuste(tmp_path):
    cfg, gmail, store, logger, mpath = _ambiente(tmp_path)
    processar_manifest(mpath, cfg, gmail, store, logger)

    registrar_decisao(cfg, "final", PECA_ID, "ajustar", "trocar a legenda")
    processar_estado(store.load(PECA_ID), cfg, gmail, store, logger)

    estado = store.load(PECA_ID)
    assert estado.status == Estado.AGUARDANDO_AJUSTE
    ajustes = list(mpath.parent.glob("AJUSTE-*.txt"))
    assert len(ajustes) == 1
    assert "legenda" in ajustes[0].read_text(encoding="utf-8")


def test_sem_decisao_nao_publica(tmp_path):
    cfg, gmail, store, logger, mpath = _ambiente(tmp_path)
    processar_manifest(mpath, cfg, gmail, store, logger)

    # poller roda sem decisao registrada -> nada acontece
    processar_estado(store.load(PECA_ID), cfg, gmail, store, logger)

    assert store.exists(PECA_ID) is True
    assert store.load(PECA_ID).status == Estado.AGUARDANDO_APROVACAO


def test_multicanal_proof(tmp_path):
    cfg, gmail, store, logger, mpath = _ambiente(tmp_path)
    processar_manifest(mpath, cfg, gmail, store, logger)
    registrar_decisao(cfg, "final", PECA_ID, "aprovar")
    processar_estado(store.load(PECA_ID), cfg, gmail, store, logger)

    arquivada = next(cfg.publicado_dir.glob(f"{PECA_ID}-*"))
    proof = json.loads((arquivada / "PROOF.json").read_text(encoding="utf-8"))
    assert set(proof["canais"]) == {"instagram", "wordpress", "linkedin"}
    assert all(c["status"] == "simulado" for c in proof["canais"].values())
