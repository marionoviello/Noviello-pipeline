"""Watcher — stages 01-03. Tarefa agendada 1 (a cada 1 min).

Varre producao/ procurando MANIFEST.json de pecas novas, valida, registra a peca
para o painel e envia o email-ping. Idempotente: peca com arquivo de state nao e
reprocessada.

Rodar:  .venv\\Scripts\\python.exe -m src.watcher   (cwd = automacao/)
"""

from __future__ import annotations

import time

from src.config import load_config
from src.emails import build_error_email, build_ping_email
from src.gmail_client import GmailClient
from src.logger import get_logger, log_stage, setup_logging
from src.manifest import carregar_manifest, validate_manifest
from src.pipeline import PAINEL_URL
from src.state import Estado, LockBusy, PecaState, StateStore, agora_iso, transition


def _identificador(mpath) -> str:
    """peca_id se o MANIFEST for parseavel; senao, o nome da pasta."""
    try:
        return carregar_manifest(mpath).peca_id
    except Exception:  # noqa: BLE001
        return mpath.parent.name


def processar_manifest(mpath, cfg, gmail, store, logger) -> None:
    ident = _identificador(mpath)
    if store.exists(ident):
        return  # ja processada

    inicio = time.monotonic()
    try:
        peca = validate_manifest(mpath)
    except Exception as exc:  # noqa: BLE001  (ValidacaoError ou JSON malformado)
        erro = PecaState(peca_id=ident, status=Estado.ERRO, manifest_path=str(mpath))
        store.save(erro)
        log_stage(logger, ident, "stage.01", "erro", erro=str(exc))
        try:
            gmail.send_message(
                build_error_email(ident, "stage.01", str(exc), "logs/", cfg.email_aprovador)
            )
        except Exception as e2:  # noqa: BLE001
            log_stage(logger, ident, "stage.01", "erro_email", erro=str(e2))
        return

    log_stage(logger, peca.peca_id, "stage.01", "ok")

    # stage 03 — registra a peca para o painel e avisa por email-ping
    estado = PecaState(
        peca_id=peca.peca_id,
        status=Estado.DETECTADA,
        manifest_path=str(mpath),
        enviado_em=agora_iso(),
    )
    transition(estado, Estado.AGUARDANDO_APROVACAO)
    store.save(estado)

    try:
        gmail.send_message(build_ping_email(1, PAINEL_URL, cfg.email_aprovador))
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, peca.peca_id, "stage.03", "ping_falhou", erro=str(exc))

    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, peca.peca_id, "stage.03", "no_painel", duracao_ms=dur)


def main() -> int:
    cfg = load_config()
    setup_logging(cfg.logs_dir)
    logger = get_logger("watcher")
    from src.heartbeat import bater
    bater(cfg.state_dir, "watcher")

    if not cfg.google_pronto():
        logger.info("watcher", status="aguardando_setup_google")
        return 0

    gmail = GmailClient(cfg.google)
    store = StateStore(cfg.state_dir)

    if not cfg.producao_dir.exists():
        logger.info("watcher", status="sem_pasta_producao")
        return 0

    encontrados = 0
    for mpath in cfg.producao_dir.glob("*/*/MANIFEST.json"):
        if "_publicado" in mpath.parts:
            continue
        encontrados += 1
        ident = _identificador(mpath)
        try:
            with store.lock(ident):
                # re-verifica apos o lock: outro watcher pode ter acabado de registrar
                if store.exists(ident):
                    continue
                processar_manifest(mpath, cfg, gmail, store, logger)
        except LockBusy:
            logger.info("watcher", status="peca_ocupada", peca_id=ident)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.info("watcher", status="erro_inesperado", manifest=str(mpath), erro=str(exc))

    logger.info("watcher", status="fim", manifests_vistos=encontrados)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
