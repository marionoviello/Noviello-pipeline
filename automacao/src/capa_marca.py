"""Gerador de capa da marca (featured image) para artigos do blog.

Capa 1200x630 no DNA Noviello, conforme #BrandLockProtocol:
- fundo gradiente claret -> chocolate cosmos
- chip de area, regua anti-flash, titulo Cinzel (fonte dinamica por tamanho),
  subtitulo opcional Cormorant italico
- logo branco no rodape (embutido em base64, auto-contido)
- SOMENTE cores da allowlist; sem dourado, creme, emoji ou icone clichê

Uso:
    from src.capa_marca import gerar_html_capa
    html = gerar_html_capa(area="Direito Imobiliario", titulo="...", subtitulo="...")
    # renderizar via Playwright: page.set_content(html); locator('.capa').screenshot(...)
"""

from __future__ import annotations

import base64
import html as _html
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _logo_base64() -> str:
    """Logo branco em data URI (auto-contido). Procura nos caminhos conhecidos."""
    candidatos = [
        Path("templates/logo-noviello-branco.png"),
        Path("automacao/templates/logo-noviello-branco.png"),
    ]
    for c in candidatos:
        if c.exists():
            b = c.read_bytes()
            return "data:image/png;base64," + base64.b64encode(b).decode("ascii")
    return ""


def _font_size_titulo(titulo: str) -> int:
    """Tamanho de fonte do titulo conforme comprimento (pra caber na capa)."""
    n = len(titulo or "")
    if n <= 32:
        return 64
    if n <= 48:
        return 54
    if n <= 68:
        return 44
    if n <= 90:
        return 37
    return 31


def gerar_html_capa(area: str, titulo: str, subtitulo: str = "") -> str:
    """Monta o HTML completo da capa (1200x630). Renderizar o seletor `.capa`."""
    logo = _logo_base64()
    fs = _font_size_titulo(titulo)
    area_disp = _html.escape((area or "Noviello Advocacia").upper())
    titulo_disp = _html.escape(titulo or "")
    sub_html = (
        f'<div class="sub">{_html.escape(subtitulo)}</div>' if subtitulo else ""
    )
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700;800&family=Cormorant+Garamond:ital,wght@1,400;1,500;1,600&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{--claret:#68192E;--cosmos:#540D1D;--anti-flash:#F1F3F2;--white:#FFFFFF}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{width:1200px;height:630px;font-family:'Poppins',sans-serif;color:var(--anti-flash);overflow:hidden}}
  .capa{{width:1200px;height:630px;position:relative;display:flex;flex-direction:column;
    padding:54px 64px 0;background:linear-gradient(180deg,var(--claret) 0%,var(--cosmos) 100%)}}
  .topo{{display:flex;justify-content:space-between;align-items:center;margin-bottom:34px}}
  .chip{{font-size:15px;font-weight:600;letter-spacing:4px;text-transform:uppercase;
    color:var(--anti-flash);padding:9px 20px;border:1.5px solid var(--anti-flash);border-radius:2px}}
  .selo{{display:flex;align-items:center;gap:12px;font-family:'Cinzel',serif;font-weight:700;color:var(--white);font-size:18px;letter-spacing:3px}}
  .selo .mark{{width:12px;height:12px;background:var(--anti-flash);transform:rotate(45deg)}}
  .miolo{{flex:1;display:flex;flex-direction:column;justify-content:center}}
  .rule{{width:34px;height:2px;background:var(--anti-flash);margin-bottom:22px}}
  .titulo{{font-family:'Cinzel',serif;font-weight:600;font-size:{fs}px;line-height:1.12;
    color:var(--anti-flash);text-transform:uppercase;letter-spacing:0.5px;max-width:1010px}}
  .sub{{font-family:'Cormorant Garamond',serif;font-style:italic;font-weight:500;font-size:28px;
    line-height:1.3;color:var(--anti-flash);padding-left:22px;border-left:3px solid var(--anti-flash);
    max-width:900px;margin-top:24px}}
  .rodape{{margin:0 -64px;padding:22px 64px;background:var(--cosmos);border-top:2px solid var(--anti-flash);
    display:flex;justify-content:space-between;align-items:center}}
  .rodape .logo{{width:330px;height:88px;display:block;filter:drop-shadow(0 2px 5px rgba(0,0,0,0.4))}}
  .rodape .sub-marca{{font-family:'Poppins',sans-serif;font-size:14px;letter-spacing:3px;color:var(--anti-flash);
    text-transform:uppercase;text-align:right;line-height:1.5}}
  .rodape .sub-marca .l2{{font-size:12px;letter-spacing:1px;font-weight:300}}
</style></head><body>
<div class="capa">
  <div class="topo">
    <div class="chip">{area_disp}</div>
    <div class="selo"><div class="mark"></div>NOVIELLO</div>
  </div>
  <div class="miolo">
    <div class="rule"></div>
    <div class="titulo">{titulo_disp}</div>
    {sub_html}
  </div>
  <div class="rodape">
    <img class="logo" src="{logo}" alt="Noviello Advocacia">
    <div class="sub-marca">Advocacia<div class="l2">Imobiliário e Sucessório</div></div>
  </div>
</div></body></html>"""
