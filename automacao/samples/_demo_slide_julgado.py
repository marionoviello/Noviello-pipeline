"""Demo visual: renderiza 3 slides do mesmo julgado em 3 estéticas
diferentes (claro, escuro, foto-fundo) com a barra de julgado + carimbo
ativos. Confirma que a estética nova bate com o card LinkedIn."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import carousel_render  # noqa: E402

# Slides de exemplo — mesmo julgado, ângulos diferentes
SLIDES = [
    {  # slide 1: capa (escuro)
        "titulo": "STJ muda a leitura do justo título",
        "corpo": "Recibo de compra basta para a usucapião ordinária. Decisão recente abre caminho para regularizar imóveis adquiridos sem escritura.",
        "area": "Direito Imobiliário",
        "selo_tribunal": "STJ",
        "processo_id": "REsp 2.215.421/SE",
        "carimbo": "Unanimidade",
    },
    {  # slide 2: tese (claro)
        "titulo": "O justo título não é o documento",
        "corpo": "A tese: justo título é o fundamento do direito, não o papel formal. Recibo simples serve quando demonstra a intenção de transmissão.",
        "area": "Direito Imobiliário",
        "selo_tribunal": "STJ",
        "processo_id": "REsp 2.215.421/SE",
    },
    {  # slide 3: impacto prático (escuro, sem carimbo)
        "titulo": "Quem pode usar essa via",
        "corpo": "Famílias com imóvel comprado no recibo há 10+ anos. Posse mansa e pacífica + boa-fé + recibo = caminho ordinário em vez de extraordinária.",
        "area": "Direito Imobiliário",
        "selo_tribunal": "STJ",
        "processo_id": "REsp 2.215.421/SE",
    },
]

destino = ROOT / "samples" / "demo-slides-julgado"
destino.mkdir(parents=True, exist_ok=True)

layout = {
    1: ("escuro", None),
    2: ("claro", None),
    3: ("escuro", None),
}

print("Renderizando 3 slides com estética nova de julgado...")
jpgs = carousel_render.renderizar(
    SLIDES,
    pasta_destino=destino,
    templates_dir=ROOT / "templates",
    render_script=ROOT.parent / "scripts" / "render-slide.py",
    layout_map=layout,
)
for p in jpgs:
    print(f"  {p.name}  ({p.stat().st_size:,} bytes)")
print("Pronto.")
