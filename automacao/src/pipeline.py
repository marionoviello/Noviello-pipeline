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

def _registrar_publicacao_unica(peca, estado, cfg, logger) -> None:
    """Registra a publicacao no registry de unicidade pra evitar duplicatas.

    Extrai a chave canonica do MANIFEST.json:
      - Julgado:  ativos.julgado.processo_id  -> 'processo:<normalizado>'
      - Blog WP:  ativos.wordpress.post_id_existente -> 'wp:<id>'
      - Outras:   manual:<peca_id>

    Idempotente. Falha aqui nao deve quebrar o pipeline.
    """
    from src.publicacoes_unicas import (
        RegistroStore, chave_processo, chave_wp_post, chave_manual,
    )
    registry = RegistroStore(cfg.state_dir)

    chave = ""
    tipo = "manual"

    # 1. Julgado da Semana (ativos.julgado.processo_id)
    julgado = peca.ativos("julgado") or {}
    proc = (julgado.get("processo_id") or "").strip()
    if proc:
        chave = chave_processo(proc)
        tipo = "processo"
    else:
        # 2. Blog do WP (post_id_existente)
        wp = peca.ativos("wordpress") or {}
        post_id = wp.get("post_id_existente")
        if post_id:
            chave = chave_wp_post(post_id)
            tipo = "wp_post"
        else:
            # 3. Fallback: manual com peca_id
            chave = chave_manual(peca.peca_id)
            tipo = "manual"

    canais_ok = [c for c, r in estado.canais_publicados.items() if r.get("ok")]
    urls = {c: r.get("url", "") for c, r in estado.canais_publicados.items()
            if r.get("ok") and r.get("url")}

    registry.registrar(
        chave,
        tipo=tipo,
        peca_id=peca.peca_id,
        titulo=peca.titulo_curto,
        canais_publicados=canais_ok,
        urls=urls,
    )
    log_stage(logger, peca.peca_id, "stage.08", "registrado_unicidade")

    # CROSS-FORMAT: se a peça é um blog (wp_post) e o producer detectou
    # processos no texto, registra TAMBÉM as chaves processo:* dessas
    # menções. Assim, futuro Card Julgado da Semana do mesmo processo
    # vai bloquear.
    processos_mencionados = _processos_mencionados_da_peca(peca, estado, cfg)
    for chave_proc in processos_mencionados:
        if chave_proc == chave:
            continue  # ja é a chave principal
        registry.registrar(
            chave_proc,
            tipo="processo",
            peca_id=peca.peca_id,
            titulo=peca.titulo_curto,
            canais_publicados=canais_ok,
            urls=urls,
            notas=f"detectado em texto de {peca.peca_id} (cross-format)",
        )
        log_stage(logger, peca.peca_id, "stage.08",
                  "registrado_unicidade_cross_format")


def _processos_mencionados_da_peca(peca, estado, cfg) -> list[str]:
    """Recupera as chaves de processos mencionados no state do producer Blog.

    Acessa via ProducaoStore (o producer Blog popula 'processos_mencionados'
    no state durante a etapa A). Falha silenciosa se state não for de blog.
    """
    try:
        from src.producer_state import ProducaoStore
        # peca_id de blog é 'social-{post_id}', então post_id = peca_id[7:]
        if not peca.peca_id.startswith("social-"):
            return []
        post_id = peca.peca_id.replace("social-", "", 1)
        prod_store = ProducaoStore(cfg.state_dir)
        if not prod_store.exists(post_id):
            return []
        prod_state = prod_store.load(post_id)
        return [p.get("chave_registry", "") for p in (prod_state.processos_mencionados or [])
                if p.get("chave_registry")]
    except Exception:  # noqa: BLE001
        return []


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

    # ANTI-DUPLICATA: registra esta publicacao no registry de unicidade,
    # pra evitar republicacao acidental do mesmo conteudo (mesmo processo
    # STJ, mesmo post_id WP, etc). Idempotente — se ja existir, incrementa
    # contador de tentativas. Falha aqui nao bloqueia arquivamento.
    try:
        _registrar_publicacao_unica(peca, estado, cfg, logger)
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, peca.peca_id, "stage.08",
                  "registrar_unicidade_falhou", erro=str(exc))

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
