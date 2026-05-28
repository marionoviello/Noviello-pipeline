"""Smoke real: baixa 1 informativo do STJ via Playwright.

Valida o ciclo completo: select_option + wait_for_timeout + eval_on_selector
contra o portal real. Sem Anthropic ainda.

Uso:
    .venv\\Scripts\\python.exe -m samples._smoke_stj_baixar

Esperado:
    HTML salvo em state/julgado_radar_cache/stj/inf-NNNN.html (>1KB)
    contendo referencias a "PROCESSO", "REsp", "AgInt" ou similares.
    Segunda execucao: usa cache em <1s sem abrir Chromium.
"""

import time
from pathlib import Path

from src.julgado_radar.feeds_stj import baixar_informativo, descobrir_informativos


def main() -> int:
    print("Passo 1: descobrir refs de 2024...")
    t0 = time.monotonic()
    refs = descobrir_informativos([2024])
    print(f"  {len(refs)} refs em {time.monotonic() - t0:.1f}s")

    if not refs:
        print("ERRO: nenhuma ref descoberta. Roda _smoke_stj_descobrir primeiro.")
        return 1

    ref = refs[0]  # mais recente
    print(f"\nPasso 2: baixar inf-{ref.numero:04d}")
    print(f"  titulo: {ref.titulo[:70]}")
    print(f"  select_id: {ref.select_id}, option_value: {ref.option_value}")

    cache = Path("state/julgado_radar_cache/stj")
    cache.mkdir(parents=True, exist_ok=True)

    # 1a execucao: abre Chromium
    t1 = time.monotonic()
    arq = baixar_informativo(ref, cache)
    dur1 = time.monotonic() - t1
    html = arq.read_text(encoding="utf-8")

    print(f"\n  1a execucao: {dur1:.1f}s")
    print(f"  arquivo: {arq}")
    print(f"  tamanho: {len(html)} chars")

    # 2a execucao: cache hit (deve ser instantanea)
    t2 = time.monotonic()
    arq2 = baixar_informativo(ref, cache)
    dur2 = time.monotonic() - t2
    print(f"  2a execucao (cache hit): {dur2:.2f}s")

    print("\nPrimeiras 500 chars do HTML:")
    print("-" * 60)
    print(html[:500])
    print("-" * 60)

    # Validacao de conteudo
    marcadores = ("PROCESSO", "REsp", "AgInt", "HC", "AREsp", "EREsp", "ementa")
    achados = [m for m in marcadores if m.lower() in html.lower()]
    print(f"\nMarcadores juridicos encontrados: {achados}")

    print("\nCriterios:")
    print(f"  - HTML >1KB: {'OK' if len(html) > 1024 else 'FALHOU'} ({len(html)} chars)")
    print(f"  - tem marcador juridico: {'OK' if achados else 'FALHOU'}")
    print(f"  - cache hit rapido (<1s): {'OK' if dur2 < 1.0 else 'FALHOU'} ({dur2:.2f}s)")

    if len(html) > 1024 and achados and dur2 < 1.0:
        print("\n>>> PASSOU")
        return 0
    print("\n>>> FALHOU")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
