"""Leitura da fonte de conteudo — artigos do plugin na categoria "Fila Social".

O Mario marca um artigo do "Gerador IA Pro" com a categoria "Fila Social". Esta
camada le esses artigos via WP REST para a ponte de producao processar.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field

from src.wp_client import WordPressClient

SITE = "noviello"  # a Fila Social vive no site principal


@dataclass
class ArtigoFonte:
    post_id: int
    titulo: str
    slug: str
    conteudo_html: str  # HTML cru do plugin (post_content.raw)
    categorias: list[int]
    status: str
    # enriquecimento (resolvido em listar_fila_social):
    tags: list[int] = field(default_factory=list)
    categorias_nomes: list[str] = field(default_factory=list)
    tags_nomes: list[str] = field(default_factory=list)
    featured_media_id: int = 0  # 0 = sem imagem destacada
    featured_media_url: str = ""


class CategoriaNaoEncontrada(Exception):
    pass


class WordPressSource:
    def __init__(self, wp_client: WordPressClient, categoria_nome: str):
        self._wp = wp_client
        self._categoria_nome = categoria_nome
        self._categoria_id: int | None = None

    def categoria_id(self) -> int:
        """ID da categoria "Fila Social" (resolvido uma vez, em cache)."""
        if self._categoria_id is None:
            for cat in self._wp.get_categories(SITE, self._categoria_nome):
                if cat.get("name", "").strip().lower() == self._categoria_nome.strip().lower():
                    self._categoria_id = cat["id"]
                    break
            if self._categoria_id is None:
                raise CategoriaNaoEncontrada(
                    f"categoria '{self._categoria_nome}' nao existe em {SITE}.adv.br — "
                    "crie-a no wp-admin."
                )
        return self._categoria_id

    def listar_fila_social(self) -> list[ArtigoFonte]:
        """Artigos na categoria Fila Social, ainda nao publicados.

        Enriquece com categorias_nomes, tags_nomes e featured_media_url via
        lookups em batch (uma chamada por taxonomy + uma por media).
        """
        posts = self._wp.get_posts(
            SITE,
            {
                "categories": self.categoria_id(),
                "status": "draft,pending",
                "per_page": 30,
                "context": "edit",
                "_fields": "id,title,slug,content,categories,tags,featured_media,status",
            },
        )
        if not posts:
            return []

        # batch lookup de categorias e tags (1 GET cada)
        cat_id_para_nome: dict[int, str] = {}
        tag_id_para_nome: dict[int, str] = {}
        midia_id_para_url: dict[int, str] = {}
        try:
            cats = self._wp.get_json(SITE, "categories", {"per_page": 100})
            cat_id_para_nome = {c["id"]: c.get("name", "") for c in cats}
        except Exception:  # noqa: BLE001
            pass
        try:
            tags = self._wp.get_json(SITE, "tags", {"per_page": 100})
            tag_id_para_nome = {t["id"]: t.get("name", "") for t in tags}
        except Exception:  # noqa: BLE001
            pass
        # featured media: 1 lookup individual por post (so quando tem)
        for p in posts:
            fid = p.get("featured_media") or 0
            if fid and fid not in midia_id_para_url:
                try:
                    m = self._wp.get_json(SITE, f"media/{fid}", {})
                    midia_id_para_url[fid] = m.get("source_url", "") if isinstance(m, dict) else ""
                except Exception:  # noqa: BLE001
                    midia_id_para_url[fid] = ""

        artigos = []
        for p in posts:
            titulo = p.get("title", {})
            titulo = titulo.get("raw") or titulo.get("rendered", "")
            conteudo = p.get("content", {})
            conteudo = conteudo.get("raw") or conteudo.get("rendered", "")
            cats_ids = p.get("categories", [])
            tags_ids = p.get("tags", [])
            fid = p.get("featured_media") or 0

            artigos.append(
                ArtigoFonte(
                    post_id=p["id"],
                    titulo=_html.unescape(titulo),
                    slug=p.get("slug", ""),
                    conteudo_html=conteudo,
                    categorias=cats_ids,
                    status=p.get("status", ""),
                    tags=tags_ids,
                    categorias_nomes=[cat_id_para_nome.get(c, "") for c in cats_ids if cat_id_para_nome.get(c)],
                    tags_nomes=[tag_id_para_nome.get(t, "") for t in tags_ids if tag_id_para_nome.get(t)],
                    featured_media_id=fid,
                    featured_media_url=midia_id_para_url.get(fid, ""),
                )
            )
        return artigos
