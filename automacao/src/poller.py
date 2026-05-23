"""Poller — stage 04. Tarefa agendada 2 (a cada 1 min).

Le a decisao que o painel gravou em cada peca (estado.decisao) e roteia para o
handler. Nao varre o Gmail.

Rodar:  .venv\\Scripts\\python.exe -m src.poller   (cwd = automacao/)
"""

from __future__ import annotations

import datetime as _dt

from src.config import load_config
from src.gmail_client import GmailClient
from src.logger import get_logger, log_stage, setup_logging
from src.pipeline import enviar_followup, handle_adjust, handle_approve, handle_timeout
from src.state import Estado, LockBusy, StateStore


def _horas_desde(iso: str, agora: _dt.datetime | None = None) -> float:
    if not iso:
        return 0.0
    agora = agora or _dt.datetime.now().astimezone()
    try:
        ref = _dt.datetime.fromisoformat(iso)
    except ValueError:
        return 0.0
    if ref.tzinfo is None:
        ref = ref.astimezone()
    return (agora - ref).total_seconds() / 3600.0


def processar_estado(estado, cfg, gmail, store, logger) -> None:
    status = estado.status

    # recuperacao de crash: peca ficou no meio da publicacao
    if status in (Estado.APROVADA, Estado.PUBLICANDO):
        log_stage(logger, estado.peca_id, "stage.05", "retomada_pos_crash")
        handle_approve(estado, cfg, gmail, store, logger)
        return

    if status != Estado.AGUARDANDO_APROVACAO:
        return

    if estado.decisao == "aprovar":
        handle_approve(estado, cfg, gmail, store, logger)
    elif estado.decisao == "ajustar":
        handle_adjust(estado, estado.ajuste_texto, cfg, gmail, store, logger)
    else:
        # sem decisao: verifica timeout / follow-up
        horas = _horas_desde(estado.enviado_em)
        if horas >= cfg.erro_horas:
            handle_timeout(estado, cfg, gmail, store, logger)
        elif horas >= cfg.followup_horas and not estado.followup_enviado:
            enviar_followup(estado, cfg, gmail, store, logger)


def main() -> int:
    cfg = load_config()
    setup_logging(cfg.logs_dir)
    logger = get_logger("poller")
    from src.heartbeat import bater
    bater(cfg.state_dir, "poller")

    if not cfg.google_pronto():
        logger.info("poller", status="aguardando_setup_google")
        return 0

    gmail = GmailClient(cfg.google)
    store = StateStore(cfg.state_dir)

    pecas = store.list_all()
    for estado in pecas:
        try:
            with store.lock(estado.peca_id):
                # Re-load apos pegar o lock: outro processo pode ter modificado
                # entre o list_all e este ponto. Se a peca foi arquivada, pula.
                if not store.exists(estado.peca_id):
                    continue
                estado_atual = store.load(estado.peca_id)
                processar_estado(estado_atual, cfg, gmail, store, logger)
        except LockBusy:
            logger.info("poller", status="peca_ocupada", peca_id=estado.peca_id)
            continue
        except Exception as exc:  # noqa: BLE001
            log_stage(logger, estado.peca_id, "stage.04", "erro_inesperado", erro=str(exc))

    logger.info("poller", status="fim", pecas_em_andamento=len(pecas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
