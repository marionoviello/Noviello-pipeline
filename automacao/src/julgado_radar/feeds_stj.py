"""STJ Informativos — duas estrategias de coleta.

**Estrategia atual (2026-05-27 final, validada):** baixar **PDFs anuais
agregados** via httpx puro. Cada PDF contem todos os ~38 informativos de
um ano consolidados (ex: informativo_anual_2023.pdf = 1000 paginas, 26MB).

URL pattern:
  https://processo.stj.jus.br/docs_internet/informativos/anuais/informativo_anual_{ANO}.pdf

Anos com PDF anual disponivel: 2021, 2022, 2023 (confirmados via probe).
2024 ainda nao foi publicado (STJ demora ~1 ano pra consolidar). Pra anos
correntes, ver `baixar_informativo` (Playwright — limitado).

**Estrategia legacy (Playwright):** `descobrir_informativos` + `baixar_informativo`
continuam presentes, mas `baixar_informativo` foi documentado como BROKEN
contra o portal real (selects sao decorativos, conteudo do informativo nao
muda apos select). Mantido pra back-compat e pra futura calibracao.

Diagnostico completo em probes v3-v5 (automacao/samples/_probe_stj_v*.py).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterable, Optional

from src.julgado_radar.config import RATE_LIMIT_STJ_SEG


URL_PORTAL_INFORMATIVOS = (
    "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"
)

URL_PDF_ANUAL_TEMPLATE = (
    "https://processo.stj.jus.br/docs_internet/informativos/anuais/"
    "informativo_anual_{ano}.pdf"
)

# Anos suportados pelo portal (cada um tem seu proprio combo `idInformativoEdicoesCombo{ano}`).
# 2026 e o teto atual (recalibrar quando STJ publicar 2027).
ANOS_SUPORTADOS = (2021, 2022, 2023, 2024, 2025, 2026)

# Anos com PDF anual confirmado disponivel (probe 2026-05-27).
# 2024/2025 dao 404 — STJ demora ~1 ano pra consolidar o anual.
ANOS_PDF_ANUAL = (2021, 2022, 2023)


@dataclass(frozen=True)
class InformativoRef:
    """Referencia leve a um Informativo do STJ (sem ainda baixar).

    Compatibilidade: campos antigos (numero, ano, url_pdf) preservados
    para serializacao; novos campos (select_id, option_value, titulo)
    sao usados pelo novo fluxo Playwright.
    """

    numero: int
    ano: int
    url_pdf: str = ""  # legacy — preenchido com URL canonica do portal
    select_id: str = ""
    option_value: str = ""
    titulo: str = ""

    @property
    def fonte_key(self) -> str:
        """Chave de idempotencia pra fetch_log."""
        return f"stj-informativo-{self.numero}"

    @property
    def filename(self) -> str:
        """Nome do arquivo em cache. HTML no novo fluxo, .pdf no legacy."""
        return f"inf-{self.numero:04d}.html"


# ===== Estrategia atual: PDF anual agregado via httpx =====

@dataclass(frozen=True)
class PdfAnualRef:
    """Referencia a um PDF anual agregado do STJ (1 PDF = todos os infos do ano).

    Ex: PdfAnualRef(ano=2023, url='.../informativo_anual_2023.pdf')
    """

    ano: int
    url: str

    @property
    def fonte_key(self) -> str:
        """Chave de idempotencia para fetch_log."""
        return f"stj-pdf-anual-{self.ano}"

    @property
    def filename(self) -> str:
        return f"informativo_anual_{self.ano}.pdf"


# Default HTTP getter (httpx) — pode ser substituido em testes.
HttpGetFn = Callable[[str], tuple[int, bytes]]


def _http_get_default(url: str) -> tuple[int, bytes]:  # pragma: no cover — real net
    """Fallback real para baixar PDFs anuais. Importa httpx lazy."""
    import httpx  # noqa: PLC0415

    resp = httpx.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        },
        timeout=120.0,  # PDFs anuais sao 17-38MB
        follow_redirects=True,
    )
    return resp.status_code, resp.content


def _http_head_default(url: str) -> tuple[int, dict]:  # pragma: no cover — real net
    """HEAD request — checa existencia sem baixar."""
    import httpx  # noqa: PLC0415

    resp = httpx.head(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        },
        timeout=15.0,
        follow_redirects=True,
    )
    return resp.status_code, dict(resp.headers)


HttpHeadFn = Callable[[str], tuple[int, dict]]


def obter_pdfs_anuais(
    anos: Iterable[int],
    *,
    http_head: Optional[HttpHeadFn] = None,
) -> list[PdfAnualRef]:
    """Para cada ano pedido, verifica se o PDF anual existe via HEAD e devolve refs.

    Anos sem PDF disponivel (HEAD != 200) sao silenciosamente filtrados. Em
    testes, injetar `http_head` que devolve dict de status por URL.
    """
    head = http_head or _http_head_default
    refs: list[PdfAnualRef] = []
    for ano in sorted(set(int(a) for a in anos)):
        url = URL_PDF_ANUAL_TEMPLATE.format(ano=ano)
        try:
            status, _ = head(url)
        except Exception:  # noqa: BLE001
            continue
        if status == 200:
            refs.append(PdfAnualRef(ano=ano, url=url))
    return refs


def baixar_pdf_anual(
    ref: PdfAnualRef,
    cache_dir: Path,
    *,
    http_get: Optional[HttpGetFn] = None,
    rate_limit_seg: float = RATE_LIMIT_STJ_SEG,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Path:
    """Baixa o PDF anual via httpx e grava no cache.

    Se ja existe em `cache_dir/informativo_anual_{ano}.pdf` (e nao-vazio),
    devolve direto (cache hit). Levanta FeedSTJError em falha.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destino = cache_dir / ref.filename

    if destino.exists() and destino.stat().st_size > 0:
        return destino

    getter = http_get or _http_get_default
    try:
        status, body = getter(ref.url)
    except Exception as exc:  # noqa: BLE001
        raise FeedSTJError(
            f"falha de rede baixando PDF anual {ref.ano}: {exc}"
        ) from exc

    if status != 200 or len(body) < 100_000:  # PDFs anuais nunca <100KB
        raise FeedSTJError(
            f"PDF anual {ref.ano} indisponivel (status={status}, "
            f"bytes={len(body)})"
        )

    if not body.startswith(b"%PDF"):
        raise FeedSTJError(
            f"PDF anual {ref.ano} corrompido (nao comeca com %PDF)"
        )

    if rate_limit_seg > 0:
        sleep_fn(rate_limit_seg)

    destino.write_bytes(body)
    return destino


# ===== Estrategia legacy: Playwright (mantida pra compat / futura calibracao) =====

# Interface minima esperada da pagina Playwright (subset de
# playwright.sync_api.Page usado aqui). Permite mock simples nos testes.
class _PageLike:  # pragma: no cover — protocolo, nao classe real
    def goto(self, url: str, *args: Any, **kwargs: Any) -> Any: ...
    def wait_for_load_state(self, state: str, *args: Any, **kwargs: Any) -> Any: ...
    def wait_for_timeout(self, ms: int) -> Any: ...
    def evaluate(self, script: str, *args: Any) -> Any: ...
    def eval_on_selector(self, selector: str, script: str) -> Any: ...
    def select_option(self, selector: str, *, value: str) -> Any: ...


# Factory deve retornar um context manager que devolve um objeto compativel
# com _PageLike (idealmente uma pagina Playwright real, ou um mock nos tests).
PlaywrightFactory = Callable[[], ContextManager[_PageLike]]


@contextmanager
def _default_playwright_factory():  # pragma: no cover — real Chromium
    """Fallback real: abre Chromium headless e devolve a pagina."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            )
            page = ctx.new_page()
            yield page
        finally:
            browser.close()


def _abrir_portal(page: _PageLike) -> None:
    """Carrega o portal e espera os combos serem injetados via JS."""
    page.goto(URL_PORTAL_INFORMATIVOS, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)


# JS snippet que enumera as <option> de um <select> e devolve list de
# {value, text}. Devolvido como lista (nao tuple) por compat com mocks.
_JS_LISTAR_OPCOES = """(sel) => {
    const el = document.querySelector(sel);
    if (!el) return [];
    return Array.from(el.options)
        .filter(o => o.value && o.value.trim() !== '')
        .map(o => ({value: o.value, text: o.textContent.trim()}));
}"""


def _listar_opcoes_do_select(page: _PageLike, select_id: str) -> list[dict]:
    """Enumera as opcoes (numero do informativo) disponiveis num select por ano."""
    try:
        return page.evaluate(_JS_LISTAR_OPCOES, f"#{select_id}") or []
    except Exception:  # noqa: BLE001
        return []


def descobrir_informativos(
    anos: Iterable[int],
    *,
    playwright_factory: Optional[PlaywrightFactory] = None,
) -> list[InformativoRef]:
    """Descobre informativos do STJ via Playwright para os anos pedidos.

    Para cada ano, le o combo `#idInformativoEdicoesCombo{ano}` e cria
    uma `InformativoRef` por opcao valida. Devolve lista ordenada por
    (ano DESC, numero DESC) — mais recentes primeiro.

    Sem rede em testes: passar `playwright_factory` retornando context
    manager com uma `FakePage` que implementa `goto/wait_for_*/evaluate`.
    """
    factory = playwright_factory or _default_playwright_factory
    anos_filtrados = sorted(set(int(a) for a in anos if int(a) in ANOS_SUPORTADOS))
    if not anos_filtrados:
        return []

    refs: list[InformativoRef] = []
    with factory() as page:
        _abrir_portal(page)
        for ano in anos_filtrados:
            select_id = f"idInformativoEdicoesCombo{ano}"
            opcoes = _listar_opcoes_do_select(page, select_id)
            for opt in opcoes:
                value = (opt.get("value") or "").strip()
                if not value:
                    continue
                try:
                    numero = int(value)
                except ValueError:
                    # Algumas opcoes podem ter valor nao-numerico (ex: Especiais).
                    continue
                refs.append(InformativoRef(
                    numero=numero,
                    ano=ano,
                    url_pdf=URL_PORTAL_INFORMATIVOS,
                    select_id=select_id,
                    option_value=value,
                    titulo=(opt.get("text") or "").strip(),
                ))

    # Mais recentes primeiro
    refs.sort(key=lambda r: (r.ano, r.numero), reverse=True)
    return refs


# JS pra extrair o HTML renderizado do bloco com a lista de itens do
# informativo selecionado. O ID do container observado no probe e
# `#idInformativoBlocoLista` (pode mudar — alternativas como fallback).
_SELECTORES_BLOCO = (
    "#idInformativoBlocoLista",
    "#idBlocoListaInformativos",
    ".informativo-bloco",
)


def _extrair_bloco(page: _PageLike) -> str:
    """Tenta extrair innerHTML do bloco da lista, com fallback entre selectors."""
    for selector in _SELECTORES_BLOCO:
        try:
            html = page.eval_on_selector(selector, "el => el ? el.innerHTML : ''")
        except Exception:  # noqa: BLE001
            continue
        if html and str(html).strip():
            return str(html)
    return ""


def baixar_informativo(
    ref: InformativoRef,
    cache_dir: Path,
    *,
    playwright_factory: Optional[PlaywrightFactory] = None,
    rate_limit_seg: float = RATE_LIMIT_STJ_SEG,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Path:
    """Baixa o HTML renderizado do informativo via Playwright + cache local.

    Se o arquivo `cache_dir/inf-NNNN.html` ja existe (e nao-vazio), devolve
    direto (cache hit, sem rede). Caso contrario, abre o portal, faz
    select_option e captura `innerHTML` do bloco da lista de itens.

    Levanta `FeedSTJError` se nao conseguir extrair HTML nao-vazio.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destino = cache_dir / ref.filename

    if destino.exists() and destino.stat().st_size > 0:
        return destino

    if not ref.select_id or not ref.option_value:
        raise FeedSTJError(
            f"InformativoRef {ref.numero} sem select_id/option_value — "
            "descobrir_informativos precisa rodar antes"
        )

    factory = playwright_factory or _default_playwright_factory
    with factory() as page:
        _abrir_portal(page)
        try:
            # Usa evaluate direto: o <select> existe mas pode estar invisivel
            # (escondido atras de aba/accordion do ano). select_option do
            # Playwright timeouta nesse caso. Setar value via JS + disparar
            # change bypassa todas as checagens de visibilidade.
            page.evaluate(
                """([selectId, optValue]) => {
                    const el = document.querySelector('#' + selectId);
                    if (!el) throw new Error('select nao encontrado: ' + selectId);
                    el.value = optValue;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""",
                [ref.select_id, ref.option_value],
            )
        except Exception as exc:  # noqa: BLE001
            raise FeedSTJError(
                f"select via evaluate falhou para informativo {ref.numero}: {exc}"
            ) from exc
        # AJAX leva ~2-3s pra atualizar o bloco
        page.wait_for_timeout(3000)
        html = _extrair_bloco(page)

    if not html or not html.strip():
        raise FeedSTJError(
            f"bloco vazio apos select para informativo {ref.numero} "
            f"(select={ref.select_id}, value={ref.option_value})"
        )

    # Rate limit antes de gravar (efeito colateral controlado nos tests)
    if rate_limit_seg > 0:
        sleep_fn(rate_limit_seg)

    destino.write_text(html, encoding="utf-8")
    return destino


class FeedSTJError(Exception):
    """Erro no fluxo de descoberta/download de informativos STJ."""

    pass
