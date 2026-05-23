"""Testa a orquestracao publicar_canal / publicar_todos (sem chamar APIs reais)."""

from src.circuit import registrar_falha
from src.config import load_config
from src.logger import get_logger, setup_logging
from src.manifest import carregar_manifest
from src.publish_result import ERRO, OK, PULADO, SIMULADO
from src.publishers import publicar_canal, publicar_todos
from tests.helpers import criar_peca_dir


def _cfg(tmp_path, *, enabled, dry_run, com_credenciais):
    cfg = load_config()
    cfg.enabled_channels = list(enabled)
    cfg.dry_run = dry_run
    cfg.state_dir = tmp_path / "state"
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    if com_credenciais:
        cfg.meta = {"page_token": "tok", "ig_business_id": "123", "page_id": "456"}
        cfg.wordpress = {
            "user": "mario",
            "app_password_noviello": "pw1",
            "app_password_imobiliario": "pw2",
        }
        cfg.linkedin = {"access_token": "tok", "refresh_token": "r", "person_urn": "u"}
    else:
        cfg.meta = {"page_token": "", "ig_business_id": "", "page_id": ""}
        cfg.wordpress = {"user": "", "app_password_noviello": "", "app_password_imobiliario": ""}
        cfg.linkedin = {"access_token": "", "refresh_token": "", "person_urn": ""}
    return cfg


def _logger(tmp_path):
    setup_logging(tmp_path / "logs")
    return get_logger("teste-pub")


def test_canal_sem_ativos_e_pulado(tmp_path):
    cfg = _cfg(tmp_path, enabled=["linkedin"], dry_run=True, com_credenciais=True)
    peca = carregar_manifest(criar_peca_dir(tmp_path / "p", canais=("instagram",)))
    r = publicar_canal("linkedin", peca, cfg, _logger(tmp_path))
    assert r.status == PULADO
    assert "sem ativos" in r.motivo


def test_canal_fora_de_enabled_e_pulado(tmp_path):
    cfg = _cfg(tmp_path, enabled=["wordpress"], dry_run=True, com_credenciais=True)
    peca = carregar_manifest(criar_peca_dir(tmp_path / "p", canais=("instagram",)))
    r = publicar_canal("instagram", peca, cfg, _logger(tmp_path))
    assert r.status == PULADO
    assert "ENABLED_CHANNELS" in r.motivo


def test_sem_credencial_e_pulado(tmp_path):
    cfg = _cfg(tmp_path, enabled=["instagram"], dry_run=True, com_credenciais=False)
    peca = carregar_manifest(criar_peca_dir(tmp_path / "p", canais=("instagram",)))
    r = publicar_canal("instagram", peca, cfg, _logger(tmp_path))
    assert r.status == PULADO
    assert "credencial" in r.motivo.lower()


def test_dry_run_retorna_simulado(tmp_path):
    cfg = _cfg(tmp_path, enabled=["instagram"], dry_run=True, com_credenciais=True)
    peca = carregar_manifest(criar_peca_dir(tmp_path / "p", canais=("instagram",)))
    r = publicar_canal("instagram", peca, cfg, _logger(tmp_path))
    assert r.status == SIMULADO
    assert r.ok is True
    assert "dry-run" in r.url


def test_circuit_breaker_aberto_e_falha_nao_pulado(tmp_path):
    # uma peca nao pode ser dada como publicada com o canal em circuit breaker
    cfg = _cfg(tmp_path, enabled=["instagram"], dry_run=True, com_credenciais=True)
    for _ in range(3):
        registrar_falha(cfg.state_dir, "instagram")
    peca = carregar_manifest(criar_peca_dir(tmp_path / "p", canais=("instagram",)))
    r = publicar_canal("instagram", peca, cfg, _logger(tmp_path))
    assert r.status == ERRO
    assert r.ok is False
    assert "circuit breaker" in r.erro


def test_publicar_todos_cobre_todos_os_canais_do_manifest(tmp_path):
    cfg = _cfg(
        tmp_path,
        enabled=["instagram", "wordpress", "linkedin"],
        dry_run=True,
        com_credenciais=True,
    )
    peca = carregar_manifest(
        criar_peca_dir(tmp_path / "p", canais=("instagram", "wordpress", "linkedin"))
    )
    resultados = publicar_todos(peca, cfg, _logger(tmp_path))
    assert set(resultados) == {"instagram", "wordpress", "linkedin"}
    assert all(r.status == SIMULADO for r in resultados.values())
