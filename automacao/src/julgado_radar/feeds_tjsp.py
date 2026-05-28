"""TJ-SP CJSG (Consulta de Jurisprudencia de Segundo Grau) — scraper com sessao.

**Recalibrado 2026-05-27**: o POST direto em
`esaj.tjsp.jus.br/cjsg/resultadoCompleta.do` retorna 403 sem cookies de
sessao. Diagnostico em
`docs/superpowers/specs/2026-05-27-radar-stj-calibracao.md`.

Estrategia nova ("session-aware scraping"):

1. Abrir um `httpx.Client` (mantem cookies entre requests)
2. GET previo em `esaj.tjsp.jus.br/cjsg/consultaCompleta.do` — devolve
   JSESSIONID via Set-Cookie e o CSRF token escondido num <input>
3. POST em `resultadoCompleta.do` com o CSRF + cookies do GET previo
4. Reusa a mesma sessao entre termos da mesma area (economia de handshake)
5. Parser de HTML segue identico ao anterior (anchor: CNJ no formato
   NNNNNNN-DD.AAAA.J.TR.OOOO)

Sem rede em testes: `session_factory` injetavel devolve um context
manager com objeto que tem `.get(url) -> (status, body, cookies)` e
`.post(url, data) -> (status, body)`. Default abre `httpx.Client` real.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, ContextManager, Optional

from src.julgado_radar.config import (
    RATE_LIMIT_TJSP_SEG,
    TERMOS_BUSCA_TJSP,
    TJSP_TOP_POR_MES_AREA,
)


URL_CJSG_CONSULTA = "https://esaj.tjsp.jus.br/cjsg/consultaCompleta.do"
URL_CJSG = "https://esaj.tjsp.jus.br/cjsg/resultadoCompleta.do"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


# ===== Tipos auxiliares =====

@dataclass
class AcordaoTJSP:
    """Resumo de 1 acordao extraido da pesquisa cjsg (so a ementa, sem PDF)."""

    processo_id: str
    classe: str = ""
    relator: str = ""
    orgao: str = ""
    data_julgamento: str = ""
    data_publicacao: str = ""
    ementa: str = ""
    url_inteiro_teor: str = ""


# Interface minima esperada da sessao injetada pelos testes / default.
class _SessionLike:  # pragma: no cover — protocolo
    def get(self, url: str) -> tuple[int, bytes]: ...
    def post(self, url: str, data: dict) -> tuple[int, bytes]: ...


SessionFactory = Callable[[], ContextManager[_SessionLike]]


class _HttpxSession:  # pragma: no cover — real network
    """Wrapper minimo em torno de httpx.Client para padronizar interface."""

    def __init__(self) -> None:
        import httpx  # noqa: PLC0415

        self._client = httpx.Client(
            headers={
                "User-Agent": _USER_AGENT,
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            },
            timeout=60.0,
            follow_redirects=True,
        )

    def get(self, url: str) -> tuple[int, bytes]:
        resp = self._client.get(url)
        return resp.status_code, resp.content

    def post(self, url: str, data: dict) -> tuple[int, bytes]:
        resp = self._client.post(url, data=data)
        return resp.status_code, resp.content

    def close(self) -> None:
        self._client.close()


@contextmanager
def _default_session_factory():  # pragma: no cover — real network
    """Fallback real: abre httpx.Client (mantem cookies entre requests)."""
    sess = _HttpxSession()
    try:
        yield sess
    finally:
        sess.close()


# ===== CSRF token =====

# CJSG usa input hidden com name="_csrf" (atributos podem aparecer em qualquer ordem)
_RE_CSRF_INPUT = re.compile(
    r'<input[^>]*name=["\']_csrf["\'][^>]*value=["\']([^"\']+)["\']'
    r'|<input[^>]*value=["\']([^"\']+)["\'][^>]*name=["\']_csrf["\']',
    re.IGNORECASE,
)
# Meta tag alternativa (alguns layouts usam): <meta name="_csrf" content="...">
_RE_CSRF_META = re.compile(
    r'<meta[^>]*name=["\']_csrf["\'][^>]*content=["\']([^"\']+)["\']'
    r'|<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']_csrf["\']',
    re.IGNORECASE,
)


def extrair_csrf(html: str) -> str:
    """Extrai o token CSRF do HTML do GET previo. Devolve '' se nao achar."""
    if not html:
        return ""
    for regex in (_RE_CSRF_INPUT, _RE_CSRF_META):
        m = regex.search(html)
        if m:
            # regex tem 2 grupos — um vai estar preenchido, o outro vazio
            return (m.group(1) or m.group(2) or "").strip()
    return ""


# ===== Payload da consulta =====

def montar_payload_cjsg(
    termo: str,
    inicio: date,
    fim: date,
    pagina: int = 1,
    csrf: str = "",
) -> dict:
    """Monta o payload de POST da consulta cjsg para um periodo.

    Inclui CSRF se fornecido (default vazio mantem compat com testes legados).
    Os campos exatos foram observados na pesquisa publica. Datas DD/MM/AAAA.
    """
    payload = {
        "conversationId": "",
        "dadosConsulta.pesquisaLivre": termo,
        "tipoDecisao": "A",  # Acordao
        "dadosConsulta.dataInicial": inicio.strftime("%d/%m/%Y"),
        "dadosConsulta.dataFinal": fim.strftime("%d/%m/%Y"),
        "dadosConsulta.localPesquisa.cdLocal": "-1",
        "dadosConsulta.ordenacao": "DESC",
        "pagina": str(pagina),
    }
    if csrf:
        payload["_csrf"] = csrf
    return payload


# ===== Parser do HTML de resultado (preservado) =====

_RE_PROCESSO_SIMPLES = re.compile(r'(\d{7}-\d{2}\.\d{4}\.\d{1,2}\.\d{2}\.\d{4})')


def _re_label(label_pattern: str, value_pattern: str = r"([^<]+?)") -> re.Pattern:
    return re.compile(
        rf"{label_pattern}\s*:?\s*(?:</[^>]+>\s*)*<[^>]+>\s*{value_pattern}\s*(?:</|<br|$)",
        re.IGNORECASE,
    )


_RE_RELATOR = _re_label(r"Relator(?:\(a\))?")
_RE_ORGAO = _re_label(r"Org[aã]o\s*Julgador")
_RE_CLASSE = _re_label(r"Classe(?:\s*/\s*Assunto)?")
_RE_DATA_JULG = _re_label(r"Data\s*do\s*Julgamento", r"(\d{2}/\d{2}/\d{4})")
_RE_DATA_PUB = _re_label(r"Data\s*de\s*publica[cç][aã]o", r"(\d{2}/\d{2}/\d{4})")
_RE_EMENTA = re.compile(
    r"Ementa\s*:?\s*(?:</[^>]+>\s*)*<[^>]+>(.*?)(?:</td>|</tr>|</span>|</div>)",
    re.DOTALL | re.IGNORECASE,
)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"\s+")


def _limpar_html(s: str) -> str:
    if not s:
        return ""
    sem_tags = _RE_TAG.sub(" ", s)
    return _RE_WS.sub(" ", sem_tags).strip()


def _extrair_um_match(regex: re.Pattern, texto: str) -> str:
    m = regex.search(texto)
    return _limpar_html(m.group(1)) if m else ""


def parse_cjsg_html(html: str) -> list[AcordaoTJSP]:
    """Parseia HTML de resultados do cjsg e devolve lista de AcordaoTJSP."""
    acordaos: list[AcordaoTJSP] = []
    if not html or not html.strip():
        return acordaos

    posicoes = [m.start() for m in _RE_PROCESSO_SIMPLES.finditer(html)]
    if not posicoes:
        return acordaos
    posicoes.append(len(html))

    for i in range(len(posicoes) - 1):
        bloco = html[posicoes[i]:posicoes[i + 1]]
        processo_match = _RE_PROCESSO_SIMPLES.search(bloco)
        if not processo_match:
            continue
        acordaos.append(AcordaoTJSP(
            processo_id=processo_match.group(1),
            classe=_extrair_um_match(_RE_CLASSE, bloco),
            relator=_extrair_um_match(_RE_RELATOR, bloco),
            orgao=_extrair_um_match(_RE_ORGAO, bloco),
            data_julgamento=_extrair_um_match(_RE_DATA_JULG, bloco),
            data_publicacao=_extrair_um_match(_RE_DATA_PUB, bloco),
            ementa=_extrair_um_match(_RE_EMENTA, bloco),
        ))
    return acordaos


# ===== Busca por (area, periodo) — agora session-aware =====

# Backwards compat: assinatura antiga (http_post) ainda funciona pra os
# testes do test_backfill.py que injetam um POST simples. Quando o caller
# passa http_post (legacy), montamos uma sessao fake equivalente.
HttpPostFn = Callable[[str, dict], tuple[int, bytes]]


def _session_factory_from_http_post(http_post: HttpPostFn) -> SessionFactory:
    """Constroi uma SessionFactory equivalente a partir de uma funcao
    `http_post` legada. O GET previo devolve sempre 200/empty (sem CSRF)
    — adequado para testes que nao se importam com a sessao."""
    class _LegacySession:
        def get(self, url: str) -> tuple[int, bytes]:
            return 200, b""

        def post(self, url: str, data: dict) -> tuple[int, bytes]:
            return http_post(url, data)

    @contextmanager
    def factory():
        yield _LegacySession()
    return factory


def buscar_acordaos(
    area: str,
    inicio: date,
    fim: date,
    *,
    session_factory: Optional[SessionFactory] = None,
    http_post: Optional[HttpPostFn] = None,  # backcompat
    rate_limit_seg: float = RATE_LIMIT_TJSP_SEG,
    sleep_fn: Callable[[float], None] = time.sleep,
    top_n: int = TJSP_TOP_POR_MES_AREA,
) -> list[AcordaoTJSP]:
    """Busca acordaos por (area, periodo) com sessao reusada entre termos.

    Fluxo:
    1. Abre sessao (com cookies)
    2. GET em consultaCompleta.do → captura JSESSIONID + CSRF
    3. Para cada termo da area: POST em resultadoCompleta.do reusando cookies
    4. Dedup por processo_id, limita ao top_n
    5. Rate limit entre POSTs (nao antes do primeiro)

    Backwards compat: se `http_post` for passado (legacy), constroi sessao
    fake que ignora o GET previo. Recomendado migrar pra session_factory.
    """
    termos = TERMOS_BUSCA_TJSP.get(area, ())
    if not termos:
        return []

    if session_factory is None:
        if http_post is not None:
            session_factory = _session_factory_from_http_post(http_post)
        else:
            session_factory = _default_session_factory

    todos: dict[str, AcordaoTJSP] = {}

    with session_factory() as sess:
        # GET previo: captura cookies + CSRF (tolerante a falha — testes
        # legacy podem devolver 200 vazio)
        try:
            status_g, body_g = sess.get(URL_CJSG_CONSULTA)
        except Exception:  # noqa: BLE001
            status_g, body_g = 0, b""
        csrf = ""
        if status_g == 200 and body_g:
            csrf = extrair_csrf(body_g.decode("utf-8", errors="replace"))

        for i, termo in enumerate(termos):
            if i > 0 and rate_limit_seg > 0:
                sleep_fn(rate_limit_seg)
            payload = montar_payload_cjsg(termo, inicio, fim, csrf=csrf)
            try:
                status, body = sess.post(URL_CJSG, payload)
            except Exception:  # noqa: BLE001
                continue
            if status != 200 or not body:
                continue
            html = body.decode("utf-8", errors="replace")
            for a in parse_cjsg_html(html):
                if a.processo_id not in todos:
                    todos[a.processo_id] = a
                if len(todos) >= top_n:
                    break
            if len(todos) >= top_n:
                break

    return list(todos.values())[:top_n]


def fonte_key(area: str, ano: int, mes: int) -> str:
    """Chave de idempotencia pra fetch_log."""
    return f"tjsp-cjsg-{ano}-{mes:02d}-{area}"
