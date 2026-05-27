# Radar de Julgados — Backfill 5 anos (STJ + TJ-SP)

**Data:** 2026-05-26
**Autor:** brainstorming session com Mario Noviello
**Status:** aprovado para implementação autônoma

## Objetivo

Construir um **acervo local de julgados** (STJ Informativos + TJ-SP pesquisa
jurisprudencial) cobrindo **2021-2026** (5 anos), filtrado nas áreas editoriais
da Noviello (**Urbanístico, Imobiliário, Sucessões**). Esse acervo alimenta o
slot semanal `[NOV-MKT] LI 08h30 — Julgado` do calendário sem Mario precisar
pesquisar julgado novo a cada semana.

O acervo é exposto via uma tela nova no painel (`/radar`) com busca full-text,
filtros (área, tribunal, ano, classe) e botão **"usar este → Julgado da Semana"**
que dispara o producer existente (commits Wave 1-5 de 2026-05-26) com o PDF/dados
já preparados.

## Decisões arquitetônicas

| # | Decisão | Justificativa |
|---|---------|---------------|
| 1 | **SQLite com FTS5** em `state/julgados_radar.db` | Single-file, zero infra, busca full-text nativa, suporta dezenas de milhares de registros sem latência. |
| 2 | **Módulo isolado** `src/julgado_radar/` (subpacote) | 1 arquivo por fonte (feeds_stj.py, feeds_tjsp.py) + indexer + searcher. Não toca código existente. |
| 3 | **Backfill como script standalone** rodável manual | `python -m src.julgado_radar.backfill --janela 5 --fontes stj,tjsp`. Não vira tarefa agendada — rodada única histórica. |
| 4 | **Rotina quinzenal** vem em milestone separado | Depois do backfill ok, agente cria `Noviello-Radar-Update` que roda 1×/semana puxando só novos. |
| 5 | **Filtro por área no parse**, não na indexação | Anthropic classifica cada item nas 3 áreas-alvo; itens fora vão pra tabela `descartados` (auditável, sem perder). |
| 6 | **STJ Informativos como fonte primária** | Curados oficialmente, PDF estruturado, alto sinal/ruído. |
| 7 | **TJ-SP via API ESAJ `cjsg`** | Pesquisa de jurisprudência aberta. Filtra por classe processual + matéria. Top 30/mês por área. Salva ementa + relator + processo (sem inteiro teor, economiza Anthropic). |
| 8 | **Dedup por (tribunal, processo_id)** | Mesmo acórdão pode aparecer em fontes diferentes (informativo STJ + comentado por Migalhas futuramente). |
| 9 | **Painel `/radar` reaproveita Flask existente** | Nova rota no `src/painel.py`, novo template `templates/radar.html`. Sem novo servidor. |
| 10 | **Rate-limits respeitados** | STJ: 1 req/seg. TJ-SP: 1 req/3seg (mais conservador). Cache de 24h em disco pra evitar refetch. |

## Schema SQLite (FTS5)

```sql
-- Tabela principal de julgados (1 linha por acórdão)
CREATE TABLE julgados (
    id INTEGER PRIMARY KEY,
    tribunal TEXT NOT NULL,          -- 'STJ' | 'TJ-SP'
    processo_id TEXT NOT NULL,       -- 'REsp 2.215.421/SE', 'Apel 1234567-89.2020...'
    relator TEXT,
    orgao TEXT,                      -- '3ª Turma', '6ª Câmara de Direito Privado'
    data_julgamento TEXT,            -- ISO date
    data_publicacao TEXT,            -- ISO date
    area TEXT NOT NULL,              -- 'urbanistico' | 'imobiliario' | 'sucessorio'
    classe TEXT,                     -- 'Recurso Especial' | 'Apelação Cível' | ...
    tese TEXT NOT NULL,              -- 1-2 frases, núcleo da decisão
    ementa TEXT,                     -- texto completo da ementa
    citacao_voto TEXT,               -- 1 trecho marcante do voto vencedor
    fundamentos_json TEXT,           -- JSON: [{fonte, texto}]
    url_fonte TEXT,                  -- URL original do acórdão/informativo
    pdf_local TEXT,                  -- caminho local do PDF se baixado
    info_origem TEXT,                -- ex: 'informativo-789-stj' ou 'cjsg-2024-08'
    score_relevancia INTEGER DEFAULT 50,  -- 0-100, scoring futuro
    usado_em_post TEXT,              -- URN do post LI ou ID do MANIFEST se usado
    indexado_em TEXT NOT NULL,       -- ISO timestamp do parse
    UNIQUE(tribunal, processo_id)
);

-- Full-text search (FTS5) — indexa tese + ementa + citacao_voto
CREATE VIRTUAL TABLE julgados_fts USING fts5(
    tese, ementa, citacao_voto,
    content='julgados', content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers pra manter FTS sincronizado
CREATE TRIGGER julgados_ai AFTER INSERT ON julgados BEGIN
    INSERT INTO julgados_fts(rowid, tese, ementa, citacao_voto)
    VALUES (new.id, new.tese, new.ementa, new.citacao_voto);
END;
CREATE TRIGGER julgados_au AFTER UPDATE ON julgados BEGIN
    INSERT INTO julgados_fts(julgados_fts, rowid, tese, ementa, citacao_voto)
    VALUES('delete', old.id, old.tese, old.ementa, old.citacao_voto);
    INSERT INTO julgados_fts(rowid, tese, ementa, citacao_voto)
    VALUES (new.id, new.tese, new.ementa, new.citacao_voto);
END;
CREATE TRIGGER julgados_ad AFTER DELETE ON julgados BEGIN
    INSERT INTO julgados_fts(julgados_fts, rowid, tese, ementa, citacao_voto)
    VALUES('delete', old.id, old.tese, old.ementa, old.citacao_voto);
END;

-- Auditoria de itens descartados (fora das 3 áreas-alvo)
CREATE TABLE descartados (
    id INTEGER PRIMARY KEY,
    tribunal TEXT,
    processo_id TEXT,
    motivo TEXT,                     -- 'area_fora_escopo' | 'sem_tese_extraida' | 'duplicata'
    payload_json TEXT,
    descartado_em TEXT
);

-- Tracking do backfill (idempotência)
CREATE TABLE fetch_log (
    id INTEGER PRIMARY KEY,
    fonte TEXT NOT NULL,             -- 'stj-informativo-789' | 'tjsp-cjsg-2024-08-imobiliario'
    fetched_em TEXT NOT NULL,
    status TEXT,                     -- 'ok' | 'erro' | 'parcial'
    itens_inseridos INTEGER DEFAULT 0,
    erro TEXT,
    UNIQUE(fonte)
);
```

## Estrutura de módulos

```
src/julgado_radar/
  __init__.py
  config.py                    # AREAS_ALVO, JANELA_ANOS, RATE_LIMITS
  db.py                        # conexão + schema + migrations
  models.py                    # dataclasses Julgado, Descartado
  feeds_stj.py                 # discover URLs + download + parse Informativos STJ
  feeds_tjsp.py                # query API cjsg + parse pesquisa
  parser.py                    # extração via pypdf + Anthropic (reusa AnthropicClient)
  indexer.py                   # insert/dedup/update FTS
  searcher.py                  # API de busca (full-text + filtros)
  backfill.py                  # main entrypoint do backfill histórico
  __main__.py                  # `python -m src.julgado_radar`

tests/julgado_radar/
  test_config.py
  test_db.py                   # schema + triggers + FTS round-trip
  test_feeds_stj.py            # mock URLs, parse de PDF de exemplo
  test_feeds_tjsp.py           # mock API response
  test_parser.py               # estrutura JSON saída
  test_indexer.py              # dedup, atualização, descartados
  test_searcher.py             # full-text + filtros combinados
  test_backfill_smoke.py       # mock 2 informativos + 5 TJSP, verifica DB final

templates/
  radar.html                   # nova tela com busca + filtros + cards

state/
  julgados_radar.db            # SQLite local
  julgado_radar_cache/         # PDFs baixados (HTTP cache)
```

## Anthropic — schemas de extração

**Schema STJ Informativo** (1 chamada por item do informativo):

```python
STJ_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "relevante": {"type": "boolean"},  # casa com áreas-alvo?
        "area": {"type": "string", "enum": ["urbanistico", "imobiliario", "sucessorio", "fora"]},
        "processo_id": {"type": "string"},
        "relator": {"type": "string"},
        "orgao": {"type": "string"},
        "data_julgamento": {"type": "string"},
        "tese": {"type": "string", "maxLength": 280},
        "ementa": {"type": "string"},
        "citacao_voto": {"type": "string"},
        "fundamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fonte": {"type": "string"},
                    "texto": {"type": "string"}
                }
            }
        }
    },
    "required": ["relevante", "area", "processo_id", "tese"]
}
```

**Schema TJ-SP acórdão** (a partir da ementa + metadata da pesquisa):
- Mesma estrutura, mas `ementa` é o input principal (sem PDF de inteiro teor).

## Plano em 7 waves

### Wave 0 — Schema + módulo base (~1h)
- [ ] Criar `src/julgado_radar/` com `__init__.py`, `config.py`, `models.py`, `db.py`
- [ ] Implementar schema SQLite + migrations idempotentes
- [ ] Testes: `test_db.py` (schema, triggers, FTS round-trip)
- [ ] Commit: "Radar Wave 0: schema SQLite + módulo base"

### Wave 1 — STJ Informativos: discover + download (~1h)
- [ ] `feeds_stj.py`: descobrir URLs dos informativos 2021-2026 via portal
  oficial `stj.jus.br/sites/portalp/Paginas/Servicos/Informativo-de-Jurisprudencia.aspx`
- [ ] Downloader paralelo (4 workers) com retry + rate-limit 1 req/seg
- [ ] Cache em disco: `state/julgado_radar_cache/stj/inf-NNN.pdf`
- [ ] Testes: mock HTTP, verifica retry e respeito de rate-limit
- [ ] Smoke: baixar 3 informativos reais e confirmar PDFs válidos

### Wave 2 — STJ Parser (~1.5h)
- [ ] `parser.py`: `extrair_itens_de_informativo(pdf_path) -> list[dict]`
  - pypdf extrai texto bruto
  - Anthropic divide em itens (cada informativo tem N julgados destacados)
  - Para cada item, classifica área + extrai campos estruturados
- [ ] Itens com `area == "fora"` vão pra `descartados`
- [ ] Testes: parse de 2 informativos reais conhecidos (validar nº de itens + áreas)
- [ ] Commit: "Radar Wave 1+2: STJ informativos completo"

### Wave 3 — TJ-SP scraper (~1.5h)
- [ ] `feeds_tjsp.py`: query API `cjsg`
  - URL: `https://esaj.tjsp.jus.br/cjsg/resultadoCompleta.do`
  - Filtros: classe = (Apelação Cível, Agravo de Instrumento) × matéria
  - Períodos: 12 queries/ano × 5 anos = 60 períodos × 3 áreas = 180 queries
  - Top 30/mês por área (limita volume)
  - Rate-limit: 1 req/3seg (TJ-SP é mais sensível que STJ)
- [ ] Parser: lê HTML da listagem + extrai ementa + relator + processo + classe + data
- [ ] Salva PDF do inteiro teor APENAS quando Mario marcar "usar este" (sob demanda)
- [ ] Testes: mock response HTML
- [ ] Commit: "Radar Wave 3: TJ-SP cjsg scraper"

### Wave 4 — Indexer + Dedup (~0.5h)
- [ ] `indexer.py`: insere com `INSERT OR IGNORE`, atualiza FTS via trigger
- [ ] Dedup por `(tribunal, processo_id)`
- [ ] Quando dedup detecta: mantém o mais novo, registra no `fetch_log`
- [ ] Testes: 2 inserções mesma chave → 1 linha; FTS retorna corretamente

### Wave 5 — Searcher (~0.5h)
- [ ] `searcher.py::buscar(termo, area=None, tribunal=None, ano=None, classe=None, limit=20)`
- [ ] Combina FTS5 MATCH com WHERE simples
- [ ] Score: BM25 nativo do FTS5 + boost se area==filtro
- [ ] Testes: cenários (busca "ITBI" área imobiliario, busca processo exato, etc)

### Wave 6 — Painel `/radar` (~1h)
- [ ] Nova rota em `src/painel.py`: `@app.get("/radar")` e `@app.post("/radar/usar")`
- [ ] Template `templates/radar.html`: form de busca, filtros, lista de cards
- [ ] Botão "usar este" cria pasta `producao/julgados/sem-N/` com PDF baixado + JSON
  do julgado, e cria `JulgadoState` pré-preenchido (paraleliza fluxo do producer Wave 5)
- [ ] Testes: rota responde, busca devolve resultados, "usar este" cria state

### Wave 7 — Backfill end-to-end + testes finais (~0.5h)
- [ ] `backfill.py`: orquestra Waves 1-3 + 4-5 numa execução
  - `python -m src.julgado_radar.backfill --janela 5 --fontes stj,tjsp`
  - Progresso em log estruturado
  - Idempotência: `fetch_log` evita refetch
- [ ] Smoke test ponta-a-ponta com 5 informativos STJ + 30 acórdãos TJ-SP
- [ ] README em `docs/radar-julgados.md`

## Custos estimados (uma vez só)

| Item | Volume | Custo |
|------|--------|-------|
| Download PDFs STJ (5 anos × 24/ano = 120) | 120 PDFs × ~2MB | grátis |
| Parse STJ via Anthropic | 120 × ~30k input tokens × claude-opus-4-7 | ~$11 input + ~$3 output |
| Query TJ-SP cjsg | 180 queries × HTTP | grátis |
| Parse TJ-SP (ementa só, ~1k tokens) | 30/mês × 60 meses × 3 áreas = 5400 itens × ~1k tokens | ~$8 |
| **Total** | | **~$22-25** |

Tempo de execução estimado (sequencial): ~3h. Com paralelismo (4 workers em downloads/parses): ~70 min.

## Critérios de aceitação

1. ✅ Comando `python -m src.julgado_radar.backfill --janela 5 --fontes stj,tjsp` roda
   sem erros até o fim, idempotente (re-rodar não duplica).
2. ✅ `state/julgados_radar.db` populado com:
   - **STJ**: ≥600 julgados nas 3 áreas-alvo (estimativa: ~50% de 1200 itens brutos)
   - **TJ-SP**: ~5400 acórdãos indexados (top 30/mês × 60 meses × 3 áreas)
3. ✅ Painel `/radar` retorna resultados em <500ms pra query "ITBI" ou "usucapião"
4. ✅ Botão "usar este → Julgado da Semana" cria state válido + pasta `producao/julgados/sem-N/`
5. ✅ **Todos os testes passando** (baseline 233 + ~70 novos = ≥300 tests)
6. ✅ Retrocompatibilidade total: nenhum teste existente quebra
7. ✅ Spec + README + 7 commits granulares no master

## Pontos de atenção

### Termos de uso e legalidade
- **STJ Informativos**: portal oficial público, livre uso (CF art. 5º, LX)
- **TJ-SP cjsg**: pesquisa pública via interface aberta. **Atenção**: nada de mascarar User-Agent, respeitar `robots.txt`, rate-limit conservador. Se em algum momento receber 429/403, parar e abrir issue.
- **Dados pessoais**: ementas/acórdãos públicos OK; **não** indexar nomes de partes em campos searchable (LGPD art. 7º X — exercício regular de direitos em processo público — autoriza, mas nosso uso editorial deve focar em tese, não em pessoas).
- **Direitos autorais**: ementa é parte do julgado (informação pública). Comentários jornalísticos de terceiros (ConJur, Migalhas) ficam de fora desta wave.

### Risco técnico
- **HTML do cjsg pode mudar**: testes devem usar fixtures de HTML, não hits ao vivo
- **PDFs do STJ variam em formato**: alguns informativos antigos (pré-2022) podem ter encoding ruim. Solução: pypdf fallback pra OCR via `pytesseract` se texto extraído for vazio
- **Anthropic rate-limit**: 4 workers paralelos = 4 calls/seg. Tier atual aguenta. Se hit limit, exponential backoff via tenacity (já usado no projeto)

### Encerramento
- **Não** modificar `julgado_producer.py`, `julgado_card_render.py`, `painel.py` (lógica existente) nesta entrega. Apenas **adicionar** rotas e módulos.
- **Não** ativar tarefa agendada de update incremental — isso vira milestone separado depois.
- **Sim** commitar SPEC + PLAN + 7 commits implementação granulares.

## Goal final (para `/goal` no Claude Code)

```
acervo de julgados STJ Informativos 2021-2026 e TJ-SP pesquisa cjsg 2021-2026
(áreas urbanístico, imobiliário, sucessório) indexado em state/julgados_radar.db
via SQLite FTS5; painel /radar com busca full-text e filtros; botão "usar este"
cria producao/julgados/sem-N/ pronto pro producer existente consumir;
backfill.py rodável; >=300 testes passando; retrocompatibilidade total
(233 testes baseline sem regressão); 7 commits granulares Wave 0-7.
```

## Prompt inicial sugerido

```
Implementa este radar. Segue o plano em 7 waves. TDD: testes primeiro pra cada
módulo. Commit ao final de cada wave. Não toca código existente do
julgado_producer/painel além de adicionar rota /radar. Quando terminar, roda o
backfill com --janela 5 --fontes stj,tjsp E me mostra: (a) total de julgados
inseridos por tribunal/área, (b) tempo total, (c) custo aproximado, (d)
3 exemplos de query no painel ("ITBI", "usucapião extrajudicial", "holding familiar").
```
