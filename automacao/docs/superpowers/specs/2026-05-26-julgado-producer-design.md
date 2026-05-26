# Julgado da Semana — Producer Automatizado

**Data:** 2026-05-26
**Autor:** brainstorming session com Mario Noviello
**Status:** aprovado para implementação

## Objetivo

Estender o pipeline de automação editorial da Noviello para que o producer detecte
automaticamente o evento `[NOV-MKT] LI 08h30 — Julgado` no Google Calendar, leia o PDF
do acórdão depositado em `producao/julgados/sem-N/`, extraia os dados estruturados
(relator, processo, citação, tese, área, tribunal, carimbo, fundamentos, data,
turma, órgão completo) e gere as duas peças sociais: carrossel multi-slide para
Instagram e card single-image para LinkedIn. As duas peças passam pelo fluxo já
existente de aprovação por painel + email antes de publicar.

**Restrições críticas:**
- Retrocompatibilidade total: nenhum teste existente pode quebrar (baseline = 164 tests).
- Nenhuma alteração de comportamento dos fluxos atuais (blog Fila Social, cadência semanal).
- Os campos `area`, `selo_tribunal`, `processo_id` e `carimbo` no `slide-carrossel.html`
  já existem como opcionais (Batch (a)); o novo producer apenas os popula.

## Decisões arquitetônicas

| # | Decisão | Justificativa |
|---|---------|---------------|
| 1 | Módulo isolado `src/julgado_producer.py` chamado de `producer.main()` | Reaproveita loop, lock, heartbeat e logger sem inflar o producer (482 → ~600 LoC) e sem migração de state. |
| 2 | Parsing híbrido: `pypdf` extrai texto bruto → Anthropic estrutura em JSON | Layout de acórdão varia entre STJ/STF/TJs; IA absorve a variação. ~1 chamada Anthropic por julgado. |
| 3 | Pasta por semana ISO: `producao/julgados/sem-N/` com exatamente 1 PDF | Casamento determinístico: evento da semana ISO X consome `sem-X`. Sem ambiguidade. |
| 4 | Idempotência por `event.id` do Google Calendar | ID estável e único; sem confusão com PDF refeito ou semana renumerada. |
| 5 | Duas camadas de aprovação humana | Painel revisa extração + copy gerada; email do watcher revisa peça final renderizada. |
| 6 | Saídas: IG carrossel (multi-slide via IA) + LinkedIn card (single-image) | WP fica de fora (Mario faz blog manual). Carrossel reaproveita `slide-carrossel.html` com Batch (a). Card reaproveita `julgado-card.html`. |
| 7 | Novo `JulgadoState` + `JulgadoStore` (paralelo a `ProducaoState`/`ProducaoStore`) | State files separados em `state/julgados/`. Zero risco para state files atuais. |
| 8 | Template `julgado-card.html` ganha placeholder `{carimbo_label}` (default "Unanimidade") | Hoje está hardcoded "Unanimidade"; sem placeholder, carimbo dinâmico não funciona. Retrocompatibilidade garantida pelo default. |

## Arquitetura — visão geral

```
┌────────────────────────────────────────────────────────────────────────┐
│ producer.main() (a cada 2 min, via Agendador)                          │
│  ├── Etapa A (blog)         — WP Fila Social → painel                  │
│  ├── Etapa B (blog)         — decisão painel → MANIFEST                │
│  └── Etapa Julgado (NOVO)   — calendar → PDF → painel → MANIFEST       │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ src/julgado_producer.py (NOVO)                                         │
│                                                                        │
│  detectar_e_extrair(cfg, cal, anthropic, store, logger)                │
│    │                                                                   │
│    ├─ cal.listar_eventos_futuros("Noviello — Marketing",              │
│    │                              janela_horas=72,                     │
│    │                              filtro="[NOV-MKT] LI 08h30 — Julgado")│
│    ├─ para cada event não-store.exists(event.id):                     │
│    │     ├─ identifica semana ISO do event.start                       │
│    │     ├─ pasta = cfg.producao_dir / "julgados" / f"sem-{N:02d}"   │
│    │     ├─ pdf_extractor.extrair(pasta) → dados estruturados          │
│    │     ├─ anthropic.gerar_carrossel_julgado(dados)                   │
│    │     ├─ anthropic.gerar_linkedin_julgado(dados)                    │
│    │     ├─ JulgadoState(event_id, dados, copy) → painel               │
│    │     └─ envia ping de email "novo julgado pra revisar"             │
│    │                                                                   │
│  processar_revisao(estado, cfg, anthropic, store, logger)              │
│    │                                                                   │
│    ├─ status == AGUARDANDO_REVISAO + decisao == "aprovar":             │
│    │     ├─ render_carrossel (com area/selo/processo/carimbo)          │
│    │     ├─ render_card_li (julgado-card.html)                         │
│    │     ├─ escreve MANIFEST tipo="julgado"                            │
│    │     └─ estado → PECA_MONTADA                                      │
│    └─ status == AGUARDANDO_REVISAO + decisao == "ajustar":             │
│          └─ regenera copy com ajuste_texto                             │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ watcher → email aprovação → poller → publishers (IG + LI)              │
│ (FLUXO EXISTENTE, sem mudanças funcionais)                             │
└────────────────────────────────────────────────────────────────────────┘
```

## Módulos novos

### `src/pdf_extractor.py`

Extração híbrida pypdf + Anthropic.

```python
class PDFExtractorError(Exception): ...

def extrair_texto_pdf(pdf_path: Path) -> str:
    """Le texto bruto do PDF via pypdf. Levanta PDFExtractorError se falhar."""

def localizar_pdf_da_semana(julgados_dir: Path, semana_iso: int) -> Path:
    """Devolve o caminho do único PDF em julgados_dir / f'sem-{N:02d}'.
    Levanta PDFExtractorError se a pasta não existe, está vazia, ou tem >=2 PDFs."""

def extrair_dados_julgado(pdf_texto: str, anthropic_client) -> dict:
    """Roda 1 chamada Anthropic com structured output.
    Devolve dict com chaves: area, selo_tribunal, orgao_completo, turma,
    processo, data_julgamento, relator, relator_curto, tese,
    citacao_principal, carimbo, fundamentos (lista de {fonte, texto})."""
```

Schema Anthropic JSON (structured output):

```python
JULGADO_SCHEMA = {
    "type": "object",
    "properties": {
        "area": {"type": "string"},
        "selo_tribunal": {"type": "string"},     # "STJ", "STF", "TJ-SP", etc.
        "orgao_completo": {"type": "string"},    # "Terceira Turma do STJ"
        "turma": {"type": "string"},             # "3ª Turma · Unanimidade"
        "processo": {"type": "string"},          # "REsp 2.215.421/SE"
        "data_julgamento": {"type": "string"},   # "10/03/2026"
        "relator": {"type": "string"},           # "Min. Nancy Andrighi"
        "relator_curto": {"type": "string"},
        "tese": {"type": "string"},
        "citacao_principal": {"type": "string"},
        "carimbo": {"type": "string"},           # "Unanimidade" | "Maioria" | "Repetitivo Tema X" | ...
        "fundamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"fonte": {"type": "string"}, "texto": {"type": "string"}},
                "required": ["fonte", "texto"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["area", "selo_tribunal", "processo", "relator", "tese",
                 "citacao_principal", "carimbo", "fundamentos"],
    "additionalProperties": False,
}
```

Campos opcionais (`orgao_completo`, `turma`, `data_julgamento`, `relator_curto`) caem em
defaults vazios. Validações:
- `area`, `selo_tribunal`, `processo`, `relator`, `tese`, `citacao_principal`, `carimbo`
  obrigatórios — se a IA devolver vazios, levanta `PDFExtractorError`.
- `fundamentos` deve ter ≥1 item — se vazio, levanta `PDFExtractorError`.

### `src/julgado_state.py`

```python
class EstadoJulgado:
    DETECTADO = "detectado"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    APROVADO = "aprovado"          # intermediário entre clique do painel e renderização
    PECA_MONTADA = "peca_montada"
    ERRO = "erro"

# Transições válidas (espelha producer_state._TRANSICOES):
# DETECTADO -> AGUARDANDO_REVISAO | ERRO
# AGUARDANDO_REVISAO -> APROVADO | ERRO
# APROVADO -> PECA_MONTADA | ERRO
# ERRO -> AGUARDANDO_REVISAO | APROVADO  (permite recovery)
# PECA_MONTADA -> (terminal)

@dataclass
class JulgadoState:
    event_id: str               # chave primária (event.id do Google Calendar)
    semana_iso: int             # ex: 22
    ano_iso: int                # ex: 2026
    event_summary: str = ""
    event_start_iso: str = ""
    status: str = EstadoJulgado.DETECTADO
    pdf_path: str = ""
    dados_julgado: dict = field(default_factory=dict)
    copy_carrossel: dict = field(default_factory=dict)
    texto_linkedin: str = ""
    decisao: str = ""           # "" | "aprovar" | "ajustar"
    ajuste_texto: str = ""
    tentativas_ajuste: int = 0
    ai_tells_resumo: dict = field(default_factory=dict)
    erro_mensagem: str = ""     # detalhe do erro para o painel mostrar
    atualizado_em: str = field(default_factory=agora_iso)
    historico: list = field(default_factory=list)

class JulgadoStore:
    """state/julgados/<event_id_safe>.json. event_id pode conter chars
    inválidos pra filesystem; sanitiza substituindo por '_'."""
    def __init__(self, state_dir): ...
    def _safe_key(self, event_id) -> str: ...
    def exists(self, event_id) -> bool: ...
    def load(self, event_id) -> JulgadoState: ...
    def save(self, state) -> None: ...
    def delete(self, event_id) -> None: ...
    def list_all(self) -> list[JulgadoState]: ...
    def lock(self, event_id): ...
```

### `src/julgado_producer.py`

```python
PILAR = "Julgado da Semana"

def detectar_e_extrair(cfg, cal_client, anthropic_cli, store, logger):
    """Etapa A do Julgado — varre calendário, extrai PDFs novos."""

def processar_revisao(estado, cfg, anthropic_cli, store, logger):
    """Etapa B do Julgado — aprovar → montar peça; ajustar → regenerar copy."""

def montar_peca(estado, cfg, logger) -> Path:
    """Renderiza carrossel + card LI + escreve MANIFEST. Devolve a pasta."""

def main_julgado(cfg, gmail, anthropic_cli, cal_client, store, logger):
    """Entrypoint chamado de producer.main()."""
```

### `src/julgado_card_render.py`

Renderiza `templates/julgado-card.html` em JPG 1080×1350 via Playwright (espelha
`carousel_render.renderizar`). API:

```python
def renderizar_card(
    dados: dict,
    pasta_destino: Path,
    templates_dir: Path,
    render_script: Path,
    *,
    canal: str = "li",   # "li" | "ig" — diferencia o subtítulo da marca
) -> Path:
    """Devolve o caminho do JPG. Falha → RenderError (mesma classe de carousel_render)."""
```

Lógica de `canal`:
- `li`: subtítulo "Advocacia · Imobiliário e Sucessório" (não usa "Direito Sênior" em B2B)
- `ig`: subtítulo "Advocacia · Direito Sênior"

(Reaproveita a regra do `samples/_julgado_card_publicar.py`.)

### `src/anthropic_client.py` — métodos novos

```python
def extrair_dados_julgado(self, pdf_texto: str) -> dict:
    """Structured output via JULGADO_SCHEMA. 1 chamada, cache no system block."""

def gerar_carrossel_julgado(
    self, dados: dict, *, ajuste: str = "",
    system_extra: str = "", contexto_blog: str = "",
) -> dict:
    """Igual ao gerar_carrossel atual, mas:
    - entrada é dict estruturado (não artigo bruto),
    - cada slide retorna com area/selo_tribunal/processo_id/carimbo preenchidos,
    - schema do carrossel ganha esses 4 campos opcionais (todos com default '')."""

def gerar_linkedin_julgado(
    self, dados: dict, url_blog: str = "", *, ajuste: str = "",
    system_extra: str = "", contexto_blog: str = "",
) -> str:
    """Post LinkedIn técnico (B2B). url_blog é opcional — só inclui se Mario
    já tiver publicado o blog. Default: sem link (Mario publica manual depois)."""
```

Schema do carrossel estendido (compatível com o atual):

```python
CAROUSEL_SCHEMA_JULGADO = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "corpo": {"type": "string"},
                    "area": {"type": "string"},
                    "selo_tribunal": {"type": "string"},
                    "processo_id": {"type": "string"},
                    "carimbo": {"type": "string"},
                },
                "required": ["titulo", "corpo"],
                "additionalProperties": False,
            },
        },
        "legenda": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slides", "legenda", "hashtags"],
    "additionalProperties": False,
}
```

## Mudanças cirúrgicas em código existente

### `templates/julgado-card.html`

Substituir o hardcoded `Unanimidade` por placeholder:

```html
<!-- antes -->
<div class="carimbo-unanime"><span class="bullet">●</span> Unanimidade</div>

<!-- depois -->
<div class="carimbo-unanime"><span class="bullet">●</span> {carimbo_label}</div>
```

`julgado_card_render.renderizar_card` injeta `{carimbo_label}` com fallback "Unanimidade"
quando `dados.get("carimbo")` é vazio. O `samples/_julgado_card_publicar.py` ganha
um patch mínimo (1 linha) para passar `carimbo_label`. Existing visual output não muda
porque o default é o texto antigo.

### `src/producer.py`

Adicionar uma única chamada após o loop de Etapa A:

```python
# ETAPA Julgado — detectar evento + extrair PDF
if cfg.julgado_ativo:
    from src.julgado_producer import main_julgado
    from src.calendar_client import CalendarClient
    try:
        cal_client = CalendarClient(cfg.google)
        julgado_store = JulgadoStore(cfg.state_dir)
        main_julgado(cfg, gmail, anthropic_cli, cal_client, julgado_store, logger)
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, "julgado", "etapa_julgado", "erro_inesperado", erro=str(exc))
```

Isto não afeta o fluxo blog porque é um bloco try/except isolado executado depois.

### `src/config.py`

Novos campos no `Config` (todos com defaults seguros):

```python
julgado_ativo: bool = True
julgado_calendario: str = "Noviello — Marketing"
julgado_filtro_titulo: str = "[NOV-MKT] LI 08h30 — Julgado"
julgado_janela_horas: int = 72  # tempo pra Mario depositar PDF e aprovar
julgado_dir: Path | None = None  # defaults para cfg.producao_dir / "julgados"
```

Carregados via env vars correspondentes (`JULGADO_ATIVO`, `JULGADO_CALENDARIO`, etc).
`julgado_dir` é derivado em `load_config()` se a env var não estiver setada.

### `src/painel.py`

`listar_pendencias` ganha terceira chave `"julgado"`. Template `painel.html` ganha seção
nova "Julgado da Semana" listando itens com:
- título = `dados_julgado.tese`
- mostrar dados extraídos (relator, processo, área, carimbo) para Mario validar a extração
- mostrar copy gerada (slides do carrossel + texto LinkedIn)
- botões Aprovar / Ajustar (idem ao fluxo de copy do blog)

`registrar_decisao` aceita `tipo == "julgado"` e usa `JulgadoStore`.

Rota `/arte` já funciona para qualquer peça (independe do tipo) — sem mudança.

### `src/manifest.py` e `MANIFEST` schema

Manifest do julgado fica com a mesma estrutura que o do blog, adicionando `tipo: "julgado"`
no top-level e nada mais — o `watcher`, `poller` e `publishers` não precisam mudar.

```json
{
  "peca_id": "julgado-2026-S22-resp-2215421",
  "tipo": "julgado",
  "pilar": "Julgado da Semana",
  "titulo_curto": "Recibo basta como justo título — STJ",
  "data_publicacao_alvo": "2026-05-28T08:30:00-03:00",
  "status": "pronta_para_aprovacao",
  "validacoes": {"oab_205": "aprovado", "marca": "v2-conforme", "ortografia": "ok"},
  "ativos": {
    "instagram": {
      "imagens": ["slide01.jpg", ..., "slide08.jpg"],
      "legenda": "legenda.txt",
      "hashtags": [...],
      "tipo_post": "carrossel"
    },
    "linkedin": {
      "imagem": "card-li.jpg",
      "texto": "linkedin.txt"
    }
  },
  "cross_link": {"ig_para_wp": false, "li_para_wp": false, "linktree_topo": false}
}
```

`peca_id` formato: `julgado-{ano}-S{semana:02d}-{processo_slug}`.

`processo_slug` derivado de `dados["processo"]` via:
```python
import re
slug = re.sub(r"[^a-z0-9]+", "-", processo.lower()).strip("-")
# "REsp 2.215.421/SE" -> "resp-2-215-421-se"
```

Sem chave `wordpress` no `ativos` — comprovado em `publishers/__init__.py:25-27`:
`publicar_canal` devolve `pulado` quando `peca.ativos(canal)` é vazio, e `publicar_todos`
itera apenas `peca.canais_no_manifest()`. Portanto MANIFEST sem `wordpress` simplesmente
não dispara o publisher WP. Sem blindagem extra necessária.

## Fluxo de dados (sequência completa)

1. **t=0**: Mario deposita `acordao.pdf` em `producao/julgados/sem-22/`.
2. **t=0..72h antes do event start**: producer rodando a cada 2 min:
   - `cal.listar_eventos_futuros("Noviello — Marketing", 72, "[NOV-MKT] LI 08h30 — Julgado")`
   - Para o primeiro evento cujo `event.id` não existe no `JulgadoStore`:
     - identifica semana ISO do `event.start`
     - `pdf_path = localizar_pdf_da_semana(julgado_dir, semana)`
     - `pdf_texto = extrair_texto_pdf(pdf_path)`
     - `dados = anthropic.extrair_dados_julgado(pdf_texto)`
     - `copy_carrossel = anthropic.gerar_carrossel_julgado(dados)`
     - `texto_linkedin = anthropic.gerar_linkedin_julgado(dados)`
     - `JulgadoStore.save(estado)` com `status=AGUARDANDO_REVISAO`
     - ping de email para Mario
3. **Mario abre o painel**: vê seção "Julgado da Semana", revisa extração + copy.
   - Clica Aprovar → `decisao="aprovar"` salvo no JSON.
4. **Próxima rodada do producer**:
   - `processar_revisao` carrega estado com `decisao="aprovar"`:
     - renderiza N slides do carrossel (via `carousel_render.renderizar`, passando
       `slides` que já trazem `area/selo_tribunal/processo_id/carimbo`)
     - renderiza o card LinkedIn (`julgado_card_render.renderizar_card`)
     - escreve `MANIFEST.json`
     - `status=PECA_MONTADA`
5. **Watcher detecta MANIFEST**: envia email para Mario com os ativos.
6. **Mario aprova via Gmail label**: poller publica em IG + LinkedIn.

## Tratamento de erros

| Cenário | Comportamento |
|---------|---------------|
| Pasta `sem-N` não existe | log info `aguardando_pdf`, sem alerta. Tenta de novo na próxima rodada. |
| Pasta vazia (sem PDF) | idem |
| Pasta com ≥2 PDFs | `status=ERRO`, `erro_mensagem` específico, log warn, painel mostra erro. Mario remove o extra. |
| pypdf falha (PDF corrompido) | `status=ERRO`, `erro_mensagem`, painel mostra erro, ping de email. |
| Anthropic falha (timeout/quota) | `status=ERRO` + retry automático na próxima rodada (não persiste o estado erro se for 5xx — só loga). |
| Anthropic retorna campo obrigatório vazio | `status=ERRO`, `erro_mensagem` lista qual campo faltou. |
| Mario clica Ajustar com texto | `_regenerar_copy` re-chama `gerar_carrossel_julgado(dados, ajuste=texto)`. Limite 3 tentativas (já tem padrão no blog). |
| Janela passa do evento sem aprovação | comportamento atual: estado fica `AGUARDANDO_REVISAO` indefinidamente. Aceitável para v1; alerta vem do watcher de followup se Mario seguir o fluxo. |

## Testes

### Testes novos (alvo: +30-40 testes)

**`tests/test_pdf_extractor.py`**
- `test_localizar_pdf_pasta_inexistente_falha`
- `test_localizar_pdf_pasta_vazia_falha`
- `test_localizar_pdf_multiplos_pdfs_falha`
- `test_localizar_pdf_unico_pdf_devolve`
- `test_extrair_texto_pdf_smoke` (PDF de teste pequeno em `tests/fixtures/`)
- `test_extrair_dados_julgado_com_mock_anthropic` (mock do client)
- `test_extrair_dados_julgado_campos_obrigatorios_vazios_falha`
- `test_extrair_dados_julgado_fundamentos_vazios_falha`

**`tests/test_julgado_state.py`**
- `test_store_crud`
- `test_event_id_sanitizado_no_path` (event IDs do Google podem ter chars como `_`, `@`)
- `test_transicao_valida`
- `test_transicao_invalida`
- `test_decisao_persiste`
- `test_lock_exclusivo`
- `test_list_all_ignora_arquivos_invalidos`

**`tests/test_julgado_producer.py`**
- `test_pasta_da_semana_iso_correta` (event start de 26/05/2026 → sem-22)
- `test_idempotencia_por_event_id`
- `test_detectar_sem_eventos_no_op`
- `test_detectar_evento_sem_pdf_grava_erro`
- `test_pipeline_completo_com_mocks` (calendar + anthropic mockados → estado AGUARDANDO_REVISAO)
- `test_processar_revisao_aprovar_monta_peca`
- `test_processar_revisao_ajustar_regenera`
- `test_montar_peca_escreve_manifest_correto`
- `test_montar_peca_renderiza_carrossel_com_meta_campos`
- `test_montar_peca_renderiza_card_li`
- `test_peca_id_formato`

**`tests/test_julgado_card_render.py`**
- `test_renderizar_card_li_subtitulo_correto`
- `test_renderizar_card_ig_subtitulo_correto`
- `test_carimbo_default_unanimidade`
- `test_carimbo_dinamico_maioria`
- `test_escape_html_em_campos`

**`tests/test_anthropic_client_julgado.py`** (gated por API key, normalmente skipped)
- smoke test apenas — não bloqueante no CI local.

### Retrocompatibilidade — testes existentes

Todos os 164 testes atuais devem continuar passando sem mudança. Verificação dirigida:
- `test_carousel_render.py` (10 testes): inclui Batch (a), valida que slide sem campos novos não renderiza meta nem carimbo. Os novos slides do Julgado **vão** renderizar — mas o teste não muda.
- `test_producer.py` (5 testes): só toca `_texto_limpo`, `ProducaoState`, `ProducaoStore`. Não afetado.
- `test_pipeline_e2e.py`: usa MANIFEST do blog. Não afetado.
- `test_painel.py`: ganha 1-2 testes novos para a nova seção (esses contam como testes novos), mas os existentes não mudam.

Meta final: **≥194 testes passando** (164 baseline + ~30 novos).

## Dependências novas

- `pypdf` — adicionar a `requirements.txt`. SDK puro Python, sem libs nativas. Bem
  estabelecido, sem CVEs ativas relevantes para nosso uso (leitura local).

Nenhuma outra dependência. Anthropic SDK e Playwright já estão instalados.

## Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Extração Anthropic retorna dados incorretos (alucina relator, processo) | Painel obriga revisão humana — Mario valida antes de virar peça. |
| PDF de tribunal pouco comum não estrutura bem | Painel mostra erro detalhado; Mario pode complementar manualmente em `samples/_julgado_card_publicar.py` (escape hatch atual continua funcionando). |
| Carimbo dinâmico quebra layout do card | Template `julgado-card.html` tem `padding 6px 14px` no carimbo — testar com texto longo "Repetitivo Tema 1234"; ajustar `max-width` se necessário. Audit visual em sample antes de publicar. |
| Conflito com event_id que mude (Google às vezes recria) | Default: aceita re-extração — gera nova peça. Risco baixo: event_id de eventos do mesmo calendário é estável. |
| Race condition: producer chamado 2× simultâneo | `JulgadoStore.lock` via `_file_lock` (mesmo padrão do blog). |
| Anthropic quota/billing | Cada Julgado ≈ 3 chamadas (extração + carrossel + linkedin). Cadência semanal = 12/ano. Custo desprezível. |

## Plano de implementação (alta granularidade)

Detalhes vão para `writing-plans`. Visão por waves:

- **Wave 1 — base**: `pdf_extractor.py`, `julgado_state.py`, testes unitários (sem rede).
- **Wave 2 — extração IA**: novos métodos do `anthropic_client.py`, testes com mock.
- **Wave 3 — render**: `julgado_card_render.py`, template patch, testes.
- **Wave 4 — producer**: `julgado_producer.py` (detectar + processar_revisao + montar_peca), testes.
- **Wave 5 — integração**: hook no `producer.main()`, novos campos em `config.py`, seção no painel.
- **Wave 6 — verificação E2E**: roda manualmente com PDF real, valida 164+ testes passam.

Cada wave commita atomicamente; commit final faz `pytest` rodar full suite verde.

## Definição de pronto

- [ ] `pytest` rodando localmente reporta **≥194 testes** com 0 falhas.
- [ ] Producer detecta evento `[NOV-MKT] LI 08h30 — Julgado` no Google Calendar.
- [ ] Lê PDF de `producao/julgados/sem-N/` e extrai relator, processo, citação, tese
  (mais área, selo_tribunal, carimbo, fundamentos, data, turma).
- [ ] Os 4 campos `area`/`selo_tribunal`/`processo_id`/`carimbo` aparecem renderizados
  no JPG dos slides do carrossel IG (validar inspecionando 1 slide gerado).
- [ ] O JPG do card LinkedIn (`julgado-card.html`) renderiza com `carimbo` dinâmico.
- [ ] MANIFEST do julgado é consumido pelo watcher existente sem modificação no watcher/poller.
- [ ] Painel mostra a peça pendente e Mario consegue aprovar/ajustar.
- [ ] Todos os caminhos do fluxo blog atual continuam funcionando (zero regressão).
- [ ] Sample manual `_julgado_card_publicar.py` continua executável (regressão visual).
