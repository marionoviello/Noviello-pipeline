"""STJ Informativos — discover URLs + download com cache local + rate limit.

Fonte: portal oficial do STJ. Cada informativo tem um numero (1, 2, ...) e um
PDF associado. O backfill itera por uma faixa de numeros (estimado por ano),
checa cache, baixa se falta e devolve o path local.

Estrategia de descoberta: o STJ publica a lista de informativos por ano em
HTML simples. Esta funcao raspa essa pagina pra coletar (numero, url_pdf).

URLs canonicas:
- Lista por ano: https://www.stj.jus.br/sites/portalp/Paginas/Servicos/Informativo-de-Jurisprudencia.aspx
- PDFs: https://www.stj.jus.br/publicacaoinstitucional/index.php/informjuris/issue/view/...

Os tests evitam rede — usam fixtures HTML/bytes e mockam o downloader.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import urljoin

from src.julgado_radar.config import RATE_LIMIT_STJ_SEG


# Pagina de listagem (default — pode ser overrideada nos testes)
URL_LISTAGEM_STJ = (
    "https://www.stj.jus.br/sites/portalp/Paginas/Servicos/"
    "Informativo-de-Jurisprudencia.aspx"
)


@dataclass(frozen=True)
class InformativoRef:
    """Referencia leve a um Informativo (sem ainda baixar o PDF)."""

    numero: int
    ano: int
    url_pdf: str

    @property
    def fonte_key(self) -> str:
        """Chave de idempotencia pra fetch_log."""
        return f"stj-informativo-{self.numero}"

    @property
    def filename(self) -> str:
        return f"inf-{self.numero:04d}.pdf"


# Default HTTP getter — pode ser substituido nos testes (injection).
# Recebe url -> devolve (status_code, body_bytes).
HttpGetFn = Callable[[str], tuple[int, bytes]]


def _http_get_default(url: str) -> tuple[int, bytes]:  # pragma: no cover — real net
    """Fallback real (usado fora dos testes). Importa httpx lazy pra nao
    obrigar a dependencia em testes que mockam."""
    import httpx  # noqa: PLC0415

    resp = httpx.get(
        url,
        headers={"User-Agent": "Noviello-Radar/1.0 (+contato: mario@noviello.adv.br)"},
        timeout=30.0,
        follow_redirects=True,
    )
    return resp.status_code, resp.content


# Regex pra capturar links de PDFs de informativos em HTML.
# Aceita varios formatos (numero como path ou query param).
_RE_PDF_INFO = re.compile(
    r'href="([^"]+)"[^>]*>[^<]*Informativo\s+(?:n[º°.]?\s*)?(\d{1,4})',
    re.IGNORECASE,
)


def parse_listagem(html: str, base_url: str = URL_LISTAGEM_STJ) -> list[InformativoRef]:
    """Extrai (numero, url) dos informativos a partir do HTML da listagem.

    Heuristica robusta a variacoes do HTML do portal STJ: procura por
    'Informativo NNN' associado a um href de PDF.
    """
    refs: list[InformativoRef] = []
    visto: set[int] = set()
    for href, num_str in _RE_PDF_INFO.findall(html):
        try:
            numero = int(num_str)
        except ValueError:
            continue
        if numero in visto:
            continue
        # filtra apenas URLs que parecem ser de PDF
        if not (href.lower().endswith(".pdf") or "pdf" in href.lower()):
            continue
        url_abs = href if href.startswith("http") else urljoin(base_url, href)
        visto.add(numero)
        # ano nao vem da listagem direta — chamador decide via filtro_ano
        refs.append(InformativoRef(numero=numero, ano=0, url_pdf=url_abs))
    return refs


def descobrir_informativos(
    anos: Iterable[int],
    *,
    url_listagem: str = URL_LISTAGEM_STJ,
    http_get: Optional[HttpGetFn] = None,
) -> list[InformativoRef]:
    """Descobre informativos do STJ filtrando pela lista de anos.

    Devolve lista de InformativoRef. Sem rede em testes (http_get mockavel).
    """
    getter = http_get or _http_get_default
    anos_set = set(int(a) for a in anos)

    status, body = getter(url_listagem)
    if status != 200:
        return []
    html = body.decode("utf-8", errors="replace")

    refs = parse_listagem(html, base_url=url_listagem)

    # Heuristica de ano: STJ ate 2026 tem ~24-30 informativos por ano. Atribuimos
    # ano pelo numero (ranges aproximados). Esta funcao e best-effort; o backfill
    # pode confirmar/corrigir ano via metadata do PDF depois.
    refs_com_ano = [_atribuir_ano(r) for r in refs]
    return [r for r in refs_com_ano if r.ano in anos_set]


# Mapeamento aproximado numero -> ano (calibrado em 2026-05).
# Cada faixa cobre ~24-28 informativos por ano. Atualizar quando o STJ
# publicar mais ao longo de 2026.
_FAIXAS_ANO: tuple[tuple[range, int], ...] = (
    (range(700, 730), 2021),
    (range(730, 760), 2022),
    (range(760, 790), 2023),
    (range(790, 820), 2024),
    (range(820, 850), 2025),
    (range(850, 880), 2026),
)


def _atribuir_ano(ref: InformativoRef) -> InformativoRef:
    for faixa, ano in _FAIXAS_ANO:
        if ref.numero in faixa:
            return InformativoRef(numero=ref.numero, ano=ano, url_pdf=ref.url_pdf)
    return ref  # ano=0 = desconhecido (sera filtrado)


def baixar_informativo(
    ref: InformativoRef,
    cache_dir: Path,
    *,
    http_get: Optional[HttpGetFn] = None,
    rate_limit_seg: float = RATE_LIMIT_STJ_SEG,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Path:
    """Baixa o PDF do informativo em cache_dir. Se ja existe (e tamanho > 0),
    devolve o path direto.

    Levanta FeedSTJError em falha de download.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destino = cache_dir / ref.filename

    if destino.exists() and destino.stat().st_size > 0:
        return destino

    getter = http_get or _http_get_default
    status, body = getter(ref.url_pdf)
    if status != 200 or not body:
        raise FeedSTJError(
            f"falha ao baixar informativo {ref.numero} de {ref.url_pdf} "
            f"(status={status}, bytes={len(body)})"
        )

    # Rate limit BEFORE escrever pro disco (efeito colateral controlado nos tests)
    if rate_limit_seg > 0:
        sleep_fn(rate_limit_seg)

    destino.write_bytes(body)
    return destino


class FeedSTJError(Exception):
    pass
