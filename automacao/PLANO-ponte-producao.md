# Plano de Implementação — Ponte de Produção

> Base: `ESPEC-ponte-producao.md`. Execução inline autônoma, sem Git.
> Testes: `pytest` na lógica pura; clientes de API com testes de fumaça.

**Goal:** Construir o produtor que transforma um artigo do plugin "Gerador IA Pro"
numa peça multicanal pronta (artigo estilizado + carrossel + post LinkedIn) e a
entrega como MANIFEST ao pipeline de aprovação.

**Architecture:** 3ª tarefa agendada (`producer.py`) que estende o pipeline existente,
reusando Gmail client, state, config, labels e `render-slide.py`. Gera copy via API
Anthropic; revisão da copy por email+label antes de montar a peça.

**Tech Stack:** Python 3.14, httpx (Anthropic + WP REST), Playwright (render), tenacity,
structlog, pytest.

---

## Fase 0 — Config, labels, dependências

### Task 0.1: Estender `config.py`
- Adicionar ao `Config`: `anthropic` (api_key, model), `wp_categoria_fila_social`.
- Ler `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (default `claude-sonnet-4-5`),
  `WP_CATEGORIA_FILA_SOCIAL` (default `Fila Social`).
- Método `anthropic_pronto()`.
- Teste: `tests/test_config.py` — novos campos carregam.

### Task 0.2: Labels de produção em `labels.py`
- Constantes: `PROD_PARENT="Noviello-Producao"`, `PROD_REVISAR`, `PROD_COPY_OK`,
  `PROD_COPY_AJUSTAR`, `PROD_ERRO`. Lista `PRODUCAO_TODAS`.
- Teste: `tests/test_labels.py` — 5 labels, prefixo correto.

### Task 0.3: `setup/setup_labels_producao.py`
- Cria as labels `Noviello-Producao/*` (idempotente); grava no mesmo `labels.json`
  (merge com as existentes).
- Instalar Playwright: `pip install playwright` + `playwright install chromium`.

## Fase 1 — Leitura da fonte (WordPress)

### Task 1.1: `src/wp_source.py`
- `WordPressSource(wp_cfg)`: resolve o ID da categoria "Fila Social" pelo nome;
  `listar_fila_social()` → lista de artigos (id, title, slug, content.raw,
  categorias, status) via `GET /wp/v2/posts?categories=ID&context=edit`.
- Reusa o padrão de auth Basic do `wp_client.py`.
- Teste de fumaça gated por credencial WP.

## Fase 2 — Estilização do artigo

### Task 2.1: `templates/artigo-noviello.html`
- Template-mestre extraído do post 11723: `<!-- wp:html -->` + `<style>` da marca
  (paleta, Cinzel/Poppins) + `<div class="noviello-artigo">{conteudo}</div>`.

### Task 2.2: `src/article_styler.py`
- `estilizar(html_cru: str, titulo: str) -> str`: injeta o HTML do plugin no
  template; adiciona `class="noviello-tabela"` às tabelas.
- Teste: `tests/test_article_styler.py` — saída contém o wrapper, o `<style>`,
  o conteúdo original, e tabelas com a classe.

## Fase 3 — Geração de copy (API Anthropic)

### Task 3.1: `src/anthropic_client.py`
- `AnthropicClient(anthropic_cfg)`: chama `POST https://api.anthropic.com/v1/messages`
  (header `x-api-key`, `anthropic-version`). Retry `tenacity`.
- `gerar_carrossel(artigo_texto, peca_meta) -> list[dict]` — slides com
  `titulo`/`corpo`, via prompt estruturado pedindo JSON.
- `gerar_linkedin(artigo_texto, url_artigo) -> str`.
- Prompt de sistema = brief da marca Noviello + regras OAB 205/2021
  (`templates/brief-marca.txt`).
- Teste: parsing da resposta JSON em `list[dict]`; cliente real com teste de fumaça.

### Task 3.2: `templates/brief-marca.txt`
- Brief condensado: tom de voz, pilares, terminologia Sênior, proibições OAB,
  estrutura de carrossel (hook → desenvolvimento → CTA).

## Fase 4 — Renderização do carrossel

### Task 4.1: `templates/slide-carrossel.html`
- Layout 1080x1350 no padrão visual da marca (Cinzel, creme, claret), com
  placeholders `{titulo}`, `{corpo}`, `{numero}`.

### Task 4.2: `src/carousel_render.py`
- `renderizar(slides: list[dict], pasta_destino: Path) -> list[Path]`: para cada
  slide preenche o template, salva o HTML, chama `scripts/render-slide.py` via
  subprocess, devolve os caminhos dos JPGs.
- Teste: gera HTML correto por slide (sem render real no unit test).

## Fase 5 — Produtor (orquestração)

### Task 5.1: `src/producer_state.py`
- State por artigo em `state/producao/<post_id>.json`. Campos: post_id, slug,
  titulo, status, thread_revisao_id, message_id, nossos_msg_ids, copy_carrossel,
  texto_linkedin, html_estilizado, tentativas_ajuste.
- Estados: `aguardando_revisao_copy → copy_aprovada → peca_montada`; `erro`.
- Teste: CRUD + transições.

### Task 5.2: `templates/email-revisar-copy.html`
- Corpo do email: artigo (link), copy do carrossel slide a slide, texto LinkedIn,
  instruções (mover `_COPY_OK` ou responder com ajustes).

### Task 5.3: `src/producer.py` — etapa A
- Varre `wp_source.listar_fila_social()`; para artigo sem state: estiliza →
  gera copy (carrossel + LinkedIn) → envia email `[Revisar copy]` → aplica
  `_REVISAR` → grava state.

### Task 5.4: `src/producer.py` — etapa B + ajustes
- Para state `aguardando_revisao_copy`: lê o thread; `_COPY_OK` → etapa B;
  `_COPY_AJUSTAR` ou reply → regenera copy com as instruções, reenvia.
- Etapa B: renderiza carrossel → monta pasta `producao/<ano>-S<semana>/<slug>/`
  com JPGs, legenda, textos, `conteudo.html` estilizado, `MANIFEST.json`.

## Fase 6 — Integração com o pipeline existente

### Task 6.1: MANIFEST com `post_id_existente`
- `manifest.py`: `Peca.ativos("wordpress")` aceita `post_id_existente`.
- O MANIFEST gerado pela ponte inclui esse campo.

### Task 6.2: Publisher WordPress — modo "publicar rascunho existente"
- `publishers/wordpress.py`: se `post_id_existente` presente → `WordPressClient`
  atualiza o post (`status=publish`, `content`=HTML estilizado, remove a categoria
  "Fila Social"); senão, comportamento atual.
- `wp_client.py`: novo método `update_post(site, post_id, ...)`.
- Teste: orquestração escolhe o modo certo conforme o campo.

## Fase 7 — Instalação e teste

### Task 7.1: 3ª tarefa agendada
- `install_tasks.ps1`: adicionar `Noviello-Producer` → `pythonw.exe -m src.producer`,
  a cada 2 min, oculta.

### Task 7.2: Teste end-to-end
- Mario cria a categoria "Fila Social" e marca 1 dos 5 artigos reais.
- Rodar `producer.py` à mão: confere email `[Revisar copy]` → `_COPY_OK` →
  MANIFEST montado → watcher/poller publicam em `DRY_RUN`.

---

## Auto-revisão
- Cobertura do spec: cada seção (geração de copy, estilização, render, publisher,
  labels, MANIFEST, estado) tem task. ✓
- Sem placeholders: tasks têm paths e comportamento concretos.
- Consistência: `post_id_existente`, `AnthropicClient`, `WordPressSource`,
  `producer_state` usados de forma uniforme.
