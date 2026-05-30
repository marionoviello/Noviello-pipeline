"""Motor de padronizacao do blog — re-estiliza todos os posts no padrao Noviello.

Para cada post:
  1. limpa o HTML legado (article_styler.limpar_html_legado)
  2. re-estiliza no template novo (hero sintetico, largura 1240, allowlist)
  3. valida #BrandLockProtocol (cores/glyphs)
  4. gera a capa da marca (capa_marca) e renderiza JPG via Playwright
  5. [se nao --dry-run] sobe a capa como featured + atualiza o content no WP
  6. salva amostra (html + capa) em producao/_padronizacao/ para revisao

Backup-fonte: state/backup-blog-conteudos-20260529.json (NAO consulta o WP pra ler;
usa o backup, garantindo idempotencia e seguranca).

Uso:
  python -m samples._padronizar_blog --limite 3 --dry-run   # piloto, sem publicar
  python -m samples._padronizar_blog --limite 3             # piloto, publica 3
  python -m samples._padronizar_blog                         # lote completo (108)
"""

from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from src.article_styler import estilizar, limpar_html_legado
from src.capa_marca import gerar_html_capa
from src.config import load_config

BACKUP = Path("state/backup-blog-conteudos-20260529.json")
AMOSTRAS = Path("producao/_padronizacao")
BASE = "https://noviello.adv.br/wp-json/wp/v2"
PALETA = {"68192E", "540D1D", "F1F3F2", "FFFFFF", "FFF", "1A1A1A", "444444", "000000"}
# cor real e seguida de nao-alfanumerico; evita falso-positivo de ancora href="#efe..."
_RE_HEX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z])|#[0-9a-fA-F]{3}(?![0-9a-zA-Z])")
_RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⚐-⚗⚔⚱\U0001F3DB]")
_RE_GLYPH = re.compile(r'content:\s*["\']\\?(2696|2694|26B1|1F4D6|1F3DB)', re.I)
# categorias a ignorar no kicker/area
_CAT_IGNORAR = {"sem categoria", "fila social", "backlog editorial"}


def brandlock_erros(html: str) -> list[str]:
    erros = []
    off = sorted({h[1:].upper() for h in _RE_HEX.findall(html)} - PALETA)
    if off:
        erros.append("cores: " + ", ".join("#" + h for h in off))
    if _RE_EMOJI.search(html):
        erros.append("emoji/icone")
    if _RE_GLYPH.search(html):
        erros.append("glyph CSS")
    return erros


def carregar_taxonomias(auth) -> tuple[dict, dict]:
    """Mapas id->nome de categorias e tags."""
    def baixar(rota):
        m = {}
        pag = 1
        while True:
            r = httpx.get(f"{BASE}/{rota}", auth=auth, timeout=60,
                          params={"per_page": 100, "page": pag, "_fields": "id,name"})
            if r.status_code != 200:
                break
            lote = r.json()
            if not lote:
                break
            for it in lote:
                m[it["id"]] = it["name"]
            if len(lote) < 100:
                break
            pag += 1
        return m
    return baixar("categories"), baixar("tags")


def area_do_post(cat_ids, cat_map) -> list[str]:
    nomes = [cat_map.get(cid, "") for cid in (cat_ids or [])]
    nomes = [n for n in nomes if n and n.strip().lower() not in _CAT_IGNORAR]
    return nomes[:3]


def montar_content(html_artigo: str, logo_url: str) -> str:
    """Extrai <style>+<body interno> e envolve em wp:html (pronto pro WP)."""
    style = html_artigo[html_artigo.index("<style>"):html_artigo.index("</style>") + 8]
    body = html_artigo[html_artigo.index("<body>") + 6:html_artigo.index("</body>")]
    body = body.replace('src="logo-noviello-branco.png"', f'src="{logo_url}"')
    return "<!-- wp:html -->\n" + style + body + "\n<!-- /wp:html -->"


def processar(post, cat_map, tag_map, page, cfg, auth, dry_run) -> dict:
    pid = post["id"]
    titulo = _html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"])).strip()
    raw = post["content"]["raw"]
    areas = area_do_post(post.get("categories"), cat_map)
    tags = [tag_map.get(t, "") for t in (post.get("tags") or [])]
    tags = [t for t in tags if t][:6]
    try:
        d = datetime.fromisoformat(post["date"])
    except Exception:  # noqa: BLE001
        d = None

    # 1-2. limpa + estiliza
    limpo = limpar_html_legado(raw)
    artigo = estilizar(
        limpo, titulo, Path("templates"),
        categorias=areas or None, tags=tags or None,
        data_publicacao=d, canonical_url=post.get("link", ""),
    )
    # 3. brandlock
    erros = brandlock_erros(artigo)
    if erros:
        return {"id": pid, "titulo": titulo, "ok": False, "erro": "brandlock: " + "; ".join(erros)}

    # 4. capa
    AMOSTRAS.mkdir(parents=True, exist_ok=True)
    capa_html = gerar_html_capa(area=" · ".join(areas) if areas else "Noviello Advocacia",
                               titulo=titulo)
    page.set_content(capa_html)
    page.wait_for_timeout(900)
    capa_path = AMOSTRAS / f"capa-{pid}.jpg"
    page.locator(".capa").screenshot(path=str(capa_path), type="jpeg", quality=88)
    (AMOSTRAS / f"artigo-{pid}.html").write_text(artigo, encoding="utf-8")

    if dry_run:
        return {"id": pid, "titulo": titulo, "ok": True, "dry_run": True,
                "areas": areas, "capa": str(capa_path)}

    # 5. publica: upload capa -> featured + content
    try:
        m = httpx.post(f"{BASE}/media", auth=auth, timeout=120,
                       headers={"Content-Disposition": f"attachment; filename=capa-noviello-{pid}.jpg",
                                "Content-Type": "image/jpeg"},
                       content=capa_path.read_bytes())
        m.raise_for_status()
        capa_id = m.json()["id"]
        logo_url = "https://noviello.adv.br/wp-content/uploads/2026/05/logo-noviello-branco.png"
        content = montar_content(artigo, logo_url)
        r = httpx.post(f"{BASE}/posts/{pid}", auth=auth, timeout=120,
                       json={"content": content, "featured_media": capa_id})
        r.raise_for_status()
        return {"id": pid, "titulo": titulo, "ok": True, "capa_id": capa_id,
                "link": r.json().get("link", "")}
    except Exception as exc:  # noqa: BLE001
        return {"id": pid, "titulo": titulo, "ok": False, "erro": f"publish: {str(exc)[:120]}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=0, help="processar so N posts (0 = todos)")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="gera/valida sem publicar")
    args = ap.parse_args(argv)

    cfg = load_config()
    auth = (cfg.wordpress["user"], cfg.wordpress.get("app_password_noviello", ""))
    posts = json.loads(BACKUP.read_text(encoding="utf-8"))
    posts = sorted(posts, key=lambda p: p.get("date", ""), reverse=True)  # recentes 1o
    if args.offset:
        posts = posts[args.offset:]
    if args.limite:
        posts = posts[:args.limite]

    print(f"Padronizacao: {len(posts)} posts | dry_run={args.dry_run}")
    cat_map, tag_map = carregar_taxonomias(auth)
    print(f"taxonomias: {len(cat_map)} categorias, {len(tag_map)} tags\n")

    from playwright.sync_api import sync_playwright
    ok, falhas = [], []
    t0 = time.monotonic()
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
        for i, post in enumerate(posts, 1):
            res = processar(post, cat_map, tag_map, page, cfg, auth, args.dry_run)
            status = "OK " if res["ok"] else "XX "
            print(f"  [{i}/{len(posts)}] {status}{res['id']}  {res['titulo'][:48]}"
                  + ("" if res["ok"] else f"  -> {res.get('erro','')}"))
            (ok if res["ok"] else falhas).append(res)
        b.close()

    dur = time.monotonic() - t0
    print(f"\n===== RESUMO ({dur:.0f}s) =====")
    print(f"OK: {len(ok)} | FALHAS: {len(falhas)}")
    if falhas:
        print("Falhas:")
        for f in falhas:
            print(f"  {f['id']}: {f.get('erro','')}")
    print(f"\nAmostras (html + capa) em: {AMOSTRAS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
