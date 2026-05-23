"""Testa o watcher: detecta MANIFEST, registra a peca e envia o email-ping."""

from src.config import load_config
from src.logger import get_logger, setup_logging
from src.state import Estado, StateStore
from src.watcher import processar_manifest
from tests.helpers import FakeGmail, criar_peca_dir


def _ctx(tmp_path):
    cfg = load_config()
    setup_logging(tmp_path / "logs")
    logger = get_logger("teste-watcher")
    store = StateStore(tmp_path / "state")
    return cfg, logger, store


def test_peca_valida_registra_e_avisa(tmp_path):
    cfg, logger, store = _ctx(tmp_path)
    gmail = FakeGmail()
    mpath = criar_peca_dir(tmp_path / "producao")

    processar_manifest(mpath, cfg, gmail, store, logger)

    assert len(gmail.enviados) == 1  # email-ping
    estado = store.load("2026-S20-teste")
    assert estado.status == Estado.AGUARDANDO_APROVACAO
    assert estado.decisao == ""
    assert estado.enviado_em != ""


def test_idempotente_nao_reprocessa(tmp_path):
    cfg, logger, store = _ctx(tmp_path)
    gmail = FakeGmail()
    mpath = criar_peca_dir(tmp_path / "producao")

    processar_manifest(mpath, cfg, gmail, store, logger)
    processar_manifest(mpath, cfg, gmail, store, logger)

    assert len(gmail.enviados) == 1  # nao avisou de novo


def test_validacao_falha_grava_erro(tmp_path):
    cfg, logger, store = _ctx(tmp_path)
    gmail = FakeGmail()
    mpath = criar_peca_dir(tmp_path / "producao", oab="reprovado")

    processar_manifest(mpath, cfg, gmail, store, logger)

    estado = store.load("2026-S20-teste")
    assert estado.status == Estado.ERRO
    assert len(gmail.enviados) == 1
    assert "[ERRO]" in gmail.enviados[0]["Subject"]
