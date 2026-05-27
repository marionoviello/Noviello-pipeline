"""Renderiza o portal STJ com Playwright (passa Cloudflare) e descobre:
1. Numero do informativo atual
2. Como navegar pra históricos
3. URL real dos PDFs"""

from playwright.sync_api import sync_playwright

URL = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Extrai estado atual
    info = page.evaluate("""() => {
        const r = {};
        // Inputs hidden
        r.inputs = [];
        document.querySelectorAll('input').forEach(i => {
            if (i.value) r.inputs.push({name: i.name, value: i.value.slice(0, 80)});
        });
        // Numero atual do informativo (visivel no header)
        const headers = document.querySelectorAll('h1, h2, h3, .titulo-edicao');
        r.headers = Array.from(headers).slice(0, 5).map(h => h.textContent.trim().slice(0, 100));
        // Selects (combos de informativos)
        r.selects = [];
        document.querySelectorAll('select').forEach(s => {
            const opts = Array.from(s.options).slice(0, 5).map(o => ({
                value: o.value, text: o.textContent.trim().slice(0, 60)
            }));
            r.selects.push({name: s.name, n_options: s.options.length, samples: opts});
        });
        // Links com query string que podem ser navegação
        const links = [];
        document.querySelectorAll('a[href*="?"]').forEach(a => {
            const h = a.href;
            if (h.includes('informativo') || h.includes('publicacao') || h.includes('SCON')) {
                links.push(h.slice(0, 200));
            }
        });
        r.links_navegacao = [...new Set(links)].slice(0, 10);
        // Forms
        r.forms = [];
        document.querySelectorAll('form').forEach(f => {
            r.forms.push({action: f.action, method: f.method});
        });
        return r;
    }""")
    print("=== HEADERS ===")
    for h in info["headers"]:
        print(f"  {h}")
    print("\n=== INPUTS (com valor) ===")
    for i in info["inputs"]:
        print(f"  {i['name']} = {i['value']}")
    print("\n=== SELECTS (combos) ===")
    for s in info["selects"]:
        print(f"  {s['name']}: {s['n_options']} options")
        for opt in s["samples"]:
            print(f"    [{opt['value']}] {opt['text']}")
    print("\n=== FORMS ===")
    for f in info["forms"]:
        print(f"  {f['method'].upper()} {f['action']}")
    print("\n=== LINKS DE NAVEGAÇÃO ===")
    for l in info["links_navegacao"]:
        print(f"  {l}")

    # Testa: clica em "anterior" pra ver como volta um informativo
    print("\n=== Tentando botao 'Anterior' ===")
    try:
        page.click("text=Anterior", timeout=3000)
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1000)
        url2 = page.url
        print(f"  URL apos clicar Anterior: {url2}")
    except Exception as e:
        print(f"  Sem botao 'Anterior' obvio: {str(e)[:80]}")

    browser.close()
