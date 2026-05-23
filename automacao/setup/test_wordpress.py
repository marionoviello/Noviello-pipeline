"""Teste seguro do caminho de escrita do WordPress.

Cria um post RASCUNHO real no noviello.adv.br: faz upload de uma imagem na
biblioteca de midia e cria o post com status=draft. O rascunho NAO fica publico.
Valida upload_media + create_post sem publicar nada.

Rodar (a partir de automacao/):
    .venv\\Scripts\\python.exe setup\\test_wordpress.py
"""

from __future__ import annotations

import base64
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402
from src.wp_client import WordPressClient  # noqa: E402

# JPEG 1x1 valido
_JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEA"
    "AAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AvwAH/9k="
)


def main() -> int:
    cfg = load_config()
    if not cfg.wordpress_pronto():
        print("ERRO: credenciais WordPress ausentes no .env.")
        return 1

    site = "noviello"
    cliente = WordPressClient(
        cfg.wordpress["user"],
        {
            "noviello": cfg.wordpress.get("app_password_noviello", ""),
            "imobiliario": cfg.wordpress.get("app_password_imobiliario", ""),
        },
    )

    print(f"[1/2] Upload de imagem de teste na midia do {site}.adv.br...")
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(_JPEG_1X1)
        tmp_path = tmp.name
    midia = cliente.upload_media(tmp_path, site)
    Path(tmp_path).unlink(missing_ok=True)
    print(f"  OK - media id {midia['id']}")
    print(f"       source_url: {midia['source_url']}")

    print(f"[2/2] Criando post RASCUNHO (status=draft)...")
    post = cliente.create_post(
        site,
        titulo="[TESTE AUTOMACAO] Validacao do pipeline - pode apagar",
        slug="teste-automacao-pipeline-apagar",
        conteudo_html="<p>Post de teste gerado pelo pipeline de automacao. "
        "E um rascunho, nao esta publico. Pode apagar.</p>",
        status="draft",
        featured_media=midia["id"],
        meta_description="Post de teste - apagar.",
    )
    print(f"  OK - post id {post['id']} (status: rascunho)")
    print(f"       link (so visivel logado): {post['link']}")
    print()
    print("=" * 60)
    print("  SUCESSO. O caminho de escrita do WordPress funciona.")
    print("=" * 60)
    print()
    print("Para limpar: entre no wp-admin do noviello.adv.br,")
    print("  - Posts -> apague o rascunho '[TESTE AUTOMACAO]...'")
    print("  - Midia -> apague a imagem de teste (1x1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
