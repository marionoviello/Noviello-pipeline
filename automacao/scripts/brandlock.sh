#!/usr/bin/env bash
# #BrandLockProtocol — validador de pre-entrega da identidade visual Noviello.
# Uso: bash scripts/brandlock.sh <arquivo.html>
# Saida 0 = OK (pode entregar) | 1 = corrigir antes de entregar.
# Allowlist FECHADA de cores + proibicao de emoji/icone clichê + fontes da marca.

ARQ="${1:?passe o caminho do .html}"
FAIL=0

# (a) Cores fora da paleta — qualquer hex nao-tabelado falha
OFF=$(grep -oiE '#[0-9a-f]{3,8}' "$ARQ" | tr 'a-f' 'A-F' | sort -u \
  | grep -vE '^#(68192E|540D1D|F1F3F2|FFFFFF|FFF|1A1A1A|444444|000000)$')
[ -n "$OFF" ] && { echo "X Cores fora da paleta:"; echo "$OFF"; FAIL=1; }

# (b) Emoji ou icone juridico clichê (balanca, espadas, urna, livro, predio classico)
ICN=$(grep -nP '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2690}-\x{2697}\x{2694}\x{26B1}\x{1F3DB}]' "$ARQ")
[ -n "$ICN" ] && { echo "X Emoji/icone proibido:"; echo "$ICN"; FAIL=1; }

# (c) Glyph de balanca via CSS content (ex.: content:"\2696")
grep -niE 'content:\s*"\\?(2696|2694|26b1)' "$ARQ" && { echo "X Glyph cliche em CSS content"; FAIL=1; }

# (d) Fontes nao autorizadas
grep -niE 'font-family:[^;}]*(inter|roboto|arial|helvetica|system-ui[^,]*$)' "$ARQ" \
  && { echo "X Fonte fora da marca (use Cinzel/Poppins/Cormorant)"; FAIL=1; }

[ "$FAIL" -eq 0 ] && echo "OK #BrandLockProtocol" || { echo "-> Corrigir antes de entregar."; exit 1; }
