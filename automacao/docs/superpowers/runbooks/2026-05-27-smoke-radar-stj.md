# Runbook: Smoke real do Radar STJ (pós-calibração)

**Status:** pronto para Mario executar
**Data:** 2026-05-27
**Pré-requisitos:** `.venv` ativado, Anthropic key em `.env`, Playwright Chromium instalado

## Contexto

As waves 1 e 2 já estão commitadas (`fc2c03d` STJ, `8730181` TJ-SP). 421/421
testes passam com mocks de Playwright e `httpx.Client`. Este runbook valida
contra o portal real do STJ (rede + Anthropic), antes do backfill de 5 anos.

## Passo 0 — sanidade (offline, ~5s)

```powershell
cd C:\Users\mario\Documents\Noviello-Produtividade\automacao
.venv\Scripts\python.exe -m pytest tests/julgado_radar/ -q
```

Esperado: `132 passed`. Se falhar, parar e reportar.

## Passo 1 — Playwright Chromium instalado?

```powershell
.venv\Scripts\python.exe -m playwright install chromium
```

Se já instalado, é no-op em ~3s. Se não, baixa ~150MB (~30s).

## Passo 2 — smoke do descobrir_informativos (sem Anthropic, ~30s)

Cria `automacao/samples/_smoke_stj_descobrir.py`:

```python
"""Smoke: descobre informativos 2024 via portal real."""
from src.julgado_radar.feeds_stj import descobrir_informativos

refs = descobrir_informativos([2024])
print(f"Total descobertos para 2024: {len(refs)}")
for r in refs[:5]:
    print(f"  - inf-{r.numero:04d}: {r.titulo[:60]}")
```

```powershell
.venv\Scripts\python.exe -m automacao.samples._smoke_stj_descobrir
```

**Critérios de aceitação:**
- ≥30 informativos descobertos para 2024 (esperado: 38)
- Cada ref tem `select_id`, `option_value`, `titulo` preenchidos
- Nenhuma exceção; Chromium fecha limpo

## Passo 3 — smoke do baixar_informativo (sem Anthropic, ~10s/inf)

Cria `automacao/samples/_smoke_stj_baixar.py`:

```python
"""Smoke: baixa 1 informativo via portal real."""
from pathlib import Path
from src.julgado_radar.feeds_stj import descobrir_informativos, baixar_informativo

refs = descobrir_informativos([2024])
ref = refs[0]  # mais recente
print(f"Baixando inf-{ref.numero:04d} ({ref.titulo[:50]})")

cache = Path("state/julgado_radar_cache/stj")
arq = baixar_informativo(ref, cache)
html = arq.read_text(encoding="utf-8")
print(f"  HTML salvo em {arq} ({len(html)} chars)")
print(f"  Primeiras 300 chars: {html[:300]}")
```

**Critérios de aceitação:**
- Arquivo `state/julgado_radar_cache/stj/inf-NNNN.html` criado (>1KB)
- HTML contém referências a "PROCESSO", "REsp", "AgInt" ou similares
- Segundo run usa cache (≤1s, sem abrir Chromium)

## Passo 4 — backfill real 1 ano (com Anthropic, ~$2-4)

```powershell
.venv\Scripts\python.exe -m src.julgado_radar.backfill --janela 1 --fontes stj
```

**Critérios de aceitação:**
- ≥30 informativos baixados (38 esperados para 2024)
- ≥30 julgados em `state/julgado_radar.db` table `julgados`
- Mix de áreas: urbanístico + imobiliário + sucessório (variável; pelo
  menos 3 de cada se a janela cobriu 12 meses)
- Custo Anthropic Console: $2-4 (10-20K tokens input × ~6K saída × 38 chamadas)
- Sem stack traces; erros tolerados em até 3 informativos (parsing
  edge cases)

## Passo 5 — query de exemplo (verifica que entrou)

```powershell
.venv\Scripts\python.exe -c "
from src.julgado_radar import searcher, db
from src.config import load_config
cfg = load_config()
conn = db.abrir(cfg.state_dir)
print('Total julgados:', searcher.contar_total(conn))
print('Por area:', searcher.contar_por_area(conn))
print()
print('3 julgados urbanisticos recentes:')
for j in searcher.buscar(conn, '', area='urbanistico', limit=3):
    print(f'  - {j[\"processo_id\"]}: {j[\"tese\"][:80]}')
"
```

## Se algo falhar

1. **Portal STJ mudou layout** (select ID diferente): atualizar
   `URL_PORTAL_INFORMATIVOS` ou `ANOS_SUPORTADOS` em `feeds_stj.py`.
2. **Chromium não inicia** (headless flag rejeitada): rodar
   `playwright install chromium` de novo.
3. **HTML vazio depois do select**: aumentar `wait_for_timeout(3000)` para
   `5000` em `baixar_informativo` (AJAX lento).
4. **Anthropic rate-limit**: rodar com `--janela 1` (≤40 chamadas) ao
   invés de `--janela 5` (~200 chamadas).

## TJ-SP (não rodar ainda neste smoke)

A wave 2 só faz GET prévio + POST com CSRF — não foi probada contra portal
real. Recomendo deixar pra um smoke separado depois que o STJ estiver
estável. Comando previsto: `python -m src.julgado_radar.backfill --janela 1
--fontes tjsp --areas imobiliario` (~50 min, sem custo Anthropic — TJ-SP
não usa IA).
