"""Probe v2: lista TODOS os selects por id, agrupa por ano, mostra
o padrão completo dos informativos."""

from playwright.sync_api import sync_playwright

URL = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    # Lista TODOS os selects (com id) e suas opções
    info = page.evaluate("""() => {
        const selects = Array.from(document.querySelectorAll('select[id]'));
        return selects.map(s => ({
            id: s.id,
            visible: s.offsetParent !== null,
            n_options: s.options.length,
            samples: Array.from(s.options).slice(0, 3).map(o => ({v: o.value, t: o.textContent.trim().slice(0, 70)})),
            last_3: Array.from(s.options).slice(-3).map(o => ({v: o.value, t: o.textContent.trim().slice(0, 70)})),
        }));
    }""")
    for s in info:
        vis = "VIS" if s["visible"] else "OCULTO"
        print(f"\n[{vis}] id={s['id']}  n={s['n_options']}")
        print(f"  primeiros:")
        for o in s["samples"]:
            print(f"    [{o['v']}] {o['t']}")
        if s["n_options"] > 3:
            print(f"  últimos:")
            for o in s["last_3"]:
                print(f"    [{o['v']}] {o['t']}")

    browser.close()
