"""Renderiza o card LinkedIn/IG do Julgado da Semana em JPG 1080x1350.

Preenche templates/julgado-card.html com dados estruturados (saida do
julgado_parser) e chama scripts/render-slide.py (Playwright) para gerar
o JPG. Subtitulo da marca varia por canal:
  - 'li' (LinkedIn B2B): "Advocacia · Imobiliario e Sucessorio"
  - 'ig' (Instagram B2C): "Advocacia · Direito Senior"

A nomenclatura dos campos do dict de entrada segue o parser:
  processo_id, orgao, orgao_completo, relator, relator_curto, tese,
  citacao_principal, carimbo, fundamentos, area, data_julgamento, turma.

O template julgado-card.html usa placeholders {processo} e {orgao} — o
preencher faz o mapeamento.
"""

from __future__ import annotations

import html as _html
import shutil
import subprocess
import sys
from pathlib import Path

CARD_TEMPLATE = "julgado-card.html"
LOGO = "logo-noviello-branco.png"

SUBTITULOS_PADRAO = {
    "li": "Advocacia · Imobiliario e Sucessorio",
    "ig": "Advocacia · Direito Sênior",
}


class CardRenderError(Exception):
    pass


def _fundamentos_html(fundamentos: list[dict]) -> str:
    return "\n".join(
        f'<div class="fund-item">'
        f'<div class="fonte">{_html.escape(f.get("fonte", ""))}</div>'
        f'<div class="texto">{_html.escape(f.get("texto", ""))}</div>'
        f'</div>'
        for f in fundamentos
    )


# Mapeamento dos campos do dict (chave esquerda) para placeholders do template
# (chave direita). Onde mesma chave, omitir (loop simples a seguir cuida).
_DIRECT_FIELDS = (
    "area", "orgao", "orgao_completo", "turma",
    "data_julgamento", "relator", "relator_curto",
    "tese", "citacao_principal",
    "label_doc", "legenda_doc",
    "tema_rodape", "tema_rodape_sub", "assinatura",
)


def _preencher_card(template: str, dados: dict, *, canal: str = "li") -> str:
    """Devolve HTML do card preenchido (sem disco).

    `canal` ('li'|'ig') controla o subtitulo da marca.
    """
    out = template

    # Carimbo dinamico — default Unanimidade quando vazio/None
    carimbo = dados.get("carimbo")
    carimbo_label = (carimbo or "Unanimidade").strip() or "Unanimidade"
    out = out.replace("{carimbo_label}", _html.escape(carimbo_label))

    # Campos diretos (escape sempre)
    for chave in _DIRECT_FIELDS:
        valor = str(dados.get(chave, ""))
        out = out.replace("{" + chave + "}", _html.escape(valor))

    # processo_id (chave canonica do parser) -> placeholder {processo} no template
    out = out.replace("{processo}", _html.escape(str(dados.get("processo_id", ""))))

    # Default labels do recibo se nao vierem (smoke-friendly)
    if "{label_doc}" in out:
        out = out.replace("{label_doc}", "Documento Analisado")
    if "{legenda_doc}" in out:
        out = out.replace("{legenda_doc}", "")
    if "{assinatura}" in out:
        out = out.replace("{assinatura}", "")
    if "{tema_rodape}" in out:
        out = out.replace("{tema_rodape}", _html.escape(dados.get("tese", "")[:60]))
    if "{tema_rodape_sub}" in out:
        out = out.replace("{tema_rodape_sub}", "")

    # Fundamentos (lista)
    fundamentos = dados.get("fundamentos") or []
    out = out.replace("{fundamentos_html}", _fundamentos_html(fundamentos))

    # Subtitulo da marca por canal (override via dados['subtitulo_marca_li'|'_ig'])
    chave_sub = f"subtitulo_marca_{canal}"
    subtitulo = dados.get(chave_sub) or SUBTITULOS_PADRAO.get(canal, "Advocacia")
    out = out.replace("{subtitulo_marca}", _html.escape(subtitulo))

    return out


def renderizar_card(
    dados: dict,
    pasta_destino: Path,
    templates_dir: Path,
    render_script: Path,
    *,
    canal: str = "li",
    nome_base: str = "card",
) -> Path:
    """Renderiza o card como JPG 1080x1350. Devolve o caminho do JPG.

    Levanta CardRenderError em falha do Playwright/subprocess.
    """
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    templates_dir = Path(templates_dir)

    template_text = (templates_dir / CARD_TEMPLATE).read_text(encoding="utf-8")
    html = _preencher_card(template_text, dados, canal=canal)

    # Copia logo para a pasta de destino (o template referencia logo via src relativo)
    logo_src = templates_dir / LOGO
    if logo_src.exists():
        shutil.copy(logo_src, pasta_destino / LOGO)

    arq_html = pasta_destino / f"{nome_base}-{canal}.html"
    arq_jpg = pasta_destino / f"{nome_base}-{canal}.jpg"
    arq_html.write_text(html, encoding="utf-8")

    resultado = subprocess.run(
        [sys.executable, str(render_script), str(arq_html), str(arq_jpg)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if resultado.returncode != 0 or not arq_jpg.exists():
        raise CardRenderError(
            f"falha ao renderizar card {canal}: "
            f"{resultado.stderr or resultado.stdout}"
        )
    return arq_jpg
