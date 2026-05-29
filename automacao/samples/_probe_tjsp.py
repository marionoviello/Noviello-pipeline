"""Probe diagnostico do TJ-SP cjsg — testa o fluxo session-aware contra o portal real.

1. GET previo em consultaCompleta.do  -> status, cookies (JSESSIONID?), CSRF
2. POST em resultadoCompleta.do com cookies + CSRF -> status, tamanho, n acordaos
Sem Anthropic, sem custo. Diagnostica se o portal coopera ou resiste (como o STJ).
"""

from datetime import date

import httpx

from src.julgado_radar import feeds_tjsp as f

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def main() -> int:
    print("=" * 64)
    print("PROBE TJ-SP cjsg — fluxo session-aware")
    print("=" * 64)

    with httpx.Client(
        headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"},
        timeout=60.0, follow_redirects=True,
    ) as client:

        # ---- 1. GET previo ----
        print(f"\n[1] GET {f.URL_CJSG_CONSULTA}")
        try:
            r0 = client.get(f.URL_CJSG_CONSULTA)
            print(f"    status: {r0.status_code} | bytes: {len(r0.content):,}")
            cookies = dict(client.cookies)
            print(f"    cookies: {list(cookies.keys())}")
            tem_jsession = any("JSESSION" in k.upper() for k in cookies)
            print(f"    JSESSIONID presente: {tem_jsession}")
        except Exception as exc:  # noqa: BLE001
            print(f"    ERRO no GET previo: {exc}")
            return 1

        html0 = r0.text
        csrf = f.extrair_csrf(html0)
        print(f"    CSRF extraido: {csrf[:24] + '...' if csrf else '(NAO ACHOU)'}")

        # diagnostico: o form de pesquisa existe?
        import re
        tem_form = bool(re.search(r'id=["\']?dadosConsulta', html0)) or "cjsg" in html0.lower()
        print(f"    pagina parece a de consulta: {tem_form}")
        # procura nomes de campos hidden uteis
        hiddens = re.findall(r'<input[^>]+type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\']', html0)
        print(f"    inputs hidden (top 10): {hiddens[:10]}")

        # ---- 2. POST de busca ----
        termo = "usucapiao"
        inicio, fim = date(2024, 1, 1), date(2024, 12, 31)
        payload = f.montar_payload_cjsg(termo, inicio, fim, csrf=csrf)
        print(f"\n[2] POST {f.URL_CJSG}  (termo='{termo}', 2024)")
        print(f"    campos do payload: {list(payload.keys())}")
        try:
            r1 = client.post(f.URL_CJSG, data=payload)
            print(f"    status: {r1.status_code} | bytes: {len(r1.content):,}")
        except Exception as exc:  # noqa: BLE001
            print(f"    ERRO no POST: {exc}")
            return 1

        html1 = r1.text
        # parse
        acordaos = f.parse_cjsg_html(html1)
        print(f"    acordaos parseados: {len(acordaos)}")
        # diagnostico bruto: quantos processos CNJ aparecem no HTML?
        procs = re.findall(r'\d{7}-\d{2}\.\d{4}\.\d{1,2}\.\d{2}\.\d{4}', html1)
        print(f"    processos CNJ no HTML (bruto): {len(procs)} (unicos: {len(set(procs))})")

        if acordaos:
            print("\n    Exemplos:")
            for a in acordaos[:3]:
                print(f"      - {a.processo_id} | {a.relator[:30]} | {a.ementa[:60]}")

        # sinais de bloqueio
        baixo = html1.lower()
        for sinal in ("captcha", "acesso negado", "forbidden", "erro", "bloqueado", "indisponiv"):
            if sinal in baixo:
                print(f"    [!] sinal '{sinal}' encontrado no HTML de resposta")

    print("\n" + "=" * 64)
    if acordaos:
        print(">>> PROBE OK — portal cooperou, parser extraiu acordaos")
        return 0
    print(">>> PROBE PARCIAL — POST respondeu mas parser nao extraiu. Ver HTML.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
