"""Sanity: simula o pipeline producer.processar_artigo_novo apenas para a
parte de estilizacao (sem chamar Anthropic). Confirma que os campos novos
(tags, categorias, imagem destaque, canonical) sao passados corretamente."""

from __future__ import annotations

import datetime as _dt
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

from src import article_styler  # noqa: E402
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

if not artigos:
    print("Nenhum artigo na Fila Social.")
    sys.exit(0)

# pega o primeiro pra estilizar como o producer faria
a = artigos[0]
print(f"Estilizando: [{a.post_id}] {a.titulo}")
print(f"  cats: {a.categorias_nomes}")
print(f"  tags: {a.tags_nomes}")
print(f"  featured: {a.featured_media_url[:80]}...")

canonical = (
    f"https://noviello.adv.br/{a.slug}/" if a.slug
    else f"https://noviello.adv.br/?p={a.post_id}"
)

html = article_styler.estilizar(
    a.conteudo_html,
    a.titulo,
    ROOT / "templates",
    categorias=a.categorias_nomes or None,
    tags=a.tags_nomes or None,
    imagem_destaque=a.featured_media_url or None,
    data_publicacao=_dt.date.today(),
    canonical_url=canonical,
)

destino = ROOT / "samples" / f"pipeline-real-{a.post_id}.html"
destino.write_text(html, encoding="utf-8")
print(f"\nHTML salvo: {destino}")
print(f"tamanho: {len(html)} chars")

# checks rapidos
print("\nChecks:")
print(f"  canonical no head: {'rel=\"canonical\" href=\"' + canonical + '\"' in html}")
print(f"  og:image: {'property=\"og:image\" content=\"' + a.featured_media_url + '\"' in html}")
print(f"  JSON-LD Article: {'\"@type\": \"Article\"' in html}")
chip = a.categorias_nomes[0] if a.categorias_nomes else ""
print(f"  chip categoria '{chip}': {f'<span class=\"chip\">{chip}</span>' in html}")
print(f"  tags rodape: {'tags-rodape' in html and (a.tags_nomes[0] in html if a.tags_nomes else True)}")
print(f"  hero com imagem: {'class=\"hero com-imagem\"' in html}")
