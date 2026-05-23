# Plano de Implementação — Painel de Aprovação Local

> Base: `ESPEC-painel-aprovacao.md`. Execução inline autônoma, sem Git.
> Testes: `pytest` na lógica pura + rotas Flask via `app.test_client()`.

**Goal:** Substituir o mecanismo de decisão por email/label do Gmail por um painel
web local com botões Aprovar/Ajustar.

**Architecture:** Servidor Flask em `127.0.0.1:8765` lê os arquivos de estado, mostra
as pendências com arte e copy, e grava a decisão de volta no estado. Watcher/poller/
producer passam a ler `estado.decisao` em vez de varrer o Gmail. Gmail vira só
email-ping de aviso.

**Tech Stack:** Python 3.14, Flask, pytest. Reusa state/producer_state/pipeline.

---

## Fase 0 — Campos de decisão no estado

### Task 0.1: `decisao` e `ajuste_texto` no estado
- `src/state.py`: `PecaState` ganha `decisao: str = ""` e `ajuste_texto: str = ""`.
- `src/producer_state.py`: `ProducaoState` ganha os mesmos dois campos.
- Teste: `tests/test_state.py` / `tests/test_producer.py` — campos persistem no CRUD.

## Fase 1 — Email-ping

### Task 1.1: `build_ping_email` e `build_publicado_email` em `emails.py`
- `build_ping_email(quantidade: int, painel_url: str) -> EmailMessage` — assunto
  `[Painel] N peça(s) para revisar`, corpo de uma linha com o link.
- `build_publicado_email(titulo: str, urls: dict, email_aprovador) -> EmailMessage` —
  confirmação curta de publicação.
- Teste: `tests/test_email.py` — assunto e corpo corretos.

## Fase 2 — O painel

### Task 2.1: `templates/painel.html`
- Página no padrão da marca (creme, claret, Cinzel). Duas seções: "Revisar copy" e
  "Aprovar peça". Placeholder `{cards}` para os cartões; cada cartão tem form POST
  para `/decidir` com botões Aprovar e Ajustar (textarea para o ajuste).

### Task 2.2: `src/painel.py` — lógica pura
- `listar_pendencias(state_dir) -> dict` — lê `producer-state` (status
  `aguardando_revisao_copy`) e `watcher-state` (status `aguardando_aprovacao`),
  devolve `{"copy": [...], "final": [...]}`.
- `registrar_decisao(state_dir, tipo, peca_id, decisao, ajuste_texto)` — grava
  `decisao`/`ajuste_texto` no arquivo de estado certo (`producao/` ou raiz).
- Teste: `tests/test_painel.py` — pendências e gravação de decisão.

### Task 2.3: `src/painel.py` — app Flask
- `criar_app(cfg)` → Flask app. Rotas: `GET /` (renderiza painel.html com os cards),
  `GET /arte/<peca>/<arquivo>` (serve JPG de `producao/`), `POST /decidir`
  (chama `registrar_decisao`, redireciona para `/`).
- `main()` — `app.run(host="127.0.0.1", port=8765)`.
- Teste: `tests/test_painel.py` — rotas via `app.test_client()`.

## Fase 3 — Scripts lêem a decisão do painel

### Task 3.1: `poller.py` lê `estado.decisao`
- `processar_estado`: remove a busca de thread no Gmail. Lê `estado.decisao`:
  `aprovar` → `handle_approve`; `ajustar` → `handle_adjust(estado.ajuste_texto)`;
  `""` → nada. Timeout 24h por `enviado_em` mantido.
- Teste: `tests/test_poller.py` — roteia conforme `decisao`.

### Task 3.2: `producer.py` `processar_revisao` lê `estado.decisao`
- Remove `_detectar_revisao` (Gmail). Lê `producer-state.decisao`: `aprovar` →
  `_finalizar`; `ajustar` → `_reenviar_revisao(estado.ajuste_texto)`.

## Fase 4 — pipeline e watcher sem Gmail de decisão

### Task 4.1: `pipeline.py` — `handle_approve`/`handle_adjust` sem labels
- `handle_approve`: publica → `build_publicado_email` (ping) → arquiva. Remove os
  `_mover_labels` e replies de thread.
- `handle_adjust`: registra `AJUSTE-<ts>.txt` + estado `aguardando_ajuste`. Sem reply.
- Remove `handle_reschedule`/`handle_timeout` reply-no-thread → timeout só loga.

### Task 4.2: watcher e producer enviam o email-ping
- `watcher.py` stage 03: em vez de `build_approval_email`, envia `build_ping_email`.
- `producer.py` etapa A: em vez de `build_revisar_copy_email`, envia `build_ping_email`.

## Fase 5 — Aposentar o Gmail-decisão

### Task 5.1: remover código morto
- Apagar `src/decision.py` (mover `_horas_desde`/`precisa_followup` para `state.py`).
- Apagar `src/labels.py`, `setup/setup_labels.py`, `templates/email-aprovacao.html`,
  `templates/email-revisar-copy.html`.
- Remover imports órfãos em poller/producer/pipeline/watcher.
- Apagar as 7 labels do Gmail (script pontual).

## Fase 6 — Instalação e teste

### Task 6.1: 4ª tarefa `Noviello-Painel`
- `install_tasks.ps1`: adicionar `Noviello-Painel` → `pythonw.exe -m src.painel`,
  gatilho no logon + repetição (reinício se cair).

### Task 6.2: teste end-to-end
- Produzir uma peça, abrir o painel, aprovar copy e peça pelos botões; confirmar
  publicação simulada em `DRY_RUN`.

---

## Auto-revisão
- Cobertura do spec: painel (2.x), leitura de decisão (3.x), pipeline sem label (4.1),
  ping (1.1, 4.2), aposentadoria (5.1), 4ª tarefa (6.1) — tudo coberto.
- Sem placeholders: tasks com paths e comportamento concretos.
- Consistência: `decisao`/`ajuste_texto`, `registrar_decisao`, `listar_pendencias`,
  `build_ping_email` usados de forma uniforme.
