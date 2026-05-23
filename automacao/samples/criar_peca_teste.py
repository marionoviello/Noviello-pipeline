"""Cria uma peca de teste em producao/ para validar o pipeline em DRY_RUN.

Gera uma pasta com MANIFEST.json + 2 JPEGs validos (1x1) + legenda.txt.
Para um teste real de Instagram, use uma peca produzida pelo render-slide.py
(os JPEGs aqui sao minimos, servem so para o fluxo em modo simulado).

Rodar (a partir de automacao/):
    .venv\\Scripts\\python.exe samples\\criar_peca_teste.py
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402

# JPEG 1x1 valido (vermelho)
_JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEA"
    "AAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AvwAH/9k="
)

def main() -> int:
    cfg = load_config()
    # peca_id com timestamp: nunca colide com state antigo
    peca_id = "vivo-" + datetime.now().strftime("%Y%m%dT%H%M%S")
    pasta = cfg.producao_dir / peca_id / "pauta-teste"
    pasta.mkdir(parents=True, exist_ok=True)

    slide1 = pasta / "slide1.jpg"
    slide2 = pasta / "slide2.jpg"
    slide1.write_bytes(_JPEG_1X1)
    slide2.write_bytes(_JPEG_1X1)

    legenda = pasta / "legenda.txt"
    legenda.write_text(
        "PECA DE TESTE — pipeline de aprovacao Noviello.\n\n"
        "Se voce esta vendo este email, o watcher funcionou. "
        "Mova para _APROVADO para testar a publicacao em DRY_RUN.",
        encoding="utf-8",
    )

    manifest = {
        "peca_id": peca_id,
        "tipo": "carrossel",
        "pilar": "TESTE",
        "titulo_curto": "Peca de teste do pipeline",
        "data_publicacao_alvo": "2026-05-25T10:00:00-03:00",
        "status": "pronta_para_aprovacao",
        "validacoes": {"oab_205": "aprovado", "marca": "v2-conforme", "ortografia": "ok"},
        "ativos": {
            "instagram": {
                "imagens": [str(slide1), str(slide2)],
                "legenda": str(legenda),
                "hashtags": ["#teste"],
                "tipo_post": "carrossel",
            }
        },
        "cross_link": {"ig_para_wp": False, "li_para_wp": False, "linktree_topo": False},
    }
    mpath = pasta / "MANIFEST.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Peca de teste criada: {mpath}")
    print(f"peca_id: {peca_id}")
    print("Rode o watcher para enviar o email de aprovacao:")
    print("  .venv\\Scripts\\python.exe -m src.watcher")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
