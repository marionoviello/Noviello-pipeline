"""Probe: verifica se PDFs anuais agregados existem em /docs_internet/.

Hipotese: cada ano tem 1 PDF agregando os ~38 informativos do ano em
/docs_internet/informativos/anuais/informativo_anual_NNNN.pdf

Diagnostic A do probe v3 listou esse padrao no select #idSelectAnoDataPDF
com value para 2023. Se funcionar pra 2024 (mais provavel) ou pra outros
anos via httpx direto, conseguimos pivotar a estrategia sem Playwright.
"""

from io import BytesIO

import httpx

BASE = "https://processo.stj.jus.br/docs_internet/informativos/anuais/informativo_anual_{ano}.pdf"
ANOS = [2024, 2023, 2025, 2022, 2021]


def main() -> int:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    }
    sucesso = 0

    for ano in ANOS:
        url = BASE.format(ano=ano)
        print(f"\n== {ano} ==")
        print(f"URL: {url}")
        try:
            resp = httpx.head(url, headers=headers, timeout=15.0, follow_redirects=True)
            print(f"  HEAD: status={resp.status_code} content-type={resp.headers.get('content-type', '?')}")
            if resp.status_code != 200:
                continue

            # Faz GET completo se HEAD ok (alguns servidores nao confiam em HEAD)
            resp = httpx.get(url, headers=headers, timeout=60.0, follow_redirects=True)
            print(f"  GET:  status={resp.status_code} bytes={len(resp.content):,}")
            if resp.status_code != 200 or len(resp.content) < 100_000:
                print("  >>> FALHOU (status ou tamanho)")
                continue

            ct = resp.headers.get("content-type", "")
            if "pdf" not in ct.lower() and not resp.content.startswith(b"%PDF"):
                print(f"  >>> FALHOU (nao parece PDF, content-type={ct})")
                continue

            # Tenta extrair texto e contar PROCESSOs
            from pypdf import PdfReader
            try:
                reader = PdfReader(BytesIO(resp.content))
                n_pags = len(reader.pages)
                # le so as primeiras 20 paginas pra rapidez (suficiente pra confirmar formato)
                texto = "\n".join(p.extract_text() or "" for p in reader.pages[:20])
                n_processos = texto.count("PROCESSO")
                n_resp = texto.count("REsp")
                print(f"  PDF OK: {n_pags} paginas; nas primeiras 20: "
                      f"{n_processos}x PROCESSO, {n_resp}x REsp")
                if n_processos >= 3:  # baixo pra teste, espera-se MUITO mais
                    print(f"  >>> PASSOU pra {ano}")
                    sucesso += 1
                else:
                    print("  >>> texto pobre — pode estar criptografado ou imagem")
            except Exception as exc:  # noqa: BLE001
                print(f"  ERRO ao parsear PDF: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ERRO HTTP: {exc}")

    print(f"\n{sucesso}/{len(ANOS)} anos validados.")
    return 0 if sucesso >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
