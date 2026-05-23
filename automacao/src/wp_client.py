"""Cliente WordPress REST — upload de midia e criacao de posts.

Autenticacao via Application Password (Basic Auth). Usado pelo publisher de WordPress
e tambem pelo publisher de Instagram (que hospeda os slides na midia do WP para obter
URLs publicas — a Graph API exige image_url publica, nao aceita upload local).
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from src.http_retry import transient_retry

SITES = {
    "noviello": "https://noviello.adv.br/wp-json/wp/v2",
    "imobiliario": "https://imobiliario.noviello.adv.br/wp-json/wp/v2",
}

_TIMEOUT = httpx.Timeout(120.0, connect=30.0)


class WordPressError(Exception):
    pass


class WordPressClient:
    def __init__(self, user: str, app_passwords: dict[str, str]):
        """app_passwords = {"noviello": "...", "imobiliario": "..."}."""
        self._user = user
        self._pw = app_passwords

    def site_disponivel(self, site: str) -> bool:
        return bool(self._user and self._pw.get(site))

    def _headers(self, site: str) -> dict:
        pw = self._pw.get(site)
        if not (self._user and pw):
            raise WordPressError(f"credencial WordPress ausente para o site '{site}'")
        token = base64.b64encode(f"{self._user}:{pw}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    @staticmethod
    def _base(site: str) -> str:
        if site not in SITES:
            raise WordPressError(f"site desconhecido: '{site}' (use {list(SITES)})")
        return SITES[site]

    @transient_retry
    def upload_media(self, path, site: str) -> dict:
        """Sobe um arquivo na biblioteca de midia. Devolve {id, source_url}."""
        path = Path(path)
        ctype = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        headers = {
            **self._headers(site),
            "Content-Disposition": f'attachment; filename="{path.name}"',
            "Content-Type": ctype,
        }
        resp = httpx.post(
            f"{self._base(site)}/media",
            headers=headers,
            content=path.read_bytes(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
        return {"id": dados["id"], "source_url": dados["source_url"]}

    @transient_retry
    def _resolve_term(self, taxonomy: str, nome: str, site: str) -> int:
        """Devolve o ID de uma categoria/tag pelo nome, criando se nao existir."""
        resp = httpx.get(
            f"{self._base(site)}/{taxonomy}",
            params={"search": nome},
            headers=self._headers(site),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        for item in resp.json():
            if item.get("name", "").lower() == nome.lower():
                return item["id"]
        criado = httpx.post(
            f"{self._base(site)}/{taxonomy}",
            json={"name": nome},
            headers=self._headers(site),
            timeout=_TIMEOUT,
        )
        criado.raise_for_status()
        return criado.json()["id"]

    @transient_retry
    def create_post(
        self,
        site: str,
        *,
        titulo: str,
        slug: str,
        conteudo_html: str,
        status: str = "publish",
        featured_media: int | None = None,
        categoria: str | None = None,
        tags: list[str] | None = None,
        meta_description: str = "",
        data: str | None = None,
    ) -> dict:
        """Cria um post. Devolve {id, link}."""
        corpo: dict = {
            "title": titulo,
            "slug": slug,
            "content": conteudo_html,
            "status": status,
        }
        if featured_media:
            corpo["featured_media"] = featured_media
        if categoria:
            corpo["categories"] = [self._resolve_term("categories", categoria, site)]
        if tags:
            corpo["tags"] = [self._resolve_term("tags", t, site) for t in tags]
        if meta_description:
            corpo["excerpt"] = meta_description
        if data and status == "future":
            corpo["date"] = data

        resp = httpx.post(
            f"{self._base(site)}/posts",
            json=corpo,
            headers=self._headers(site),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
        return {"id": dados["id"], "link": dados["link"]}

    # ---- leitura ---------------------------------------------------------
    @transient_retry
    def get_json(self, site: str, endpoint: str, params: dict | None = None) -> list | dict:
        """GET generico autenticado em /wp/v2/<endpoint>."""
        resp = httpx.get(
            f"{self._base(site)}/{endpoint}",
            params=params or {},
            headers=self._headers(site),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def get_categories(self, site: str, search: str) -> list:
        return self.get_json(site, "categories", {"search": search, "per_page": 50})

    def get_posts(self, site: str, params: dict) -> list:
        return self.get_json(site, "posts", params)

    @transient_retry
    def update_post(self, site: str, post_id, campos: dict) -> dict:
        """Atualiza um post existente (POST /wp/v2/posts/{id}). Devolve {id, link}."""
        resp = httpx.post(
            f"{self._base(site)}/posts/{post_id}",
            json=campos,
            headers=self._headers(site),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
        return {"id": dados["id"], "link": dados["link"]}
