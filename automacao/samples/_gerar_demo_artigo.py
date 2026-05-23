"""Gera prévia do artigo estilizado (Batch 1.5 — SEO + bio + callouts novos).

Busca rascunho do WP, aplica article_styler.estilizar(), renderiza via Playwright
em alta resolução e quebra em 3 crops para revisão.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# carrega .env manualmente (procura no parent tambem)
for env_file in (ROOT / ".env", ROOT.parent / ".env"):
    if env_file.exists():
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from article_styler import estilizar  # noqa: E402

# WP
WP_URL = os.environ.get("WP_URL", "https://noviello.adv.br").rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_APP_PWD = os.environ["WP_APP_PASSWORD_NOVIELLO"]
POST_ID = 11746

OUT = ROOT / "samples"
OUT.mkdir(exist_ok=True)


def buscar_post() -> dict:
    r = httpx.get(
        f"{WP_URL}/wp-json/wp/v2/posts/{POST_ID}?context=edit",
        auth=(WP_USER, WP_APP_PWD),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def buscar_categorias(ids: list[int]) -> list[str]:
    nomes = []
    for cid in ids:
        try:
            r = httpx.get(
                f"{WP_URL}/wp-json/wp/v2/categories/{cid}",
                auth=(WP_USER, WP_APP_PWD),
                timeout=15,
            )
            if r.status_code == 200:
                nomes.append(r.json()["name"])
        except Exception:
            pass
    return nomes


def buscar_tags(ids: list[int]) -> list[str]:
    nomes = []
    for tid in ids:
        try:
            r = httpx.get(
                f"{WP_URL}/wp-json/wp/v2/tags/{tid}",
                auth=(WP_USER, WP_APP_PWD),
                timeout=15,
            )
            if r.status_code == 200:
                nomes.append(r.json()["name"])
        except Exception:
            pass
    return nomes


def main() -> None:
    print(f"Buscando post {POST_ID}...")
    post = buscar_post()
    titulo = post["title"]["raw"] or post["title"]["rendered"]
    conteudo = post["content"]["raw"] or post["content"]["rendered"]
    categorias_ids = post.get("categories", [])
    categorias = buscar_categorias(categorias_ids)
    tags_ids = post.get("tags", [])
    tags = buscar_tags(tags_ids)
    # se nao tem tags do WP, derivo do titulo (palavras-chave)
    if not tags:
        tags = ["Planejamento Sucessório", "Doação", "Usufruto", "Direito Imobiliário",
                "OAB 205/2021", "Direito Sênior"]
    print(f"  titulo: {titulo}")
    print(f"  categorias: {categorias}")
    print(f"  tags: {tags}")
    print(f"  tamanho HTML cru: {len(conteudo)} chars")

    # link da imagem destacada (se houver)
    img_destaque_url = None
    fid = post.get("featured_media")
    if fid:
        try:
            r = httpx.get(
                f"{WP_URL}/wp-json/wp/v2/media/{fid}",
                auth=(WP_USER, WP_APP_PWD),
                timeout=15,
            )
            if r.status_code == 200:
                img_destaque_url = r.json().get("source_url")
                print(f"  imagem destacada: {img_destaque_url}")
        except Exception:
            pass

    print("\nEstilizando...")
    html = estilizar(
        conteudo,
        titulo=titulo,
        templates_dir=ROOT / "templates",
        categorias=categorias or ["Sucessório"],
        tags=tags,
        imagem_destaque=img_destaque_url,
        data_publicacao=date.today(),
        canonical_url=post.get("link", f"{WP_URL}/?p={POST_ID}"),
    )
    print(f"  tamanho HTML final: {len(html)} chars")

    arq_html = OUT / "demo-artigo-11746.html"
    arq_html.write_text(html, encoding="utf-8")
    print(f"  HTML salvo: {arq_html}")

    print("\nRenderizando via Playwright...")
    arq_png = OUT / "demo-artigo-11746-fullpage.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 1200})
        page.goto(f"file://{arq_html.as_posix()}", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(arq_png), full_page=True, type="png")
        browser.close()
    print(f"  screenshot: {arq_png}")

    print("\nCortando em 3 secoes...")
    img = Image.open(arq_png)
    w, h = img.size
    print(f"  tamanho total: {w}x{h}")
    # divisao: topo=ate 1500, meio=1500-fim-1500, fim=ultimos 1800
    topo = img.crop((0, 0, w, min(1500, h)))
    fim_inicio = max(0, h - 1800)
    fim = img.crop((0, fim_inicio, w, h))
    if fim_inicio > 1500:
        meio = img.crop((0, 1500, w, fim_inicio))
    else:
        meio = None

    topo.convert("RGB").save(OUT / "demo-artigo-1-topo.jpg", quality=85)
    print(f"  topo: {OUT / 'demo-artigo-1-topo.jpg'}")
    if meio is not None:
        meio.convert("RGB").save(OUT / "demo-artigo-2-meio.jpg", quality=85)
        print(f"  meio: {OUT / 'demo-artigo-2-meio.jpg'}")
    fim.convert("RGB").save(OUT / "demo-artigo-3-fim.jpg", quality=85)
    print(f"  fim:  {OUT / 'demo-artigo-3-fim.jpg'}")

    print("\nPronto.")


if __name__ == "__main__":
    main()
