"""Probe v3: investiga COMO o portal STJ carrega um informativo nao-default.

O problema: page.evaluate setou .value do select e disparou change, mas o
portal continuou mostrando inf-0890 (mais recente) em vez do solicitado.

Hipoteses testadas:
A. Select visivel != select que muda o conteudo (cada ano e um select diferente)
B. Precisa clicar num <a>/link da lista de informativos em vez de mudar select
C. Cada informativo tem URL propria (query param ou hash)
D. Submit de form/botao
"""

from playwright.sync_api import sync_playwright

URL = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"
ALVO = "0837"  # Informativo 837 (17/12/2024)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print("=" * 60)
    print("DIAGNOSTICO A: quais selects estao visiveis?")
    print("=" * 60)
    selects = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('select[id]')).map(s => ({
            id: s.id,
            visible: s.offsetParent !== null,
            current_value: s.value,
            n_options: s.options.length,
            has_837: Array.from(s.options).some(o => o.value === '0837'),
        }));
    }""")
    for s in selects:
        marker = ">>> " if s["has_837"] else "    "
        vis = "VIS" if s["visible"] else "oculto"
        print(f"{marker}[{vis}] id={s['id']} value={s['current_value']!r} "
              f"n={s['n_options']} has_837={s['has_837']}")

    print()
    print("=" * 60)
    print("DIAGNOSTICO B: existe <a> ou link na pagina apontando pra 0837?")
    print("=" * 60)
    links = page.evaluate("""() => {
        const todos = Array.from(document.querySelectorAll('a, button, [onclick]'));
        return todos.filter(el => {
            const txt = (el.textContent || '').trim();
            const oc = el.getAttribute('onclick') || '';
            const href = el.getAttribute('href') || '';
            return /837/.test(txt) || /837/.test(oc) || /837/.test(href);
        }).slice(0, 5).map(el => ({
            tag: el.tagName,
            text: (el.textContent || '').trim().slice(0, 80),
            href: el.getAttribute('href') || '',
            onclick: (el.getAttribute('onclick') || '').slice(0, 200),
            id: el.id,
            classes: el.className,
        }));
    }""")
    if links:
        for L in links:
            print(f"  <{L['tag'].lower()}> id={L['id']!r} class={L['classes']!r}")
            print(f"    text: {L['text']!r}")
            print(f"    href: {L['href']!r}")
            print(f"    onclick: {L['onclick']!r}")
    else:
        print("  (nenhum link encontrado com '837')")

    print()
    print("=" * 60)
    print("DIAGNOSTICO C: descobrir funcao JS que carrega informativo")
    print("=" * 60)
    funcs = page.evaluate("""() => {
        // procura funcoes globais que tenham 'informativo' no nome
        const nomes = Object.getOwnPropertyNames(window).filter(n =>
            /informativo/i.test(n) || /carregar/i.test(n) || /load/i.test(n)
        );
        return nomes.slice(0, 20);
    }""")
    print(f"  funcoes globais relevantes: {funcs}")

    # Inspeciona o onchange do select 2024
    onchange = page.evaluate("""() => {
        const sel = document.querySelector('#idInformativoEdicoesCombo2024');
        if (!sel) return null;
        return {
            onchange_attr: sel.getAttribute('onchange'),
            onchange_prop: typeof sel.onchange,
            visible: sel.offsetParent !== null,
        };
    }""")
    print(f"  select 2024 onchange: {onchange}")

    print()
    print("=" * 60)
    print("DIAGNOSTICO D: testar select_option com force=True (bypassa visibilidade)")
    print("=" * 60)
    try:
        page.select_option("#idInformativoEdicoesCombo2024", value=ALVO, force=True, timeout=10000)
        page.wait_for_timeout(3000)
        depois = page.evaluate("""() => {
            const hidden = document.querySelector('#idInformativoEdicaoAtual');
            const bloco = document.querySelector('#idInformativoBlocoLista');
            return {
                edicao_atual: hidden ? hidden.value : '(sem hidden)',
                bloco_len: bloco ? bloco.innerHTML.length : 0,
            };
        }""")
        print(f"  apos force=True: {depois}")
    except Exception as e:
        print(f"  ERRO: {e}")

    print()
    print("=" * 60)
    print("DIAGNOSTICO E: tentar disparar evento de mudanca + esperar")
    print("=" * 60)
    try:
        page.evaluate("""([alvo]) => {
            const sel = document.querySelector('#idInformativoEdicoesCombo2024');
            if (!sel) throw new Error('sem select');
            sel.value = alvo;
            // dispara varios eventos pra cobrir todas as hipoteses
            sel.dispatchEvent(new Event('input', {bubbles: true}));
            sel.dispatchEvent(new Event('change', {bubbles: true}));
            sel.dispatchEvent(new Event('blur', {bubbles: true}));
            // se tem onchange como atributo, chama
            if (typeof sel.onchange === 'function') sel.onchange();
        }""", [ALVO])
        page.wait_for_timeout(5000)  # espera mais
        depois = page.evaluate("""() => {
            const hidden = document.querySelector('#idInformativoEdicaoAtual');
            return hidden ? hidden.value : '(sem)';
        }""")
        print(f"  apos eventos+5s: edicao_atual='{depois}' (esperado: '0837')")
    except Exception as e:
        print(f"  ERRO: {e}")

    print()
    print("=" * 60)
    print("DIAGNOSTICO F: olhar URL atual + cookies/forms")
    print("=" * 60)
    print(f"  URL: {page.url}")
    forms = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('form')).map(f => ({
            action: f.action,
            method: f.method,
            id: f.id,
        }));
    }""")
    print(f"  Forms: {forms}")

    browser.close()
print("\nFIM")
