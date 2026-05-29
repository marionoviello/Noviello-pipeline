"""Probe v3 TJ-SP — POST com os campos CORRETOS (dados.buscaEmenta etc).

Decide se o reCAPTCHA v3 bloqueia o POST ou se era so campo errado.
"""

import re
from datetime import date

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
GET_URL = "https://esaj.tjsp.jus.br/cjsg/consultaCompleta.do"
POST_URL = "https://esaj.tjsp.jus.br/cjsg/resultadoCompleta.do"


def main() -> int:
    with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"},
                      timeout=60, follow_redirects=True) as c:
        g = c.get(GET_URL)
        html = g.text
        # pega conversationId default (se houver)
        conv = (re.search(r'name=["\']conversationId["\'][^>]*value=["\']([^"\']*)["\']', html)
                or [None, ""])[1]
        # action real do form de pesquisa
        actions = re.findall(r'<form[^>]*action=["\']([^"\']*)["\']', html)
        print("actions no form:", actions[:5])
        print("conversationId default:", repr(conv))

        payload = {
            "conversationId": conv,
            "dados.buscaInteiroTeor": "",
            "dados.pesquisarComSinonimos": "S",
            "dados.buscaEmenta": "usucapiao",
            "dados.nuProcOrigem": "",
            "dados.nuRegistro": "",
            "agenteSelectedEntitiesList": "",
            "contadoragente": "0",
            "contadorMaioragente": "0",
            "classesTreeSelection.values": "",
            "classesTreeSelection.text": "",
            "assuntosTreeSelection.values": "",
            "assuntosTreeSelection.text": "",
            "comarcaSelectedEntitiesList": "",
            "secoesTreeSelection.values": "",
            "secoesTreeSelection.text": "",
            "dados.dtJulgamentoInicio": "01/01/2024",
            "dados.dtJulgamentoFim": "31/12/2024",
            "dados.dtPublicacaoInicio": "",
            "dados.dtPublicacaoFim": "",
            "dados.origensSelecionadas": "T",
            "tipoDecisaoSelecionados": "A",
            "dados.ordenarPor": "dtPublicacao",
        }
        print(f"\nPOST {POST_URL} (dados.buscaEmenta=usucapiao, 2024)")
        r = c.post(POST_URL, data=payload)
        print(f"  status: {r.status_code} | bytes: {len(r.text):,}")

        procs = re.findall(r'\d{7}-\d{2}\.\d{4}\.\d{1,2}\.\d{2}\.\d{4}', r.text)
        print(f"  processos CNJ no HTML: {len(procs)} (unicos: {len(set(procs))})")
        # quantos resultados o portal diz ter?
        total = re.search(r'(\d[\d\.]*)\s*resultado', r.text, re.IGNORECASE)
        print(f"  'N resultados' no texto: {total.group(0) if total else '(nao achou)'}")
        # sinais
        for s in ("recaptcha", "g-recaptcha-response", "Nenhum resultado", "captcha",
                  "preencha", "obrigat"):
            if s.lower() in r.text.lower():
                print(f"  [sinal] '{s}' presente")

        if procs:
            print("\n  EXEMPLOS de processos:", list(set(procs))[:5])
            print("  >>> POST FUNCIONOU com campos corretos")
        else:
            print("\n  >>> sem processos — ver se e captcha ou outro campo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
