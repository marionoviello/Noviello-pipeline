"""Smoke real: descobre informativos do portal STJ via Playwright.

Roda contra https://processo.stj.jus.br/jurisprudencia/externo/informativo/
e enumera todos os informativos do(s) ano(s) pedidos. Sem Anthropic ainda
(so abre Chromium, faz o select, le os combos).

Uso:
    .venv\\Scripts\\python.exe -m samples._smoke_stj_descobrir

Esperado:
    Total descobertos para 2024: ~38
    (com lista das 5 mais recentes)
"""

import time

from src.julgado_radar.feeds_stj import descobrir_informativos


def main() -> int:
    print("Abrindo Chromium e consultando portal STJ...")
    t0 = time.monotonic()

    refs = descobrir_informativos([2024])

    dur = time.monotonic() - t0
    print(f"\nDuracao: {dur:.1f}s")
    print(f"Total descobertos para 2024: {len(refs)}")
    print()

    if not refs:
        print("ERRO: nenhuma referencia descoberta.")
        print("  - Portal STJ pode ter mudado layout")
        print("  - Verifique o select_id em feeds_stj.py")
        return 1

    print("5 mais recentes:")
    for r in refs[:5]:
        print(f"  - inf-{r.numero:04d} (ano {r.ano}, select_id={r.select_id})")
        print(f"      titulo: {r.titulo[:70]}")

    print()
    print("Criterio de aceitacao: >=30 informativos descobertos.")
    if len(refs) >= 30:
        print(f"  >>> PASSOU ({len(refs)} >= 30)")
        return 0
    else:
        print(f"  >>> FALHOU ({len(refs)} < 30)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
