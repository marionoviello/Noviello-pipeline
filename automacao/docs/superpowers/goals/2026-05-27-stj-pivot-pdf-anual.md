# /goal: Pivot do scraper STJ — baixar PDF anual em vez de scraping individual

## Contexto (já commitado, NÃO regredir)

- Branch `main`, último commit `d2e2f22` (push em GitHub `marionoviello/Noviello-pipeline`)
- 147/147 testes do `julgado_radar` passam
- `descobrir_informativos` via Playwright **FUNCIONA** — lista os 38 infos de 2024 com `select_id/option_value/titulo` corretos. **NÃO MEXER**.
- `baixar_informativo` via Playwright **NÃO FUNCIONA** — portal STJ retorna sempre o informativo mais recente (0890) independente do select. Probes v3/v4/v5 em `automacao/samples/_probe_stj_*.py` confirmam que:
  * selects são todos `oculto:true` (atrás de tabs CSS)
  * `loadDetalhe(num, strUrl)` precisa de `strUrl` que não está no HTML
  * `<option>`s não têm `data-url` custom
  * `jQuery trigger('change')` não dispara request STJ algum
  * form `idFormAbrirEdicaoInformativo` é form de pesquisa, não de abrir

## Nova estratégia

Diagnostic A do probe v3 revelou: existe select `#idSelectAnoDataPDF` com options apontando para PDFs anuais agregados em `/docs_internet/informativos/anuais/informativo_anual_NNNN.pdf`.

Esse path em `docs_internet/` é servido **sem Cloudflare e sem JS** (httpx puro funciona — testado em wave 1 com ZIPs RTF, baixou 9-25MB ok). Cada PDF anual contém TODOS os ~38 informativos do ano. Parser atual (`particionar_itens` + Anthropic) já sabe processar PDF informativo.

## Passo 0 — probe rápido (5 min)

1. Criar `automacao/samples/_probe_stj_pdf_anual.py` que tenta `httpx.get` nas URLs:
   - `https://processo.stj.jus.br/docs_internet/informativos/anuais/informativo_anual_2024.pdf`
   - `https://processo.stj.jus.br/docs_internet/informativos/anuais/informativo_anual_2023.pdf`
2. Validar: status 200, content-type `application/pdf`, tamanho >1MB.
3. Se 2024 existir: extrair texto via pypdf, contar quantas vezes aparece `'PROCESSO'` (esperado: ~38× ou mais).
4. Se 2024 NÃO existir: tentar 2025 e 2023 (talvez 2024 ainda esteja sendo compilado). Documentar achados.

## Refatoração (manter interface pública)

1. **`automacao/src/julgado_radar/feeds_stj.py`**:
   - `InformativoRef` conceitualmente vira "InformativoAnoRef": agora cada ref representa 1 ANO inteiro, não 1 informativo. Mas manter campo `numero` (pode virar o ano), `ano`, e adicionar `url_pdf_anual`.
   - `descobrir_informativos(anos)` continua via Playwright lendo os combos (mantém para sabermos QUAIS informativos existem em cada ano — útil pra metadata futura).
   - Adicionar nova função `obter_pdfs_anuais(anos)` que devolve list de `{ano, url, ref}` para os PDFs anuais agregados.
   - `baixar_informativo` passa a aceitar URL direta + `http_get` (sem Playwright). Renomear pra `baixar_pdf_anual` ou manter assinatura com fallback.

2. **`automacao/src/julgado_radar/parser.py`**:
   - `_ler_pdf` já lê `.pdf` via pypdf. Só verificar que aceita arquivos grandes (>10MB). Se memory pressure for problema, ler página por página.
   - `particionar_itens` já existe — confirmar que separa bem num PDF agregado (regex `'PROCESSO|RECURSO ESPECIAL|HABEAS CORPUS...'`).

3. **`automacao/src/julgado_radar/backfill.py`**:
   - `_processar_stj` agora itera por ANO (não por informativo), baixa 1 PDF anual por ano, e roda `particionar_itens` nele → N itens via Anthropic.
   - Manter `fetch_log` idempotente (chave: `stj-pdf-anual-NNNN`).

## Testes (manter 147/147 baseline + adicionar novos)

- `tests/test_feeds_stj.py`: adicionar ~5 testes pra `obter_pdfs_anuais` e `baixar_pdf_anual` com `http_get` mockado.
- `tests/test_backfill.py`: adaptar `test_executar_backfill_stj_completo_com_mocks` pra novo fluxo (mock `http_get` devolvendo PDF bytes + mock anthropic devolvendo item válido). Manter idempotência.
- Rodar:
  ```
  cd C:\Users\mario\Documents\Noviello-Produtividade\automacao
  .venv\Scripts\python.exe -m pytest tests/julgado_radar/ -q --basetemp=C:/Temp/pytest-fresh
  ```
- **Critério: ≥150 testes passando, zero regressão.**

## Smoke real (depois dos testes passarem)

1. Atualizar `automacao/samples/_smoke_stj_baixar.py` para a nova estratégia:
   - Baixa PDF anual 2024 (sem Anthropic ainda, ~10s)
   - Validar: arquivo >1MB, texto contém ≥30 'PROCESSO'
2. Atualizar runbook `automacao/docs/superpowers/runbooks/2026-05-27-smoke-radar-stj.md` com os novos passos.
3. Rodar `python -m src.julgado_radar.backfill --janela 1 --fontes stj`
   - **Critério: ≥30 julgados no DB de áreas urbanístico/imobiliário/sucessório**
   - Custo esperado: ~$3-5 (1 PDF grande × ~50K tokens input × 38 chamadas de `extrair_item_stj`)

## Commits (3 granulares)

1. `"STJ pivot: baixar PDF anual em vez de scraping individual"` (código + testes)
2. `"Smoke real: PDF anual 2024 baixado e parseado"` (samples + runbook + DB pop)
3. (opcional) `"Probe STJ: documenta limites do portal dinâmico"`

## Critérios de aceitação finais

- 150+ testes passando
- `state/julgado_radar.db` populado com ≥30 julgados de 2024
- Pelo menos 3 julgados em cada uma das 3 áreas (urbanístico, imobiliário, sucessório)
- 3 commits granulares em `main`, pushed para GitHub
- Runbook atualizado

## Fallback se Passo 0 falhar (PDF anual 2024 não existir)

Tentar `/docs_internet/informativos/ZIP/InformativosSTJ_2024.zip` (testado em wave anterior — baixa 18MB), descompactar, mas só se striprtf conseguir abrir os .rtf de dentro (provavelmente vai falhar com binários embutidos como antes). Se também falhar, **parar e reportar ao Mario**.

## Não regredir

- TJ-SP wave 2 (session-aware) deve continuar funcionando — só mexer em STJ.
- Anti-duplicata registry continua intacto.
- Painel não precisa mudar.

## Estado inicial

- `cd C:\Users\mario\Documents\Noviello-Produtividade`
- `git status` deve estar limpo (último commit `d2e2f22`)
- `.venv` ativo em `automacao/.venv/`
- Após push final, verificar `git log origin/main..HEAD` está vazio.
