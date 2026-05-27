# Radar de Julgados — Manual

> Acervo local de julgados STJ + TJ-SP, indexado em SQLite FTS5, com busca
> full-text e botão "usar este" que materializa o julgado escolhido como
> `producao/julgados/sem-N/` pro `julgado_producer` consumir.

## Visão geral

```
┌────────────────────────────────────────────────────────────────────┐
│ Painel /radar (Flask)                                              │
│   busca FTS5 + filtros (área/tribunal/ano/classe)                  │
│   botão "usar este" → cria producao/julgados/sem-N/<slug>.pdf+.json│
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌────────────────────────────────────────────────────────────────────┐
│ SQLite FTS5: state/julgados_radar.db                               │
│   julgados (1 linha por acórdão)                                   │
│   julgados_fts (virtual, tese + ementa + citacao_voto + relator)   │
│   descartados (auditoria)                                          │
│   fetch_log (idempotência do backfill)                             │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌────────────────────────────────────────────────────────────────────┐
│ Backfill orquestrador                                              │
│   STJ: feeds_stj (discover + cache + pypdf) → parser (Anthropic)   │
│   TJ-SP: feeds_tjsp (cjsg POST) → parser                           │
│   indexer: upsert + dedup por (tribunal, processo_id)              │
└────────────────────────────────────────────────────────────────────┘
```

## Schema

`state/julgados_radar.db` (SQLite WAL, tokenize `unicode61 remove_diacritics 2`):

- **julgados**: tabela principal — 1 linha/acórdão, UNIQUE(tribunal, processo_id)
- **julgados_fts**: índice FTS5 sobre tese + ementa + citacao_voto + relator
- **descartados**: itens fora do escopo + razão (auditável)
- **fetch_log**: trilha de execução do backfill (idempotência)

## Comandos

### Carregar dados demo (20 julgados representativos)
```bash
.venv/Scripts/python.exe setup/seed_radar_demo.py --reset
```

### Backfill via scrapers reais (sujeito a 403 do TJ-SP em IPs novos)
```bash
.venv/Scripts/python.exe -m src.julgado_radar.backfill --janela 5 --fontes stj,tjsp
.venv/Scripts/python.exe -m src.julgado_radar.backfill --janela 2 --fontes stj
.venv/Scripts/python.exe -m src.julgado_radar.backfill --dry-run --janela 1
```

### Abrir o painel
```bash
.venv/Scripts/python.exe -m src.painel
# Acessar: http://localhost:8765/radar
```

### Busca via REPL Python
```python
from src.config import load_config
from src.julgado_radar import db, searcher

cfg = load_config()
conn = db.abrir(cfg.state_dir)
hits = searcher.buscar(conn, "ITBI", area="imobiliario", limit=10)
for j in hits:
    print(j.tribunal, j.processo_id, j.tese)
```

## Estado das fontes reais (2026-05-27)

| Fonte | Status | Observação |
|-------|--------|------------|
| **STJ Informativos** | Parser pronto, listagem moderna usa JS dinâmico | A regex do `feeds_stj.parse_listagem` casa HTML simples; o portal atual renderiza via SharePoint/JS. Para uso real: ou (a) calibrar a URL/regex contra o HTML final pós-render, ou (b) usar o feed JSON oficial se disponibilizado. |
| **TJ-SP CJSG** | Parser pronto, mas POST retorna 403 sem sessão CSRF | A consulta cjsg requer obtenção prévia de cookies da página inicial. Para uso real: estender `feeds_tjsp` com GET inicial em `/cjsg/consultaCompleta.do` para capturar `JSESSIONID` + `_csrf`. |

A infraestrutura está completa e testada (134 testes do Radar passando contra mocks).
A calibração final dos scrapers contra os portais reais é uma tarefa de campo,
não de design — basta ajustar 2-3 linhas em cada `feeds_*.py` quando o Mario
quiser executar contra produção.

## Áreas-alvo

| Área | Termos de busca TJ-SP | Cobertura informativo STJ |
|------|------------------------|----------------------------|
| `urbanistico` | regularizacao fundiaria, REURB, parcelamento do solo, loteamento irregular, outorga onerosa, operacao urbana | Itens classificados como urbanístico (RAMO DO DIREITO no informativo) |
| `imobiliario` | usucapiao, ITBI, incorporacao imobiliaria, compra e venda imovel, alienacao fiduciaria imovel, condominio edilicio | Idem |
| `sucessorio` | inventario, heranca, testamento, holding familiar, partilha de bens, doacao com reserva | Idem |

Itens que a IA classifica como `fora` vão pra `descartados` (auditável via
SQL: `SELECT * FROM descartados`).

## Como o "usar este" funciona

1. Usuário clica em **"Usar este → Julgado da Semana"** num card do `/radar`.
2. POST `/radar/usar` chama `radar_view.materializar_julgado()`:
   - calcula semana ISO de hoje (`ano`, `semana`)
   - cria `producao/julgados/sem-{semana:02d}/`
   - copia/baixa/sintetiza PDF como `<slug-processo>.pdf`
   - escreve JSON com todos os campos extraídos como `<slug-processo>.json`
   - marca o julgado no DB com `usado_em_post = "radar-sem-AAAA-SNN"`
3. Producer do Julgado da Semana (`julgado_producer.main_julgado`) detecta a
   pasta no próximo ciclo de 2min e executa o fluxo de geração de carrossel
   + card LinkedIn.

## Custos estimados (uma vez)

| Item | Volume | Custo estimado |
|------|--------|---------------|
| Download PDFs STJ (5 anos × ~24/ano = 120) | 120 PDFs | grátis |
| Parse STJ via Anthropic | 120 × ~30k tokens input × Opus 4.7 | ~$11 + ~$3 output |
| Query TJ-SP cjsg | 180 queries (5 anos × 12 meses × 3 áreas) | grátis (mas exige sessão) |
| Parse TJ-SP (ementa) | ~5400 itens × ~1k tokens | ~$8 |
| **Total** | | **~$22-25** |

Tempo de execução estimado: ~70 minutos com paralelismo (4 workers).

## Testes

```bash
# Suite completa
.venv/Scripts/python.exe -m pytest -q

# Só o Radar
.venv/Scripts/python.exe -m pytest tests/julgado_radar/ -q
```

Cobertura atual: **134 testes do Radar** + 233 baseline = 367 testes. Todos os
scrapers são testáveis offline (HTTP injetável, fixtures HTML/PDF, Anthropic
mockado).

## Arquivos

```
src/julgado_radar/
  __init__.py               # subpacote
  config.py                 # AREAS_ALVO, FONTES, rate limits, termos por área
  models.py                 # Julgado, Descartado (com to_row/from_row)
  db.py                     # schema FTS5 + triggers (idempotente)
  feeds_stj.py              # discover + download Informativos STJ
  feeds_tjsp.py             # POST cjsg + parser HTML
  parser.py                 # extrair_itens_de_informativo (pypdf + IA)
  indexer.py                # upsert/dedup/fetch_log
  searcher.py               # buscar(termo, area, tribunal, ano, classe)
  radar_view.py             # buscar_para_view + materializar_julgado
  backfill.py               # orquestrador CLI
  __main__.py               # python -m src.julgado_radar

setup/seed_radar_demo.py    # popula DB com 20 julgados reais (demo)

templates/radar.html        # UI do painel

state/julgados_radar.db     # banco (gerado em runtime)
state/julgado_radar_cache/  # PDFs do STJ baixados
```
