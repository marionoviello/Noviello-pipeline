"""Busca o corpus recente do blog para passar como contexto à IA.

A ideia: a IA pode referenciar artigos anteriores, evitar repeticao tematica,
e fazer cross-link mais inteligente. Sem isso, ela gera cada peca em vacuo.

Estrategia:
- Top N artigos publicados (orderby=date desc), so titulo + primeiros 500 chars
  limpos de HTML. Cabe em ~5-10K tokens.
- Cache em `state/corpus-cache.json` com TTL de 24h (corpus muda devagar).
- Em prompt: bloco `user` com `cache_control: ephemeral` (Anthropic reusa entre
  chamadas dentro da janela de cache de 5min).
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import re
from pathlib import Path

import requests

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_CACHE_NOME = "corpus-cache.json"


def _limpar_html(texto: str, limite: int = 500) -> str:
    """Remove tags HTML, decodifica entidades, normaliza espacos, trunca."""
    sem_tag = _TAG_RE.sub(" ", texto)
    decodificado = _html.unescape(sem_tag)
    normalizado = _WS_RE.sub(" ", decodificado).strip()
    if len(normalizado) > limite:
        normalizado = normalizado[:limite].rsplit(" ", 1)[0] + "…"
    return normalizado


def _buscar_artigos_wp(wp_base: str, auth: tuple[str, str], top_n: int) -> list[dict]:
    """Busca os top N artigos publicados via WP REST. Devolve lista bruta."""
    r = requests.get(
        f"{wp_base.rstrip('/')}/wp-json/wp/v2/posts",
        params={
            "per_page": top_n,
            "status": "publish",
            "orderby": "date",
            "order": "desc",
            "_fields": "id,date,slug,title,content,categories",
        },
        auth=auth,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _normalizar(post: dict, excerpt_chars: int) -> dict:
    titulo = (post.get("title") or {}).get("rendered", "")
    conteudo = (post.get("content") or {}).get("rendered", "")
    return {
        "id": post.get("id"),
        "slug": post.get("slug", ""),
        "data": (post.get("date", "") or "")[:10],
        "titulo": _html.unescape(titulo).strip(),
        "excerpt": _limpar_html(conteudo, limite=excerpt_chars),
    }


def _formatar_para_prompt(artigos: list[dict]) -> str:
    """Constroi o bloco de texto que vai no prompt da IA."""
    if not artigos:
        return ""
    linhas = [
        "ARTIGOS RECENTES DO BLOG NOVIELLO (referencia para cross-link e",
        "para evitar repetir conteudo ja publicado):",
        "",
    ]
    for a in artigos:
        linhas.append(f"## {a['titulo']}")
        linhas.append(f"**slug:** {a['slug']}  **data:** {a['data']}")
        linhas.append("")
        linhas.append(a["excerpt"])
        linhas.append("")
        linhas.append("---")
        linhas.append("")
    return "\n".join(linhas)


def pegar_corpus_blog(
    state_dir: Path,
    wp_base: str,
    auth: tuple[str, str],
    top_n: int = 20,
    excerpt_chars: int = 500,
    ttl_horas: float = 24.0,
    *,
    fetcher=_buscar_artigos_wp,  # injetavel para testes
) -> str:
    """Devolve o corpus do blog formatado como string para o prompt.

    Cache em `state_dir/corpus-cache.json` com TTL de `ttl_horas`. Se o cache
    estiver fresco, reusa. Caso contrario, busca via WP REST e atualiza.

    Em caso de erro na busca: se tem cache (mesmo expirado), usa o cached;
    senao, devolve "" (silencioso — pipeline nao quebra por causa do corpus).
    """
    cache_path = Path(state_dir) / _CACHE_NOME
    agora = _dt.datetime.now().astimezone()

    cache_data: dict | None = None
    if cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache_data = None

    cache_fresco = False
    if cache_data and cache_data.get("atualizado_em"):
        try:
            atualizado = _dt.datetime.fromisoformat(cache_data["atualizado_em"])
            idade = (agora - atualizado).total_seconds() / 3600.0
            cache_fresco = idade < ttl_horas
        except ValueError:
            pass

    if cache_fresco and cache_data:
        return cache_data.get("texto", "")

    # Cache expirado ou ausente: busca novo
    try:
        posts = fetcher(wp_base, auth, top_n)
        artigos = [_normalizar(p, excerpt_chars) for p in posts]
        texto = _formatar_para_prompt(artigos)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {"atualizado_em": agora.isoformat(timespec="seconds"), "texto": texto},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return texto
    except Exception:  # noqa: BLE001 — qualquer falha de rede/WP
        # Fallback: cache antigo se existir, senao vazio
        if cache_data and cache_data.get("texto"):
            return cache_data["texto"]
        return ""
