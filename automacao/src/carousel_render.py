"""Renderiza os slides do carrossel em JPG.

Preenche templates/slide-carrossel.html com a copy de cada slide e chama
scripts/render-slide.py (Playwright) para gerar os JPG 1080x1350.
"""

from __future__ import annotations

import base64
import html as _html
import subprocess
import sys
from pathlib import Path

SLIDE_TEMPLATE = "slide-carrossel.html"
LOGO = "logo-noviello.png"


class RenderError(Exception):
    pass


def _logo_data_uri(templates_dir: Path) -> str:
    """Logo da marca como data URI base64 (embutido no HTML do slide)."""
    caminho = Path(templates_dir) / LOGO
    if not caminho.exists():
        return ""
    dados = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{dados}"


def _bg_style(imagem: Path | None) -> str:
    """Estilo CSS inline para background-image (file:// absoluto). Vazio se sem imagem."""
    if not imagem:
        return ""
    # Path.as_uri() gera file:///C:/... — Playwright consome OK.
    return f"background-image: url('{Path(imagem).resolve().as_uri()}');"


def _preencher(
    template: str,
    slide: dict,
    numero: int,
    total: int,
    *,
    tema: str | None = None,
    imagem_bg: Path | None = None,
) -> str:
    """Preenche o template para um slide.

    - tema: 'claro' | 'escuro' | 'foto-fullbleed' | 'foto-fundo'. Se None,
      alternancia automatica: impar=claro, par=escuro (compatibilidade).
    - imagem_bg: caminho da imagem para os temas 'foto-*'. Ignorado nos outros.
    """
    corpo = _html.escape(slide.get("corpo", "")).replace("\n", "<br>")
    titulo = _html.escape(slide.get("titulo", ""))
    if tema is None:
        tema = "claro" if numero % 2 == 1 else "escuro"
    bg_style = _bg_style(imagem_bg) if tema.startswith("foto-") else ""
    return (
        template.replace("{numero}", str(numero))
        .replace("{total}", str(total))
        .replace("{titulo}", titulo)
        .replace("{corpo}", corpo)
        .replace("{tema}", tema)
        .replace("{bg_style}", bg_style)
    )


# Tipo do mapa de layout: slide_numero (1-indexado) -> (tema, caminho_imagem_opcional)
LayoutSlide = tuple[str, "Path | None"]
LayoutMap = dict[int, LayoutSlide]


def renderizar(
    slides: list[dict],
    pasta_destino: Path,
    templates_dir: Path,
    render_script: Path,
    *,
    layout_map: LayoutMap | None = None,
) -> list[Path]:
    """Gera um JPG por slide em pasta_destino. Devolve a lista de caminhos dos JPG.

    `layout_map` opcional: dict {numero_slide: (tema, imagem_path)}. Slides nao
    presentes no map caem na alternancia padrao (claro/escuro).
    """
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    template = (Path(templates_dir) / SLIDE_TEMPLATE).read_text(encoding="utf-8")
    # o logo e igual em todos os slides — injeta uma vez
    template = template.replace("{logo}", _logo_data_uri(templates_dir))

    jpgs: list[Path] = []
    total = len(slides)
    for i, slide in enumerate(slides, start=1):
        layout = (layout_map or {}).get(i)
        tema, imagem = layout if layout else (None, None)
        html = _preencher(template, slide, i, total, tema=tema, imagem_bg=imagem)
        html_path = pasta_destino / f"slide{i:02d}.html"
        jpg_path = pasta_destino / f"slide{i:02d}.jpg"
        html_path.write_text(html, encoding="utf-8")

        resultado = subprocess.run(
            [sys.executable, str(render_script), str(html_path), str(jpg_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if resultado.returncode != 0 or not jpg_path.exists():
            raise RenderError(
                f"falha ao renderizar slide {i}: {resultado.stderr or resultado.stdout}"
            )
        jpgs.append(jpg_path)

    return jpgs
