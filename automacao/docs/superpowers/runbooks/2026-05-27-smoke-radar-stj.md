# Runbook: Backfill do Radar STJ (estratégia final — PDF anual)

**Status:** validado end-to-end com dados reais no DB (2026-05-28)
**Pré-requisitos:** `.venv` ativado, Anthropic key em `.env`

## Estratégia final (depois de 3 tentativas)

| Tentativa | Resultado |
|---|---|
| httpx + regex na listagem antiga | ❌ portal renderiza via JS |
| Playwright + select dinâmico | ❌ selects decorativos, conteúdo não muda |
| **PDF anual agregado via httpx** | ✅ **funciona** |

URL: `https://processo.stj.jus.br/docs_internet/informativos/anuais/informativo_anual_{ANO}.pdf`

- Cada PDF agrega ~38 informativos do ano (1000-1245 páginas, 17-38MB)
- Anos disponíveis: **2017 até 2023** (confirmado). 2024/2025 dão 404 —
  STJ demora ~1 ano pra consolidar.
- `obter_pdfs_anuais` valida cada ano via HEAD dinamicamente.

## Pré-filtro por keyword (economia de tokens)

Smoke real revelou densidade baixa: em 30 blocos do PDF 2023, só 1 era das
áreas-alvo (3%). Sem filtro, 1 ano = ~$40 pra ~16 julgados úteis.

`parser.bloco_e_candidato()` corta ~85% dos blocos (penal, família,
processual) ANTES do Anthropic, checando keyword das áreas-alvo
(usucapião, ITBI, alienação fiduciária, herança, inventário, REURB...).
Resultado: ~$6-8 por ano em vez de $40.

## Passo 0 — sanidade (offline, ~5s)

```powershell
cd C:\Users\mario\Documents\Noviello-Produtividade\automacao
.venv\Scripts\python.exe -m pytest tests/julgado_radar/ -q --basetemp=C:/Users/mario/AppData/Local/Temp/pytest-fresh
```

Esperado: `169 passed`. (O `--basetemp` evita o erro de lock do temp default.)

## Passo 1 — smoke sem Anthropic (~30s, $0)

```powershell
.venv\Scripts\python.exe -m samples._smoke_pdf_anual_2023
```

Valida: download do PDF anual 2023 (27MB), pypdf extrai ~1.5M chars,
particiona em ~550 blocos. Critérios passa/falha no fim.

## Passo 2 — smoke com Anthropic (30 blocos, ~$2.40, ~5min)

```powershell
.venv\Scripts\python.exe -m samples._smoke_anthropic_pdf_anual
```

Extrai 30 blocos via Opus 4.7, mostra distribuição por área + 3 exemplos
+ custo. Já rodado: 1/30 imobiliário, qualidade alta.

## Passo 3 — backfill real (CUIDADO com a janela)

```powershell
# 1 ano só (2023, mais recente disponível com --janela 4 a partir de 2026):
.venv\Scripts\python.exe -m src.julgado_radar.backfill --janela 4 --fontes stj

# Histórico completo 2017-2023 (7 anos, ~$40-55, ~1h):
.venv\Scripts\python.exe -m src.julgado_radar.backfill --janela 10 --fontes stj
```

**ATENÇÃO:** `--janela N` pega N anos a partir do ano atual. Como existem
PDFs desde 2017, uma janela grande processa MUITOS anos. Cada ano ~$6-8 e
~10min. Comece com `--janela 4` (só 2023) pra calibrar custo.

Idempotente: anos já processados (fetch_log=ok) são pulados. Interromper
com Ctrl+C preserva os anos completos; o ano em andamento reprocessa depois.
Ordem: mais recente primeiro (2023 → 2022 → ...).

## Passo 4 — conferir no DB

```powershell
.venv\Scripts\python.exe -c "from src.julgado_radar import searcher, indexer, db; from src.config import load_config; cfg = load_config(); conn = db.abrir(cfg.state_dir); print('Total:', searcher.contar(conn)); print('Por tribunal/area:', dict(indexer.contar_por_tribunal_area(conn)))"
```

Ou abrir o painel e ir em `/radar`:

```powershell
.venv\Scripts\python.exe -m src.painel
```

## Estado em 2026-05-28

- Pipeline validado end-to-end: 20 julgados no DB cobrindo as 3 áreas em
  STJ + TJ-SP. Backfill 2017 interrompido manualmente (custo).
- Próximo passo do Mario: decidir quantos anos de histórico indexar.

## Anos correntes (2024-2025): pendente

O PDF anual de 2024+ ainda não existe. Pra jurisprudência recente, opções
futuras (não implementadas):
- Aguardar STJ publicar o anual 2024 (~meados de 2025... ou seja, já devia
  existir; revalidar a URL periodicamente)
- Implementar coleta do informativo "mais recente" que o portal carrega
  como default (Playwright pega o último sem precisar selecionar)

## TJ-SP

Wave 2 (session-aware httpx + CSRF) implementada e testada com mocks, mas
não probada contra portal real. Smoke separado pendente — comando previsto:
`python -m src.julgado_radar.backfill --janela 1 --fontes tjsp --areas imobiliario`
(sem custo Anthropic — TJ-SP não usa IA, só regex na ementa).
