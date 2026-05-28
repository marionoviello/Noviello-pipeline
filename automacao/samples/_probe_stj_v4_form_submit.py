"""Probe v4: testar 3 estrategias pra trocar de informativo.

Achados do v3:
- Selects sao todos [oculto] (escondidos por CSS atras de tabs)
- Existe form 'idFormAbrirEdicaoInformativo' action GET para a propria URL
- Existe funcao JS global 'loadDetalhe'
- select.onchange_attr=None mas onchange_prop=object (handler programatico)

Hipoteses:
1. Chamar loadDetalhe(numero) direto
2. Setar value do select + submit do form idFormAbrirEdicaoInformativo
3. Navegar direto pra URL ?numero=XXXX
"""

from playwright.sync_api import sync_playwright

URL = "https://processo.stj.jus.br/jurisprudencia/externo/informativo/"
ALVO = "0837"


def verificar(page, etapa: str):
    info = page.evaluate("""() => {
        const hidden = document.querySelector('#idInformativoEdicaoAtual');
        const bloco = document.querySelector('#idInformativoBlocoLista');
        return {
            edicao: hidden ? hidden.value : null,
            bloco_len: bloco ? bloco.innerHTML.length : 0,
        };
    }""")
    print(f"  [{etapa}] edicao_atual='{info['edicao']}' bloco_len={info['bloco_len']:,}")
    return info["edicao"]


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    verificar(page, "inicial (default = 0890)")

    print()
    print("=" * 60)
    print("INSPECIONA loadDetalhe — assinatura/codigo da funcao")
    print("=" * 60)
    detalhe = page.evaluate("""() => {
        if (typeof loadDetalhe !== 'function') return '(loadDetalhe nao existe)';
        return loadDetalhe.toString().slice(0, 800);
    }""")
    print(detalhe)

    print()
    print("=" * 60)
    print("INSPECIONA form idFormAbrirEdicaoInformativo — campos e action")
    print("=" * 60)
    form_info = page.evaluate("""() => {
        const f = document.querySelector('#idFormAbrirEdicaoInformativo');
        if (!f) return null;
        return {
            action: f.action,
            method: f.method,
            innerHTML: f.innerHTML.slice(0, 1500),
            inputs: Array.from(f.querySelectorAll('input,select,button')).map(i => ({
                tag: i.tagName, name: i.name, id: i.id, type: i.type, value: i.value,
            })),
        };
    }""")
    print(form_info)

    print()
    print("=" * 60)
    print("ESTRATEGIA 1: chamar loadDetalhe(837) direto")
    print("=" * 60)
    try:
        page.evaluate("""([num]) => {
            if (typeof loadDetalhe === 'function') {
                loadDetalhe(num);
            } else {
                throw new Error('loadDetalhe nao definido');
            }
        }""", [837])
        page.wait_for_timeout(5000)
        edicao1 = verificar(page, "apos loadDetalhe(837)")
        if edicao1 == "0837":
            print("  >>> ESTRATEGIA 1 FUNCIONOU")
    except Exception as e:
        print(f"  ERRO: {e}")

    # reset: volta pra o inicio
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print()
    print("=" * 60)
    print("ESTRATEGIA 2: setar value do select e submeter form")
    print("=" * 60)
    try:
        page.evaluate("""([alvo]) => {
            const sel = document.querySelector('#idInformativoEdicoesCombo2024');
            const form = document.querySelector('#idFormAbrirEdicaoInformativo');
            if (sel) sel.value = alvo;
            if (form) form.submit();
        }""", [ALVO])
        page.wait_for_timeout(5000)
        edicao2 = verificar(page, "apos form.submit()")
        if edicao2 == "0837":
            print("  >>> ESTRATEGIA 2 FUNCIONOU")
    except Exception as e:
        print(f"  ERRO: {e}")

    # reset
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print()
    print("=" * 60)
    print("ESTRATEGIA 3: navegar direto pra URL com parametros candidatos")
    print("=" * 60)
    candidatos = [
        f"{URL}?edicao={ALVO}",
        f"{URL}?numero={ALVO}",
        f"{URL}?informativo={ALVO}",
        f"{URL}?id={ALVO}",
        f"{URL}#{ALVO}",
    ]
    for cand in candidatos:
        try:
            page.goto(cand, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            edicao = page.evaluate("""() => {
                const h = document.querySelector('#idInformativoEdicaoAtual');
                return h ? h.value : null;
            }""")
            mark = ">>> " if edicao == ALVO else "    "
            print(f"  {mark}{cand} -> edicao_atual='{edicao}'")
        except Exception as e:
            print(f"      {cand} -> ERRO: {e}")

    browser.close()
print("\nFIM")
