# Calibração dos scrapers STJ (e TJ-SP) — notas pós-probe

**Data:** 2026-05-27
**Status:** investigação técnica concluída, aguardando implementação

Esta nota documenta **achados de probe real** contra os portais STJ e TJ-SP,
substituindo a estratégia inicial (httpx + regex) que falhou contra JavaScript
dinâmico e proteção Cloudflare.

## STJ — diagnóstico

### Portal real

URL canônica: `https://processo.stj.jus.br/jurisprudencia/externo/informativo/`

**Renderização**: a página carrega um esqueleto e injeta a lista via JavaScript.
HTML estático (1.172 bytes) tem zero menções a "informativo" ou ".pdf".
`feeds_stj.py::parse_listagem()` (regex em HTML cru) **sempre retorna lista vazia**.

### Inventário de selects (após Playwright render)

| Select ID | Conteúdo | Volume |
|---|---|---|
| `idInformativoEdicoesCombo2026` | Edições regulares 2026 | 16 (até maio) |
| `idInformativoEdicoesCombo2025` | Edições regulares 2025 | 37 |
| `idInformativoEdicoesCombo2024` | Edições regulares 2024 | 38 |
| `idInformativoEdicoesCombo2023` | Edições regulares 2023 | 38 |
| `idInformativoEdicoesCombo2022` | Edições regulares 2022 | 40 |
| `idInformativoEdicoesCombo2021` | Edições regulares 2021 | 38 |
| `idInformativoEdicoesComboE` | Informativos Especiais | 30 (2025-2026) |
| `idSelectAnoDataPDF` | PDFs **anuais agregados** | Até 2023 (incompleto) |
| `idSelectAnoDataRTF` | **ZIPs anuais com RTFs** | 2021-2025 disponíveis |

**Cada option do combo regular tem `value` = número do informativo zero-padded
4 dígitos** (ex: `0890` para Informativo 890).

### Caminho A — ZIP anual (descartado)

URLs funcionam via httpx (sem Cloudflare): `https://processo.stj.jus.br/docs_internet/informativos/ZIP/InformativosSTJ_{ano}.zip`

| Ano | Tamanho |
|---|---|
| 2021 | 9.5 MB |
| 2022 | 25.9 MB |
| 2023 | 24.9 MB |
| 2024 | 18.3 MB |
| 2025 | 13.1 MB (parcial — só primeiro semestre) |
| 2026 | 404 (não gerado ainda) |

**Problema**: arquivos `.rtf` dentro dos ZIPs contêm **objetos binários embutidos**
(OLE/imagens?). `striprtf` retorna texto corrompido com bytes não-imprimíveis no
início. Pandoc/LibreOffice resolveriam, mas adicionam dependência externa.

### Caminho B — Playwright + select dinâmico ✅

Estratégia validada via probe:

```python
page = browser.new_page()
page.goto("https://processo.stj.jus.br/jurisprudencia/externo/informativo/")
page.wait_for_load_state("networkidle")
# Pra cada (ano, numero) que quero baixar:
page.select_option("#idInformativoEdicoesCombo2024", value="0837")
page.wait_for_timeout(3000)  # AJAX
html_bloco = page.eval_on_selector("#idInformativoBlocoLista", "el => el.innerHTML")
# html_bloco contém os ~10-15 itens do informativo, texto limpo HTML
```

**Custo**: ~5s por informativo (1s rede + 2s AJAX + 2s parse).
**Volume 5 anos**: 207 informativos × 5s = ~17min execução total.

### Implementação proposta (substitui `feeds_stj.py`)

```python
# src/julgado_radar/feeds_stj.py — REWRITE
def descobrir_informativos(anos, *, playwright_factory=None) -> list[InformativoRef]:
    """Usa Playwright pra extrair todas as edições dos combos por ano."""
    refs = []
    with (playwright_factory or _default_playwright)() as page:
        page.goto(URL_PORTAL_INFORMATIVOS)
        page.wait_for_load_state("networkidle")
        for ano in anos:
            select_id = f"idInformativoEdicoesCombo{ano}"
            opts = page.eval_on_selector(
                f"#{select_id}",
                "s => Array.from(s.options).map(o => ({v: o.value, t: o.textContent}))",
            )
            for opt in opts:
                refs.append(InformativoRef(
                    numero=int(opt["v"]),
                    ano=ano,
                    select_id=select_id,
                    option_value=opt["v"],
                    titulo=opt["t"].strip(),
                ))
    return refs


def baixar_informativo(ref, cache_dir, *, playwright_factory=None) -> Path:
    """Captura HTML renderizado do informativo via select_option."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    destino = cache_dir / f"inf-{ref.numero:04d}.html"
    if destino.exists() and destino.stat().st_size > 0:
        return destino

    with (playwright_factory or _default_playwright)() as page:
        page.goto(URL_PORTAL_INFORMATIVOS)
        page.wait_for_load_state("networkidle")
        page.select_option(f"#{ref.select_id}", value=ref.option_value)
        page.wait_for_timeout(3000)
        html_bloco = page.eval_on_selector("#idInformativoBlocoLista", "el => el.innerHTML")

    destino.write_text(html_bloco, encoding="utf-8")
    return destino
```

E parser:

```python
# src/julgado_radar/parser.py — adaptar
def extrair_itens_de_informativo(arq_html_path: Path) -> list[dict]:
    """Recebe HTML do bloco de itens e devolve lista de julgados estruturados."""
    html = arq_html_path.read_text(encoding="utf-8")
    # Anthropic structured output — schema já está definido
    return anthropic_client.parse_stj_informativo(html)
```

## TJ-SP — diagnóstico

**Endpoint**: `https://esaj.tjsp.jus.br/cjsg/resultadoCompleta.do`

**Bloqueio**: POST direto retorna 403 (sem cookies de sessão).

**Solução validada em outros projetos** (não probada aqui, mas é padrão):

```python
with httpx.Client(headers={"User-Agent": "Mozilla/5.0 ..."}) as client:
    # GET prévio em consulta inicial pega JSESSIONID + tokens hidden
    r0 = client.get("https://esaj.tjsp.jus.br/cjsg/consultaCompleta.do")
    # extrai csrf token de input hidden ou meta
    soup = BeautifulSoup(r0.text, "html.parser")
    csrf = soup.find("input", {"name": "_csrf"})["value"]
    # POST agora carrega cookies + csrf
    r1 = client.post("...resultadoCompleta.do", data={..., "_csrf": csrf})
```

Esse é o padrão "session-aware scraping" — `httpx.Client` mantém cookies
automaticamente entre requests.

## Goal recomendado para nova rodada autônoma

```
/goal calibrar feeds_stj.py para usar Playwright + select dinâmico contra
processo.stj.jus.br/jurisprudencia/externo/informativo/ extraindo HTML renderizado
de cada informativo (ZIPs RTF descartados — striprtf falha); calibrar
feeds_tjsp.py para usar httpx.Client com GET prévio em
esaj.tjsp.jus.br/cjsg/consultaCompleta.do extraindo JSESSIONID+CSRF antes
do POST; smoke test backfill --janela 1 --ano 2024 --fontes stj com pelo
menos 5 informativos parseados via Anthropic e >=30 julgados de áreas
urbanístico/imobiliário/sucessório indexados em state/julgados_radar.db;
233+ baseline testes (zero regressão) + ~15 novos cobrindo Playwright
mock e Client sessão; 3 commits granulares (stj-rewrite, tjsp-rewrite,
smoke-real).
```

**Prompt inicial**:

```
Le este documento (docs/superpowers/specs/2026-05-27-radar-stj-calibracao.md)
e implementa a calibração descrita. Mantém a interface pública dos feeds
(descobrir_informativos, baixar_informativo) — só muda implementação interna.
Adicione fixture de HTML de informativo real em tests/fixtures/stj/ para os
testes (mocka Playwright via factory injetável). Quando terminar, roda smoke
real: python -m src.julgado_radar.backfill --janela 1 --ano 2024 --fontes stj
e me mostra: (a) quantos informativos foram baixados, (b) quantos itens
chegaram ao DB, (c) custo Anthropic, (d) 3 julgados de exemplo das áreas-alvo.
```

## O que NÃO fazer

- Não voltar a usar `striprtf` em RTF do STJ (binários quebram)
- Não tentar `httpx` puro em `scon.stj.jus.br` (Cloudflare bloqueia)
- Não inserir 2026 nos ZIPs (não existe ainda)
- Não modificar a SPEC anterior (2026-05-26-radar-julgados-design.md) — esta
  é um **adendo de calibração**, não substituto

## Resumo executivo

| Item | Decisão |
|---|---|
| STJ via ZIP RTF | ❌ Abandonado |
| STJ via Playwright | ✅ Implementar |
| STJ via httpx em `scon.stj` | ❌ Cloudflare |
| TJ-SP via httpx.Client com sessão | ✅ Implementar |
| Tempo estimado de execução | ~17min STJ + ~30min TJ-SP = ~50min |
| Custo Anthropic 1 ano só (smoke) | ~$2-4 |
| Custo Anthropic 5 anos completos | ~$15-25 (após smoke) |
