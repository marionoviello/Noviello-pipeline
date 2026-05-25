"""Publisher Instagram — Graph API v21.0 (stage 05a).

A Graph API exige image_url publica para cada slide. Por isso o publisher hospeda os
JPGs na biblioteca de midia do WordPress (site 'noviello') antes de criar o carrossel.
Consequencia: o canal Instagram depende tambem da credencial WordPress.
"""

from __future__ import annotations

import time

import httpx

from src.http_retry import transient_retry
from src.manifest import Peca
from src.publish_result import PublishResult
from src.wp_client import WordPressClient

NOME = "instagram"
GRAPH = "https://graph.facebook.com/v21.0"
HOSTING_SITE = "noviello"
_TIMEOUT = httpx.Timeout(120.0, connect=30.0)


def pronto(cfg) -> bool:
    # precisa do token Meta E do WordPress (host das imagens)
    return cfg.meta_pronto() and bool(
        cfg.wordpress.get("user") and cfg.wordpress.get("app_password_noviello")
    )


def motivo_indisponivel(cfg) -> str:
    if not cfg.meta_pronto():
        return "credencial Meta ausente"
    return "credencial WordPress ausente (necessaria para hospedar os slides)"


def _legenda(peca: Peca) -> str:
    from pathlib import Path

    ig = peca.ativos("instagram") or {}
    texto = ""
    if ig.get("legenda") and Path(ig["legenda"]).exists():
        texto = Path(ig["legenda"]).read_text(encoding="utf-8").strip()
    hashtags = ig.get("hashtags") or []
    if hashtags:
        texto = (texto + "\n\n" + " ".join(hashtags)).strip()
    return texto


@transient_retry
def _graph_post(caminho: str, params: dict) -> dict:
    resp = httpx.post(f"{GRAPH}/{caminho}", data=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@transient_retry
def _graph_get(caminho: str, params: dict) -> dict:
    resp = httpx.get(f"{GRAPH}/{caminho}", params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _esperar_finished(container_id: str, token: str, tentativas: int = 15) -> None:
    """Aguarda processamento do container antes de publicar.

    Originalmente fazia polling em GET /{container_id}?fields=status_code, mas
    em 2026-05 o Meta passou a retornar 400/subcode 33 ('Authorization Error /
    object does not exist') nesse endpoint mesmo com token+scope corretos.
    O motivo aparenta ser uma restricao na "Instagram API with Instagram
    Login" — POST cria o container ok, mas leituras de status sao bloqueadas
    para tokens nao "App Review-approved".

    Estrategia atual: espera passiva (sleep). Funcional na pratica — 60s
    cobre o processamento mesmo de carrosseis de 10 slides. Se um dia o
    endpoint voltar, este helper pode ser reescrito.
    """
    # 60s cobre carrossel de ate 10 slides (~5s por slide + margem)
    time.sleep(60)


def publish(peca: Peca, cfg, logger) -> PublishResult:
    ig = peca.ativos("instagram") or {}
    imagens = ig.get("imagens") or []
    if not imagens:
        return PublishResult.pulado(NOME, "sem imagens no MANIFEST")

    token = cfg.meta["page_token"]
    ig_id = cfg.meta["ig_business_id"]
    legenda = _legenda(peca)

    # 1. hospeda os slides no WordPress para obter URLs publicas
    wp = WordPressClient(cfg.wordpress["user"], {"noviello": cfg.wordpress["app_password_noviello"]})
    urls_publicas: list[str] = []
    for caminho in imagens:
        midia = wp.upload_media(caminho, HOSTING_SITE)
        urls_publicas.append(midia["source_url"])
    logger.info("instagram", peca_id=peca.peca_id, slides_hospedados=len(urls_publicas))

    # 2. cria os containers
    if len(urls_publicas) == 1:
        container = _graph_post(
            f"{ig_id}/media",
            {"image_url": urls_publicas[0], "caption": legenda, "access_token": token},
        )
        creation_id = container["id"]
    else:
        filhos = []
        for url in urls_publicas:
            item = _graph_post(
                f"{ig_id}/media",
                {"image_url": url, "is_carousel_item": "true", "access_token": token},
            )
            filhos.append(item["id"])
        container = _graph_post(
            f"{ig_id}/media",
            {
                "media_type": "CAROUSEL",
                "children": ",".join(filhos),
                "caption": legenda,
                "access_token": token,
            },
        )
        creation_id = container["id"]

    # 3. aguarda processamento e publica
    _esperar_finished(creation_id, token)
    publicado = _graph_post(
        f"{ig_id}/media_publish",
        {"creation_id": creation_id, "access_token": token},
    )
    media_id = publicado["id"]

    # 4. obtem o permalink (best-effort — Meta as vezes bloqueia GET com 400)
    try:
        info = _graph_get(media_id, {"fields": "permalink", "access_token": token})
        permalink = info.get("permalink", "")
    except Exception:  # noqa: BLE001
        permalink = f"https://www.instagram.com/novielloadv/"  # fallback: perfil

    return PublishResult.sucesso(NOME, permalink, ids={"media_id": media_id})
