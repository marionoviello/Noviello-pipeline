"""Probe v5: intercepta requests de rede para descobrir a URL AJAX
que o portal usa para carregar um informativo especifico.

A funcao loadDetalhe(num, strUrl) precisa do strUrl — ele e quem sabe
de onde puxar o conteudo. Vamos:

1. Carregar o portal (default = 0890) e gravar todos os requests
2. Tentar gatilhos JS que possam disparar a troca (focus, click custom,
   eventos extras) e ver se aparece request novo
3. Procurar dentro do HTML por URLs que contenham '0890' ou '0837' (talvez
   estao em data-url, atributos custom, etc)
"""

from playwright.sync_api import sync_playwright

URL = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"
ALVO = "0837"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = ctx.new_page()

    # Captura todos requests
    requests_log: list[str] = []
    page.on("request", lambda req: requests_log.append(f"{req.method} {req.url}"))

    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2500)

    print("=" * 70)
    print(f"REQUESTS na carga inicial: {len(requests_log)} total")
    print("=" * 70)
    # Filtra so os que parecem chamadas dinamicas (excluindo CSS/imagens/fonts)
    relevantes = [r for r in requests_log
                  if not any(ext in r.lower() for ext in
                  (".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".ttf", ".css", ".ico"))]
    for r in relevantes[-30:]:  # ultimos 30
        print(f"  {r}")

    print()
    print("=" * 70)
    print("Procura no HTML por URLs com '0890' ou padroes /SCON/")
    print("=" * 70)
    achados = page.evaluate("""() => {
        const html = document.documentElement.outerHTML;
        // procura padroes
        const m1 = html.match(/[^"'\\s]*0890[^"'\\s]*/g) || [];
        const m2 = html.match(/\\/SCON\\/[^"'\\s]+/g) || [];
        const m3 = html.match(/[^"'\\s]*\\.json[^"'\\s]*/gi) || [];
        const m4 = html.match(/loadDetalhe\\([^)]+\\)/g) || [];
        return {
            com_0890: [...new Set(m1)].slice(0, 10),
            scon_urls: [...new Set(m2)].slice(0, 10),
            json_urls: [...new Set(m3)].slice(0, 5),
            loadDetalhe_chamadas: [...new Set(m4)].slice(0, 10),
        };
    }""")
    for k, v in achados.items():
        print(f"\n  {k}:")
        for item in v:
            print(f"    {item}")

    print()
    print("=" * 70)
    print("Inspeciona uma <option> do select 2024 — tem atributos custom?")
    print("=" * 70)
    opt_info = page.evaluate("""([alvo]) => {
        const sel = document.querySelector('#idInformativoEdicoesCombo2024');
        if (!sel) return null;
        const opt = Array.from(sel.options).find(o => o.value === alvo);
        if (!opt) return null;
        const attrs = {};
        for (const attr of opt.attributes) {
            attrs[attr.name] = attr.value;
        }
        return {
            outerHTML: opt.outerHTML,
            attrs: attrs,
            dataset: {...opt.dataset},
        };
    }""", [ALVO])
    print(opt_info)

    print()
    print("=" * 70)
    print("Limpa log e dispara select 2024 + click no botao do form")
    print("=" * 70)
    requests_log.clear()

    # Tenta encontrar e clicar num botao associado ao form de abrir edicao
    botoes = page.evaluate("""() => {
        // procura botoes/links com texto/onclick relacionado a 'abrir' ou 'edicao'
        const els = Array.from(document.querySelectorAll('button, input[type=button], input[type=submit], a[href]'));
        return els.filter(el => {
            const txt = (el.textContent + ' ' + (el.value || '') + ' ' + (el.getAttribute('onclick') || '') + ' ' + (el.getAttribute('href') || '')).toLowerCase();
            return txt.includes('abrir') || txt.includes('edicao') || txt.includes('informativo');
        }).slice(0, 10).map(el => ({
            tag: el.tagName,
            id: el.id,
            text: (el.textContent || '').trim().slice(0, 50),
            onclick: (el.getAttribute('onclick') || '').slice(0, 200),
            href: el.getAttribute('href') || '',
        }));
    }""")
    print("Botoes/links potenciais:")
    for b in botoes:
        print(f"  <{b['tag']}> id={b['id']!r}")
        print(f"    text={b['text']!r}")
        print(f"    onclick={b['onclick']!r}")
        print(f"    href={b['href']!r}")

    print()
    print("=" * 70)
    print("Tenta: setar value + chamar onchange do select 2024")
    print("=" * 70)
    requests_log.clear()
    try:
        page.evaluate("""([alvo]) => {
            const sel = document.querySelector('#idInformativoEdicoesCombo2024');
            sel.value = alvo;
            // jquery onchange?
            if (window.jQuery) {
                window.jQuery(sel).trigger('change');
            }
        }""", [ALVO])
        page.wait_for_timeout(4000)
        print(f"\nNovos requests apos jQuery trigger ({len(requests_log)}):")
        for r in requests_log:
            print(f"  {r}")
        edicao = page.evaluate("""() => {
            const h = document.querySelector('#idInformativoEdicaoAtual');
            return h ? h.value : null;
        }""")
        print(f"\nedicao_atual depois: '{edicao}'")
    except Exception as e:
        print(f"ERRO: {e}")

    browser.close()
print("\nFIM")
