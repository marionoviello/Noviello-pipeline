"""Seleciona 1 informativo via Playwright e captura o HTML do conteúdo."""

from playwright.sync_api import sync_playwright

URL = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)

    # Lista os selects e seus IDs
    selects_info = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('select')).map(s => ({
            id: s.id,
            name: s.name,
            n_options: s.options.length,
            first_option: s.options[0] ? {value: s.options[0].value, text: s.options[0].textContent.trim().slice(0, 60)} : null,
        }));
    }""")
    print("Selects identificados:")
    for s in selects_info:
        print(f"  id='{s['id']}' name='{s['name']}' n={s['n_options']} first={s['first_option']}")

    # Acha o select principal (deve ter os informativos mais recentes 2026)
    # Tenta selecionar o primeiro select com >5 opções
    print("\nSelecionando primeira opção do select 'idInformativoSelectEspecial' ou similar...")
    candidatos = [s for s in selects_info if s["n_options"] > 5 and s["id"]]
    if not candidatos:
        print("Nenhum select grande encontrado")
        browser.close()
        exit()
    sel = candidatos[0]
    print(f"Escolhi: id='{sel['id']}', valor='{sel['first_option']['value']}'")

    try:
        page.select_option(f"#{sel['id']}", value=sel["first_option"]["value"])
        page.wait_for_timeout(3000)  # espera AJAX carregar
        # Procura conteudo renderizado
        content_info = page.evaluate("""() => {
            const bloco = document.querySelector('#idInformativoBlocoLista');
            return {
                html_len: bloco ? bloco.innerHTML.length : 0,
                text_preview: bloco ? bloco.textContent.slice(0, 500) : '(sem bloco)',
                n_items: bloco ? bloco.querySelectorAll('.divCell').length : 0,
            };
        }""")
        print(f"  bloco-lista len={content_info['html_len']:,}, items={content_info['n_items']}")
        print(f"  preview: {content_info['text_preview'][:200]}")
    except Exception as e:
        print(f"  ERRO ao selecionar: {e}")

    browser.close()
