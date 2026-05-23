# Plano de Implementação — Pipeline de Aprovação e Publicação

> Base: `ESPEC-pipeline-aprovacao.md`. Execução inline autônoma, sem Git.
> Testes: `pytest` na lógica pura; clientes de API com testes de fumaça gated por credencial.

**Goal:** Construir o pipeline que envia email de aprovação, detecta a decisão via labels do
Gmail e publica nos canais ativos — rodando local via Agendador de Tarefas do Windows.

**Architecture:** Dois scripts Python idempotentes (`watcher.py`, `poller.py`) disparados a
cada 1 min. Estado por peça em JSON. Publishers plugáveis gated por `ENABLED_CHANNELS`.
Modo `DRY_RUN` para teste seguro.

**Tech Stack:** Python 3.14, google-api-python-client, google-auth-oauthlib, httpx,
tenacity, python-dotenv, structlog, pytest.

---

## Fase 0 — Scaffolding e infraestrutura

### Task 0.1: Estrutura de pastas e venv
- Criar `automacao/{src,src/publishers,setup,templates,state,logs,tests,samples}`.
- Criar venv em `automacao/.venv`; `requirements.txt`; instalar deps.
- Aceite: `python -c "import httpx, tenacity, structlog, dotenv, googleapiclient"` sem erro.

### Task 0.2: `src/config.py`
- Carrega `.env` da raiz do projeto. Resolve paths absolutos.
- `ENABLED_CHANNELS` (lista), `DRY_RUN` (bool), `EMAIL_APROVADOR`.
- Credenciais Meta: `.env` → env var Windows; reconcilia `META_IG_BUSINESS_ID` ⇄
  `IG_USER_ID_NOVIELLOADV`.
- `Config` como objeto único; função `load_config()`.
- Teste: `tests/test_config.py` — parsing de ENABLED_CHANNELS, DRY_RUN, fallback Meta.

### Task 0.3: `src/logger.py`
- structlog → JSONL em `logs/<ano>-<mes>-publicacoes.jsonl`. `get_logger()`.
- Helper `log_stage(peca_id, stage, status, duracao_ms, erro=None)`.
- Teste: escreve linha, lê de volta, valida campos.

### Task 0.4: `src/state.py`
- 1 JSON por peça: `state/<peca_id>.json`. CRUD: `load`, `save`, `delete`, `list_all`,
  `exists`. Campos: peca_id, status, message_id, thread_id, label_atual, messages_count,
  enviado_em, followup_enviado, canais_publicados, proof.
- Enum de estados. Função `transition(peca, novo_estado)` com validação.
- Teste: `tests/test_state.py` — ciclo CRUD, transições válidas/inválidas.

## Fase 1 — Setup Google (interativo, gated)

### Task 1.1: `setup/gmail_auth.py`
- Fluxo OAuth InstalledAppFlow, escopos: gmail.send, gmail.modify, gmail.labels,
  calendar.events. Abre browser, captura refresh_token, imprime para colar no `.env`.
- Não testável sem o Mario; deixar pronto + instruções no topo do arquivo.

### Task 1.2: `setup/setup_labels.py`
- Cria as 6 labels (`Noviello-Aprovacao` + 5 filhas). Idempotente (não recria
  existentes). Grava mapa nome→ID em `state/labels.json`.
- Teste de fumaça gated: roda só se houver refresh_token.

## Fase 2 — Gmail client e envio (stages 01-03)

### Task 2.1: `src/gmail_client.py`
- `GmailClient`: build service a partir do refresh_token. Métodos: `send_message(mime)`,
  `reply_to_thread(thread_id, message_id, html)`, `list_threads(query)`,
  `get_thread(thread_id)`, `modify_labels(msg_id, add, remove)`.
- Retry tenacity em 5xx/429/timeout.

### Task 2.2: `templates/email-aprovacao.html`
- HTML do email: linha de abertura, slides via `<img src="cid:slideN">`, legenda,
  rodapé "Para ajustar, responda este email".

### Task 2.3: `src/pipeline.py` — montagem do email
- `build_approval_email(peca, config)` → MIME `multipart/related` com HTML + slides
  inline (Content-ID). Subject `[Aprovar] {pilar} — {titulo_curto}`.
- Teste: `tests/test_email.py` — MIME tem N partes inline, subject correto, cid bate.

### Task 2.4: validação de MANIFEST (stage 01)
- `pipeline.validate_manifest(path)` → carrega, checa paths existem, oab_205=aprovado,
  marca=v2-conforme. Retorna `Peca` ou levanta `ValidationError`.
- Teste: `tests/test_manifest.py` — MANIFEST válido, path faltando, oab reprovado.

### Task 2.5: `src/watcher.py` (stages 01-03)
- Varre `producao/*/*/MANIFEST.json`. Para cada novo: valida → monta email → envia →
  aplica label Pendente → grava state. Erro de validação → email de erro.
- Teste em dry-run com peça de amostra (Task 5.1).

## Fase 3 — Poller e detecção de decisão (stage 04 + ALT)

### Task 3.1: detecção de decisão
- `pipeline.detect_command(thread, state, labels_map)` → approve|adjust|reschedule|
  none|timeout. Precedência: _APROVADO > _AJUSTAR > _REAGENDAR > reply > timeout.
- Teste: `tests/test_detect.py` — cada caso, incl. 12h/24h.

### Task 3.2: parsing de reply
- `pipeline.extract_reply_text(thread)` → texto plain da última msg, sem trechos
  citados (linhas iniciando com `>`).
- Teste: corpo com citação → só texto novo.

### Task 3.3: ramos ajuste/reagendamento
- `pipeline.handle_adjust(peca, texto)` → salva `AJUSTE-<ts>.txt`, reply, state.
- `pipeline.handle_reschedule(peca)` → reply com 5 datas, state.

### Task 3.4: `src/poller.py` (stages 04-08 orquestração)
- Para cada peça aguardando: get_thread → detect_command → roteia. Timeout handling.

## Fase 4 — Publishers (stages 05-08)

### Task 4.1: `src/publishers/__init__.py`
- Registro `PUBLISHERS = {"instagram":..., "linkedin":..., "wordpress":...}`.
- `get_active_publishers(config)` filtra por ENABLED_CHANNELS.
- Interface comum: `publish(peca, config, logger) -> PublishResult{ok,urls,ids,erro}`.
- Em DRY_RUN: retorna result simulado sem chamar API.
- Circuit breaker via `state/channel_health.json`.

### Task 4.2: `src/publishers/instagram.py`
- Graph API v21.0: itens de carrossel → container CAROUSEL → espera FINISHED →
  media_publish → permalink. Retry tenacity.
- Teste de fumaça: GET read-only de @novielloadv (credencial existe).

### Task 4.3: `src/publishers/wordpress.py`
- Upload media destaque → POST /wp/v2/posts (publish ou future). Host por site_destino.
- Gated por credencial.

### Task 4.4: `src/publishers/linkedin.py`
- initializeUpload → PUT imagem → POST /rest/posts. Headers de versão.
- Gated por credencial.

### Task 4.5: `src/calendar_client.py`
- `update_event(peca_id, urls)` — acha evento no calendário Marketing, faz PATCH com
  linha de publicação. Gated por credencial Google.

### Task 4.6: stages 06-08 em `pipeline.py`
- `handle_approve(peca)`: publica canais ativos → TODO linktree → email confirmação →
  calendar → move pasta para `_publicado/`, escreve PROOF.json, limpa state.
- Idempotência: checa label `_PUBLICADO` antes.

## Fase 5 — Testes end-to-end e instalação

### Task 5.1: peça de amostra
- `samples/criar_peca_teste.py` gera `producao/2026-S20-TESTE/pauta-teste/` com
  MANIFEST.json + 2 JPGs renderizados.

### Task 5.2: teste e2e dry-run
- DRY_RUN=true, ENABLED_CHANNELS=instagram: watcher → (mover label manual ou
  simulado) → poller → confirma fluxo. Documentar em `tests/e2e_dryrun.md`.

### Task 5.3: `manual_retry.py`
- `python manual_retry.py <peca_id>` → recarrega state, re-executa handle_approve.

### Task 5.4: `setup/install_tasks.ps1`
- Registra 2 tarefas no Agendador (1 min, IgnoreNew, rodar como Mario).

### Task 5.5: `RELATORIO-NOTURNO.md`
- Status do que foi construído, testado, e o passo-a-passo dos logins das 8:30.

---

## Auto-revisão
- Cobertura do spec: cada stage 01-08 + ALT tem task. Labels, state, erros, observ.,
  testes — cobertos.
- Sem placeholders: tasks têm paths e comportamento concretos.
- Consistência: `PublishResult`, `Peca`, `Config`, `detect_command` usados de forma
  uniforme entre fases.
