"""Orquestracao dos stages 05-08 e do ramo de ajuste.

As decisoes (aprovar / ajustar) vem do painel local, gravadas em estado.decisao.
Este modulo nao toca no Gmail para decidir — usa o Gmail apenas para o email-ping
de confirmacao/erro.
"""

from __future__ import annotations

import datetime as _dt
import json
import shutil
import time
from pathlib import Path

from src.calendar_client import CalendarClient
from src.emails import build_error_email, build_ping_email, build_publicado_email
from src.logger import log_stage
from src.manifest import carregar_manifest
from src.publish_result import OK, PULADO, SIMULADO
from src.publishers import publicar_canal
from src.state import Estado, StateStore, agora_iso, transition

PAINEL_URL = "http://localhost:8765"


# ---- stage 08 ------------------------------------------------------------

def arquivar_peca(peca, estado, cfg, logger) -> bool:
    """Stage 08: PROOF.json, move a pasta para _publicado/, atualiza o Calendar.

    Devolve True se a pasta foi movida (libera apagar o state com seguranca).
    """
    proof = {
        "peca_id": peca.peca_id,
        "titulo": peca.titulo_curto,
        "publicado_em": agora_iso(),
        "canais": estado.canais_publicados,
        "historico": estado.historico,
    }
    try:
        (peca.manifest_dir / "PROOF.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:  # noqa: BLE001
        log_stage(logger, peca.peca_id, "stage.08", "proof_falhou", erro=str(exc))

    cfg.publicado_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    destino = cfg.publicado_dir / f"{peca.peca_id}-{ts}"
    movido = False
    try:
        shutil.move(str(peca.manifest_dir), str(destino))
        movido = True
    except (OSError, shutil.Error) as exc:  # noqa: BLE001
        log_stage(logger, peca.peca_id, "stage.08", "move_falhou", erro=str(exc))

    try:
        if cfg.google_pronto():
            cal = CalendarClient(cfg.google)
            achou = cal.registrar_publicacao(
                cfg.google["calendar_id"], peca, estado.canais_publicados, agora_iso()
            )
            log_stage(
                logger, peca.peca_id, "stage.08",
                "calendar_ok" if achou else "calendar_sem_evento",
            )
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, peca.peca_id, "stage.08", "calendar_falhou", erro=str(exc))

    return movido


# ---- aprovacao (stages 05-08) -------------------------------------------

def _alerta_erro(estado, peca, cfg, gmail, falhas: list[str], logger) -> None:
    from src.alertas import alertar
    detalhe = "\n".join(
        f"  - {c}: {estado.canais_publicados[c].get('erro', '?')}" for c in falhas
    )
    titulo = f"Peça '{peca.titulo_curto}' falhou em {len(falhas)} canal(is)"
    corpo = (
        f"Peça ID: {peca.peca_id}\n"
        f"Canais com falha:\n{detalhe}\n\n"
        f"Próximo passo: revisar logs em logs/ e tentar retry manual via painel."
    )
    alertar(cfg, gmail, "publisher_falhou", peca.peca_id,
            titulo=titulo, corpo=corpo, gravidade="alto", logger=logger)


def handle_approve(estado, cfg, gmail, store: StateStore, logger) -> None:
    """Stages 05-08. Idempotente: canais ja publicados nao sao republicados."""
    inicio = time.monotonic()
    peca = carregar_manifest(Path(estado.manifest_path))

    if estado.status == Estado.AGUARDANDO_APROVACAO:
        transition(estado, Estado.APROVADA)
    if estado.status in (Estado.APROVADA, Estado.ERRO):
        transition(estado, Estado.PUBLICANDO)
    store.save(estado)

    for canal in peca.canais_no_manifest():
        anterior = estado.canais_publicados.get(canal)
        if anterior and anterior.get("ok") and anterior.get("status") in (OK, SIMULADO, PULADO):
            continue
        resultado = publicar_canal(canal, peca, cfg, logger)
        estado.canais_publicados[canal] = resultado.to_dict()
        store.save(estado)
        log_stage(
            logger, peca.peca_id, f"stage.05.{canal}", resultado.status,
            erro=resultado.erro or None,
        )

    falhas = [c for c, r in estado.canais_publicados.items() if not r.get("ok")]
    if falhas:
        transition(estado, Estado.ERRO)
        store.save(estado)
        _alerta_erro(estado, peca, cfg, gmail, falhas, logger)
        return

    # stage 07 — email-ping de confirmacao
    try:
        gmail.send_message(
            build_publicado_email(peca.titulo_curto, estado.canais_publicados, cfg.email_aprovador)
        )
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, peca.peca_id, "stage.07", "confirmacao_falhou", erro=str(exc))

    # stage 08 — persistir e arquivar
    transition(estado, Estado.PUBLICADA)
    estado.proof = {"canais": estado.canais_publicados, "publicado_em": agora_iso()}
    store.save(estado)
    movido = arquivar_peca(peca, estado, cfg, logger)
    if movido:
        store.delete(estado.peca_id)
    else:
        log_stage(logger, peca.peca_id, "stage.08", "state_mantido_tombstone")

    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, peca.peca_id, "stage.08", "publicada", duracao_ms=dur)


# ---- ramo: ajuste --------------------------------------------------------

def handle_adjust(estado, texto_ajuste: str, cfg, gmail, store: StateStore, logger) -> None:
    peca = carregar_manifest(Path(estado.manifest_path))
    ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    (peca.manifest_dir / f"AJUSTE-{ts}.txt").write_text(
        texto_ajuste or "(sem texto)", encoding="utf-8"
    )
    transition(estado, Estado.AGUARDANDO_AJUSTE)
    store.save(estado)
    log_stage(logger, peca.peca_id, "stage.alt.ajuste", "registrado")


# ---- timeout e follow-up -------------------------------------------------

def enviar_followup(estado, cfg, gmail, store: StateStore, logger) -> None:
    try:
        gmail.send_message(build_ping_email(1, PAINEL_URL, cfg.email_aprovador))
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, estado.peca_id, "stage.04", "followup_falhou", erro=str(exc))
    estado.followup_enviado = True
    store.save(estado)
    log_stage(logger, estado.peca_id, "stage.04", "followup_enviado")


def handle_timeout(estado, cfg, gmail, store: StateStore, logger) -> None:
    transition(estado, Estado.TIMEOUT)
    store.save(estado)
    log_stage(logger, estado.peca_id, "stage.04", "timeout")
