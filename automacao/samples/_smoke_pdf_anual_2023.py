"""Smoke real: baixar PDF anual 2023 do STJ via httpx + particionar.

Sem Anthropic. So valida o fluxo:
  1. obter_pdfs_anuais([2023]) -> ref existe
  2. baixar_pdf_anual(ref) -> cache local
  3. particionar_itens(texto_pdf) -> quantos blocos vamos extrair via IA?

Custo: 0 (so HTTP + pypdf).
"""

import time
from pathlib import Path

from src.julgado_radar.feeds_stj import baixar_pdf_anual, obter_pdfs_anuais
from src.julgado_radar.parser import _ler_pdf, particionar_itens


def main() -> int:
    print("== Passo 1: obter_pdfs_anuais([2023]) ==")
    t0 = time.monotonic()
    refs = obter_pdfs_anuais([2023])
    print(f"  {len(refs)} ref(s) em {time.monotonic() - t0:.1f}s")
    if not refs:
        print("  ERRO: 2023 nao disponivel (probe disse que era)")
        return 1
    ref = refs[0]
    print(f"  ref: {ref}")

    print("\n== Passo 2: baixar_pdf_anual ==")
    cache = Path("state/julgado_radar_cache/stj")
    t1 = time.monotonic()
    pdf_path = baixar_pdf_anual(ref, cache)
    dur1 = time.monotonic() - t1
    tamanho = pdf_path.stat().st_size
    print(f"  baixado em {dur1:.1f}s")
    print(f"  arquivo: {pdf_path} ({tamanho:,} bytes)")

    # Roda de novo pra cache hit
    t2 = time.monotonic()
    pdf_path2 = baixar_pdf_anual(ref, cache)
    print(f"  2a execucao (cache hit): {time.monotonic() - t2:.2f}s")

    print("\n== Passo 3: extrair texto via pypdf ==")
    t3 = time.monotonic()
    texto = _ler_pdf(pdf_path)
    print(f"  pypdf: {len(texto):,} chars em {time.monotonic() - t3:.1f}s")

    print("\n== Passo 4: particionar em itens ==")
    blocos = particionar_itens(texto)
    print(f"  {len(blocos)} blocos detectados")
    print("\n  Tamanhos dos primeiros 10 blocos:")
    for i, b in enumerate(blocos[:10]):
        primeira_linha = b.split("\n", 1)[0][:80]
        print(f"    {i+1:2d}. {len(b):>6,} chars | inicio: {primeira_linha!r}")

    print("\n== CRITERIOS ==")
    crit1 = tamanho > 1_000_000  # PDF >1MB
    crit2 = len(texto) > 100_000  # Texto >100KB
    crit3 = len(blocos) >= 30  # Pelo menos 30 itens
    print(f"  PDF >1MB: {'OK' if crit1 else 'FALHOU'} ({tamanho:,})")
    print(f"  Texto >100KB: {'OK' if crit2 else 'FALHOU'} ({len(texto):,})")
    print(f"  >=30 blocos particionados: {'OK' if crit3 else 'FALHOU'} ({len(blocos)})")

    if crit1 and crit2 and crit3:
        print("\n>>> PASSOU — pronto pra rodar com Anthropic")
        print(f"  custo estimado: {len(blocos)} chamadas x ~$0.08 = ~${len(blocos) * 0.08:.2f}")
        return 0
    print("\n>>> FALHOU")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
