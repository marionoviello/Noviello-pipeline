"""TJ-SP CJSG (Consulta de Jurisprudencia de Segundo Grau) — scraper.

A consulta cjsg do TJ-SP e um formulario POST que devolve HTML com cards de
resultados. Esta fonte:
1. Monta queries por (area, ano-mes) com termos da config TERMOS_BUSCA_TJSP.
2. POST httpx pra cjsg/resultadoCompleta.do.
3. Parse do HTML de resultados extrai (processo, classe, relator, orgao, data,
   ementa) de cada card.
4. Caller filtra por TJSP_TOP_POR_MES_AREA.

Sem inteiro teor nesta wave (so a ementa que vem na pesquisa). Inteiro teor
e baixado sob demanda quando Mario clica "usar este" (Wave 5).

Sem rede em testes: http_post e parametro injetavel.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from src.julgado_radar.config import (
    RATE_LIMIT_TJSP_SEG,
    TERMOS_BUSCA_TJSP,
    TJSP_TOP_POR_MES_AREA,
    TRIBUNAL_TJSP,
)


URL_CJSG = "https://esaj.tjsp.jus.br/cjsg/resultadoCompleta.do"


HttpPostFn = Callable[[str, dict], tuple[int, bytes]]


def _http_post_default(url: str, params: dict) -> tuple[int, bytes]:  # pragma: no cover
    """Fallback real (usado fora dos testes)."""
    import httpx  # noqa: PLC0415

    resp = httpx.post(
        url,
        data=params,
        headers={"User-Agent": "Noviello-Radar/1.0 (+contato: mario@noviello.adv.br)"},
        timeout=60.0,
        follow_redirects=True,
    )
    return resp.status_code, resp.content


@dataclass
class AcordaoTJSP:
    """Resumo de 1 acordao do TJ-SP extraido da pesquisa cjsg.

    Inteiro teor (PDF) NAO e baixado aqui — so quando Mario marcar "usar este".
    """

    processo_id: str
    classe: str = ""
    relator: str = ""
    orgao: str = ""
    data_julgamento: str = ""
    data_publicacao: str = ""
    ementa: str = ""
    url_inteiro_teor: str = ""


# ===== Construcao da query =====

def montar_payload_cjsg(
    termo: str,
    inicio: date,
    fim: date,
    pagina: int = 1,
) -> dict:
    """Monta o payload de POST da consulta cjsg para um periodo.

    Os campos exatos foram observados na pesquisa publica. Caso o TJ-SP
    mude o formulario, ajustar aqui. Datas em DD/MM/AAAA.
    """
    return {
        "conversationId": "",
        "dadosConsulta.pesquisaLivre": termo,
        "tipoDecisao": "A",  # Acordao
        "dadosConsulta.dataInicial": inicio.strftime("%d/%m/%Y"),
        "dadosConsulta.dataFinal": fim.strftime("%d/%m/%Y"),
        "dadosConsulta.localPesquisa.cdLocal": "-1",  # todos os foros
        "dadosConsulta.ordenacao": "DESC",
        "pagina": str(pagina),
    }


# ===== Parser do HTML de resultado =====

# Regexes resilientes a variacoes de espacamento e tags.
# Estrategia: depois do label "Foo:", aceita qualquer combo de tags ate o
# proximo conteudo textual visivel.
_RE_PROCESSO_SIMPLES = re.compile(r'(\d{7}-\d{2}\.\d{4}\.\d{1,2}\.\d{2}\.\d{4})')


def _re_label(label_pattern: str, value_pattern: str = r"([^<]+?)") -> re.Pattern:
    """Constroi regex tolerante: 'LABEL:' + qualquer tag/espaco + VALOR + fim de tag/linha."""
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
    """Remove tags HTML e normaliza whitespace."""
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

    # Estrategia: divide o HTML por divs/li que representam 1 acordao.
    # O cjsg usa varios layouts ao longo do tempo. Aqui aceitamos a presenca
    # de processo no formato CNJ como ancora primaria.
    processos = _RE_PROCESSO_SIMPLES.finditer(html)
    cards_brutos: list[tuple[int, int]] = []
    posicoes = [m.start() for m in processos]
    if not posicoes:
        return acordaos
    posicoes.append(len(html))
    for i in range(len(posicoes) - 1):
        cards_brutos.append((posicoes[i], posicoes[i + 1]))

    for ini, fim in cards_brutos:
        bloco = html[ini:fim]
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


# ===== Busca por (area, periodo) =====

def buscar_acordaos(
    area: str,
    inicio: date,
    fim: date,
    *,
    http_post: Optional[HttpPostFn] = None,
    rate_limit_seg: float = RATE_LIMIT_TJSP_SEG,
    sleep_fn: Callable[[float], None] = time.sleep,
    top_n: int = TJSP_TOP_POR_MES_AREA,
) -> list[AcordaoTJSP]:
    """Itera termos de busca da area, agrega resultados e devolve top_n.

    Cada termo dispara 1 POST. Rate limit entre POSTs.
    """
    poster = http_post or _http_post_default
    termos = TERMOS_BUSCA_TJSP.get(area, ())
    if not termos:
        return []

    todos: dict[str, AcordaoTJSP] = {}  # dedup por processo_id
    for termo in termos:
        if rate_limit_seg > 0 and todos:  # nao dorme antes do primeiro
            sleep_fn(rate_limit_seg)
        payload = montar_payload_cjsg(termo, inicio, fim)
        status, body = poster(URL_CJSG, payload)
        if status != 200 or not body:
            continue
        html = body.decode("utf-8", errors="replace")
        acordaos = parse_cjsg_html(html)
        for a in acordaos:
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
