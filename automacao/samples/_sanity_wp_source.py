"""Sanity: lista a Fila Social com enriquecimento (tags/cats/featured)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

for env_file in (ROOT / ".env", ROOT.parent / ".env"):
    if env_file.exists():
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from src.wp_client import WordPressClient  # noqa: E402
from src.wp_source import WordPressSource  # noqa: E402

wp = WordPressClient(
    os.environ["WP_USER"],
    {
        "noviello": os.environ["WP_APP_PASSWORD_NOVIELLO"],
        "imobiliario": os.environ.get("WP_APP_PASSWORD_IMOBILIARIO", ""),
    },
)
src = WordPressSource(wp, "Fila Social")
artigos = src.listar_fila_social()
print(f"\n{len(artigos)} artigos na Fila Social:\n")
for a in artigos[:5]:
    print(f"  [{a.post_id}] {a.titulo}")
    print(f"    slug: {a.slug}")
    print(f"    status: {a.status}")
    print(f"    categorias: {a.categorias_nomes}")
    print(f"    tags: {a.tags_nomes}")
    print(f"    featured_media: id={a.featured_media_id} url={a.featured_media_url[:80] if a.featured_media_url else '(none)'}")
    print()
