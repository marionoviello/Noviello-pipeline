"""#BrandLockProtocol — validador de pre-entrega da identidade visual Noviello.

Versao Python (robusta a Unicode astral — Git Bash grep falha em emojis >FFFF).
Uso: python scripts/brandlock.py <arquivo.html> [<arquivo2.html> ...]
Saida 0 = OK (pode entregar) | 1 = corrigir antes de entregar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allowlist FECHADA de cores (hex normalizado maiusculo, sem #).
PALETA = {
    "68192E", "540D1D", "F1F3F2", "FFFFFF", "FFF", "1A1A1A", "444444", "000000",
}

# Ranges de emoji / simbolos clichê (incl. astrais).
_RE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⚐-⚗⚔⚱\U0001F3DB]"
)
# Glyphs clichê referenciados em CSS content (balanca, espadas, urna, livro, predio).
_RE_GLYPH_CSS = re.compile(
    r'content:\s*["\']\\?(2696|2694|26B1|1F4D6|1F3DB)', re.IGNORECASE
)
# cor real e seguida de nao-alfanumerico; evita falso-positivo de ancora href="#efe..."
_RE_HEX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z])|#[0-9a-fA-F]{3}(?![0-9a-zA-Z])")
_RE_FONT = re.compile(
    r"font-family:[^;}]*\b(inter|roboto|arial|helvetica)\b", re.IGNORECASE
)


def validar(arq: Path) -> list[str]:
    txt = arq.read_text(encoding="utf-8", errors="replace")
    erros: list[str] = []

    # (a) cores fora da paleta
    off = sorted({h[1:].upper() for h in _RE_HEX.findall(txt)} - PALETA)
    if off:
        erros.append("cores fora da paleta: " + ", ".join("#" + h for h in off))

    # (b) emoji / icone clichê direto no texto
    emojis = sorted(set(_RE_EMOJI.findall(txt)))
    if emojis:
        nomes = ", ".join(f"U+{ord(e):04X}" for e in emojis)
        erros.append(f"emoji/icone proibido: {nomes}")

    # (c) glyph clichê em CSS content
    glyphs = sorted(set(m.upper() for m in _RE_GLYPH_CSS.findall(txt)))
    if glyphs:
        erros.append("glyph cliche em CSS content: " + ", ".join("\\" + g for g in glyphs))

    # (d) fontes nao autorizadas
    fontes = sorted(set(f.lower() for f in _RE_FONT.findall(txt)))
    if fontes:
        erros.append("fonte fora da marca: " + ", ".join(fontes))

    return erros


def main(argv: list[str]) -> int:
    if not argv:
        print("uso: python scripts/brandlock.py <arquivo.html> [...]")
        return 2
    geral_ok = True
    for a in argv:
        arq = Path(a)
        erros = validar(arq)
        if erros:
            geral_ok = False
            print(f"X {arq.name}")
            for e in erros:
                print(f"    - {e}")
        else:
            print(f"OK {arq.name}  #BrandLockProtocol")
    if not geral_ok:
        print("-> Corrigir antes de entregar.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
