"""Probe v2 TJ-SP — disseca o formulario de consulta cjsg.

Descobre: action/method do form, nome do campo de busca livre, todos os
campos (name=value), e se ha captcha REAL (elemento) ou so string em JS.
"""

import re

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
URL = "https://esaj.tjsp.jus.br/cjsg/consultaCompleta.do"


def main() -> int:
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as c:
        r = c.get(URL)
        html = r.text
    print(f"GET {URL} -> {r.status_code}, {len(html):,} bytes\n")

    # ---- forms: action + method ----
    print("=== FORMS (action / method / id) ===")
    for m in re.finditer(r'<form\b([^>]*)>', html, re.IGNORECASE):
        attrs = m.group(1)
        action = (re.search(r'action=["\']([^"\']*)["\']', attrs) or [None, "?"])[1]
        method = (re.search(r'method=["\']([^"\']*)["\']', attrs) or [None, "?"])[1]
        fid = (re.search(r'id=["\']([^"\']*)["\']', attrs) or [None, "?"])[1]
        print(f"  form id={fid!r} method={method!r} action={action!r}")

    # ---- campo de busca livre (textarea ou input com 'livre'/'pesquisa') ----
    print("\n=== CAMPOS com 'livre'/'pesquisa'/'buscaLivre' no name ===")
    campos = re.findall(r'<(?:input|textarea)[^>]*name=["\']([^"\']+)["\']', html, re.IGNORECASE)
    for nome in campos:
        if any(t in nome.lower() for t in ("livre", "pesquisa", "busca")):
            print(f"  {nome}")

    # ---- TODOS os names (pra montar o payload certo) ----
    print(f"\n=== TODOS os campos name (total {len(campos)}) ===")
    vistos = []
    for nome in campos:
        if nome not in vistos:
            vistos.append(nome)
    for nome in vistos[:40]:
        print(f"  {nome}")

    # ---- captcha real? ----
    print("\n=== CAPTCHA ===")
    tem_recaptcha = "g-recaptcha" in html or "recaptcha/api" in html
    tem_captcha_img = bool(re.search(r'<img[^>]*captcha', html, re.IGNORECASE))
    tem_captcha_div = bool(re.search(r'<div[^>]*captcha', html, re.IGNORECASE))
    print(f"  g-recaptcha/recaptcha api: {tem_recaptcha}")
    print(f"  <img captcha>: {tem_captcha_img}")
    print(f"  <div captcha>: {tem_captcha_div}")
    # contexto das ocorrencias de 'captcha'
    for m in list(re.finditer(r'.{40}captcha.{40}', html, re.IGNORECASE))[:3]:
        print(f"    ...{m.group(0).strip()}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
