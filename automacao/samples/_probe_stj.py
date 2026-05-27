"""Probe rapido: descobre como o portal STJ Informativos passa numero
do informativo e como pegar histórico."""

from __future__ import annotations

import re
import httpx

BASE = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"

r = httpx.get(BASE, headers={"User-Agent": "Mozilla/5.0"}, timeout=20, follow_redirects=True)
html = r.text
print(f"HTTP {r.status_code}, {len(html):,} bytes")

# Inputs hidden (provavel: numero do informativo atual)
inputs = re.findall(r'<input[^>]*name="(\w+)"[^>]*value="([^"]*)"', html)
print("\nInputs:")
for n, v in inputs:
    if v and len(v) < 80:
        print(f"  {n} = {v}")

# Procura referencias a numero alto (informativo atual)
nums = re.findall(r"\b(\d{3,4})\b", html)
from collections import Counter
mais_freq = Counter(nums).most_common(20)
print("\nNumeros mais frequentes (top 20):")
for n, c in mais_freq:
    if int(n) > 500 and int(n) < 2000:
        print(f"  {n}: {c}x")

# Procura form action
forms = re.findall(r'<form[^>]*action="([^"]*)"', html)
print("\nForms action:")
for f in set(forms):
    print(f"  {f}")

# Procura links com query string
qs_links = re.findall(r'href="([^"]*\?[^"]+)"', html)
print(f"\nLinks com query string: {len(qs_links)}")
for l in qs_links[:8]:
    print(f"  {l[:130]}")

# Tenta passar parametro `aplicacao=informativo.ea&publicacao=`
print("\nProbe com publicacao=info-1186:")
for cand in ["info1186", "1186", "info-1186-2026", "1180"]:
    url = f"{BASE}?aplicacao=informativo.ea&publicacao={cand}"
    rr = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, follow_redirects=True)
    print(f"  ?publicacao={cand}: HTTP {rr.status_code}, {len(rr.text):,} bytes")

# Tenta endpoint conhecido jsp toc
print("\nProbe scon.stj.jus.br/SCON/InformativoJUR/toc.jsp:")
for url in [
    "https://scon.stj.jus.br/SCON/InformativoJUR/toc.jsp",
    "https://scon.stj.jus.br/SCON/SearchBRS?b=INFJ",
    "https://www.stj.jus.br/publicacaoinstitucional/index.php/informjuris/issue/archive",
]:
    try:
        rr = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, follow_redirects=True)
        print(f"  {url[:70]}: HTTP {rr.status_code}, {len(rr.text):,} bytes")
    except Exception as e:
        print(f"  {url[:70]}: ERR {e}")
