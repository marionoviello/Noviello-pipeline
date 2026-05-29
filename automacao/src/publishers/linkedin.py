"""Publisher LinkedIn — REST API (stage 05b).

Posta no perfil pessoal do Mario. Formato: documento PDF com todos os slides do
carrossel (mais rico que o post com imagem cover unica, que estava sendo usado
antes — IG limita carrossel a 10 slides, LinkedIn nao).

Fluxo: gerar PDF dos slides -> initializeUpload (documents) -> PUT do PDF ->
criar post com content.media.id = document_urn.
"""

from __future__ import annotations

from pathlib import Path

import httpx
from PIL import Image

from src.http_retry import transient_retry
from src.manifest import Peca
from src.publish_result import PublishResult

NOME = "linkedin"
BASE = "https://api.linkedin.com/rest"
LINKEDIN_VERSION = "202506"
_TIMEOUT = httpx.Timeout(180.0, connect=30.0)
_PDF_RESOLUCAO = 144  # DPI do PDF


def pronto(cfg) -> bool:
    return cfg.linkedin_pronto()


def motivo_indisponivel(cfg) -> str:
    return "credencial LinkedIn ausente (LI_ACCESS_TOKEN / LI_PERSON_URN)"


def _person_urn(valor: str) -> str:
    return valor if valor.startswith("urn:li:person:") else f"urn:li:person:{valor}"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }


@transient_retry
def _post_json(caminho: str, token: str, corpo: dict) -> httpx.Response:
    resp = httpx.post(
        f"{BASE}/{caminho}",
        headers={**_headers(token), "Content-Type": "application/json"},
        json=corpo,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp


@transient_retry
def _put_bytes(url: str, token: str, dados: bytes) -> None:
    resp = httpx.put(
        url,
        headers={"Authorization": f"Bearer {token}"},
        content=dados,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()


def _slides_da_peca(peca: Peca) -> list[Path]:
    """Lista os JPGs dos slides — vem da secao instagram do MANIFEST (renderizados
    pelo producer). Pega so os que existem em disco."""
    ig = peca.ativos("instagram") or {}
    slides = []
    for p in ig.get("imagens", []) or []:
        cam = Path(p)
        if cam.exists():
            slides.append(cam)
    return slides


def _gerar_pdf(slides: list[Path], destino: Path) -> Path:
    """Junta os JPGs num PDF multi-pagina. Devolve o path do PDF."""
    imgs = [Image.open(p).convert("RGB") for p in slides]
    destino.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(
        destino, save_all=True, append_images=imgs[1:], resolution=_PDF_RESOLUCAO
    )
    return destino


def _distribuicao_padrao() -> dict:
    return {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": [],
    }


def _finalizar_post(resp) -> PublishResult:
    post_urn = resp.headers.get("x-restli-id", "")
    url = f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else ""
    return PublishResult.sucesso(NOME, url, ids={"post_urn": post_urn})


def _publicar_texto(token: str, autor: str, texto: str, peca: Peca, logger) -> PublishResult:
    """Post de texto puro — sem documento/carrossel anexado."""
    if not texto:
        return PublishResult.pulado(NOME, "post de texto sem conteudo (texto vazio)")
    corpo: dict = {
        "author": autor,
        "commentary": texto,
        "visibility": "PUBLIC",
        "distribution": _distribuicao_padrao(),
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    logger.info("linkedin", peca_id=peca.peca_id, modo="texto", chars=len(texto))
    resp = _post_json("posts", token, corpo)
    return _finalizar_post(resp)


def _publicar_carrossel(
    token: str, autor: str, texto: str, slides: list[Path], peca: Peca, logger
) -> PublishResult:
    """Post com documento PDF (todos os slides do carrossel)."""
    pasta = slides[0].parent
    pdf_path = pasta / "carrossel-linkedin.pdf"
    _gerar_pdf(slides, pdf_path)
    logger.info(
        "linkedin",
        peca_id=peca.peca_id,
        modo="carrossel",
        pdf=str(pdf_path),
        slides=len(slides),
        pdf_kb=pdf_path.stat().st_size // 1024,
    )

    init = _post_json(
        "documents?action=initializeUpload",
        token,
        {"initializeUploadRequest": {"owner": autor}},
    ).json()["value"]
    doc_urn = init["document"]
    _put_bytes(init["uploadUrl"], token, pdf_path.read_bytes())

    corpo: dict = {
        "author": autor,
        "commentary": texto,
        "visibility": "PUBLIC",
        "distribution": _distribuicao_padrao(),
        "content": {
            "media": {
                "id": doc_urn,
                "title": peca.titulo_curto[:200] if peca.titulo_curto else "Carrossel",
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    resp = _post_json("posts", token, corpo)
    return _finalizar_post(resp)


def publish(peca: Peca, cfg, logger) -> PublishResult:
    """Publica no LinkedIn. Dois formatos:

    - texto puro: post so com commentary (sem documento). Acionado por
      ativos.linkedin.formato == 'texto', ou como fallback quando ha texto
      mas nenhum slide JPG disponivel.
    - carrossel: documento PDF com todos os slides (formato 'carrossel' ou
      default quando ha slides).
    """
    li = peca.ativos("linkedin") or {}
    if not li:
        return PublishResult.pulado(NOME, "sem ativos LinkedIn no MANIFEST")

    token = cfg.linkedin["access_token"]
    autor = _person_urn(cfg.linkedin["person_urn"])

    texto = ""
    if li.get("texto") and Path(li["texto"]).exists():
        texto = Path(li["texto"]).read_text(encoding="utf-8").strip()

    slides = _slides_da_peca(peca)
    formato = (li.get("formato") or "").strip().lower()

    # decisao do modo: flag explicita tem prioridade; senao, infere pela
    # presenca de slides (sem slides + com texto => texto puro).
    if formato == "texto" or (formato != "carrossel" and not slides):
        return _publicar_texto(token, autor, texto, peca, logger)

    if not slides:
        return PublishResult.pulado(NOME, "sem slides JPG para montar o PDF")
    return _publicar_carrossel(token, autor, texto, slides, peca, logger)
