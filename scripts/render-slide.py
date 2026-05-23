"""
Render HTML slide → JPG 1080x1350 via Playwright.
Usado pela skill noviello-carrossel-creator para gerar artes a partir de HTML.

Como executar:
    1) Instalar dependencias (1 vez so):
       pip install playwright
       playwright install chromium

    2) Renderizar um slide:
       python render-slide.py <arquivo.html> <saida.jpg>

       Exemplo:
       python render-slide.py "C:\\Users\\mario\\Documents\\Noviello-Produtividade\\templates\\slides-html\\post-4-certidoes.html" "C:\\Users\\mario\\Documents\\Noviello-Produtividade\\templates\\slides-html\\post-4-certidoes.jpg"

Configuracao:
    - Saida: JPEG 1080x1350, qualidade 92
    - Espera fonts carregarem antes de tirar print (1s)
"""

import sys
import asyncio
import os
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERRO: biblioteca playwright nao instalada.")
    print("Rode: pip install playwright && playwright install chromium")
    sys.exit(1)


async def render(html_path: str, output_path: str):
    html_path_abs = Path(html_path).resolve()
    output_path_abs = Path(output_path).resolve()

    if not html_path_abs.exists():
        print(f"ERRO: arquivo HTML nao encontrado: {html_path_abs}")
        sys.exit(1)

    file_url = html_path_abs.as_uri()
    print(f"Carregando: {file_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1080, "height": 1350},
            device_scale_factor=2,
        )
        page = await context.new_page()
        await page.goto(file_url, wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(output_path_abs),
            type="jpeg",
            quality=92,
            full_page=False,
            clip={"x": 0, "y": 0, "width": 1080, "height": 1350},
        )
        await browser.close()

    size_kb = output_path_abs.stat().st_size / 1024
    print(f"OK - JPG gerado: {output_path_abs} ({size_kb:.1f} KB)")


def main():
    if len(sys.argv) != 3:
        print("Uso: python render-slide.py <arquivo.html> <saida.jpg>")
        sys.exit(1)

    html_path = sys.argv[1]
    output_path = sys.argv[2]
    asyncio.run(render(html_path, output_path))


if __name__ == "__main__":
    main()
