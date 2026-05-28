"""Smoke real com Anthropic: extrai 30 blocos do PDF anual 2023.

Pega o cache do PDF 2023 (ja baixado pelo smoke anterior), particiona,
filtra blocos com >500 chars (descarta header institucional), pega os
primeiros 30, manda 1 a 1 pro Anthropic e mostra:
- quantos foram classificados em cada area
- custo total real
- exemplos de julgados das areas-alvo

Custo esperado: ~$2-3 (30 chamadas x ~$0.08).
"""

import time
from collections import Counter
from pathlib import Path

from src.config import load_config
from src.julgado_radar.config import AREAS_ALVO
from src.julgado_radar.parser import _ler_pdf, extrair_item_via_ia, particionar_itens


LIMITE = 30
TAMANHO_MIN = 500  # filtra header institucional (330 chars)


def main() -> int:
    cfg = load_config()

    if not cfg.anthropic_pronto():
        print("ERRO: Anthropic key nao configurada. Conferir .env.")
        return 1

    from src.anthropic_client import AnthropicClient
    cli = AnthropicClient(cfg.anthropic, cfg.templates_dir)

    print(f"== Lendo PDF do cache ==")
    pdf_path = cfg.state_dir / "julgado_radar_cache" / "stj" / "informativo_anual_2023.pdf"
    if not pdf_path.exists():
        print(f"ERRO: PDF nao existe em {pdf_path}")
        print("  Rode samples._smoke_pdf_anual_2023 primeiro pra baixar.")
        return 1

    texto = _ler_pdf(pdf_path)
    print(f"  texto: {len(texto):,} chars")

    blocos = particionar_itens(texto)
    blocos_filtrados = [b for b in blocos if len(b) >= TAMANHO_MIN]
    blocos_smoke = blocos_filtrados[:LIMITE]
    print(f"  blocos totais: {len(blocos)}")
    print(f"  apos filtro >={TAMANHO_MIN} chars: {len(blocos_filtrados)}")
    print(f"  selecionados pra smoke: {len(blocos_smoke)}")

    print(f"\n== Extraindo via Anthropic ({LIMITE} chamadas) ==")
    t0 = time.monotonic()
    resultados: list[dict] = []
    erros = 0

    for i, bloco in enumerate(blocos_smoke, 1):
        try:
            item = extrair_item_via_ia(bloco, cli)
            resultados.append(item)
            area = item.get("area", "?")
            proc = item.get("processo_id", "?")[:30]
            print(f"  {i:2d}/{LIMITE}  area={area:<14s} proc={proc}")
        except Exception as exc:
            erros += 1
            print(f"  {i:2d}/{LIMITE}  ERRO: {str(exc)[:60]}")

    dur = time.monotonic() - t0
    print(f"\n== Resultados ({dur:.1f}s) ==")

    # Cobertura por area
    areas = Counter(r.get("area", "?") for r in resultados)
    print("Distribuicao por area:")
    for area, n in areas.most_common():
        marca = ">>> " if area in AREAS_ALVO else "    "
        print(f"  {marca}{area:<14s}: {n}")

    aceitos = [r for r in resultados if r.get("area") in AREAS_ALVO
               and r.get("processo_id") and r.get("tese")]
    print(f"\nJulgados nas areas-alvo (urbanistico/imobiliario/sucessorio): {len(aceitos)}")

    if aceitos:
        print("\n3 exemplos:")
        for r in aceitos[:3]:
            print(f"  area={r['area']}")
            print(f"  processo: {r.get('processo_id', '')[:60]}")
            print(f"  tese: {r.get('tese', '')[:200]}")
            print()

    print(f"Erros: {erros}/{LIMITE}")
    print(f"Tempo medio: {dur/LIMITE:.1f}s/bloco")
    print()
    print("Para custo real, conferir https://console.anthropic.com/usage")
    print(f"Estimativa: ~${LIMITE * 0.08:.2f} (~$0.08 por chamada Opus 4.7)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
