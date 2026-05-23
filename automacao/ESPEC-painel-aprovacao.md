# Especificação — Painel de Aprovação Local

- **Data:** 2026-05-19
- **Autor:** Mario Noviello + Claude
- **Substitui:** o mecanismo de decisão por email + labels do Gmail
- **Motivo:** o fluxo de email/label falhou repetidamente na prática — label na peça
  errada, resposta em vez de label, aprovação órfã quando o email era reenviado.

## 1. Objetivo

Trocar o mecanismo de decisão (aplicar label no Gmail / responder email) por um
**painel local** com botões. O Mario abre `localhost:8765`, vê as peças pendentes
com a arte e a copy à vista, e clica **Aprovar** ou **Ajustar**. O Gmail sai do
caminho de decisão; permanece apenas para um email-ping de aviso.

Isso resolve, por construção, o bug do acúmulo de emails: o painel mostra sempre o
estado atual de cada peça — não há thread de email para ficar órfã.

## 2. Arquitetura

```
producer gera peca  ──► registra no estado (aguardando_revisao_copy) + email-ping
                                          │
                          Mario abre localhost:8765, clica Aprovar/Ajustar
                                          │
                          painel grava 'decisao' no arquivo de estado da peca
                                          │
producer (proxima rodada) le estado.decisao ──► monta a peca ──► MANIFEST
                                          │
watcher detecta MANIFEST ──► registra (aguardando_aprovacao) + email-ping
                                          │
                          Mario abre o painel, clica Aprovar/Ajustar
                                          │
poller (proxima rodada) le estado.decisao ──► publica
```

O painel e os scripts agendados comunicam-se **pelos arquivos de estado** — sem
Gmail no meio. O painel escreve `decisao`; os scripts leem.

## 3. O painel (`src/painel.py`)

Servidor Flask, escuta em `127.0.0.1:8765` (não exposto à rede; uso solo, sem senha).

Rotas:
- `GET /` — página com as pendências:
  - **Revisão de copy** — peças em `producer-state` com status `aguardando_revisao_copy`.
    Mostra a copy como texto (slides slide-a-slide, legenda, texto LinkedIn).
  - **Aprovação final** — peças em `watcher-state` com status `aguardando_aprovacao`.
    Mostra os slides do carrossel já renderizados (imagens), legenda e texto LinkedIn.
  - Cada peça: botão **Aprovar** e botão **Ajustar** (com campo de texto para as
    instruções de ajuste).
- `GET /arte/<peca>/<arquivo>` — serve um JPG de slide (arquivos em `producao/`).
- `POST /decidir` — recebe `{tipo, id, decisao, ajuste_texto}` e grava a decisão no
  arquivo de estado correspondente. Redireciona de volta para `/`.

Página `templates/painel.html` no padrão visual da marca (creme, claret, Cinzel).

## 4. Mudanças no que já existe

- **`state.py` / `producer_state.py`** — `PecaState` e `ProducaoState` ganham
  `decisao: str = ""` (valores: `""` | `"aprovar"` | `"ajustar"`) e `ajuste_texto: str = ""`.
- **`poller.py`** — `processar_estado` deixa de buscar thread no Gmail. Lê
  `estado.decisao`: `aprovar` → `handle_approve`; `ajustar` → `handle_adjust`
  (com `estado.ajuste_texto`); `""` → aguarda. Timeout (24h sem decisão) mantido,
  calculado por `enviado_em`.
- **`producer.py`** — `processar_revisao` deixa de detectar label no Gmail. Lê
  `estado.decisao` do `producer-state`: `aprovar` → `_finalizar`; `ajustar` →
  `_reenviar_revisao` com `estado.ajuste_texto`.
- **`watcher.py` / `producer.py` (etapa A)** — ao registrar uma peça, em vez do
  email grande de decisão, enviam o **email-ping** curto.
- **`pipeline.py`** — `handle_approve`/`handle_adjust` deixam de mover labels e
  responder threads. `handle_approve`: publica → email-ping "publicado" → arquiva.
  `handle_adjust`: registra o ajuste, estado → `aguardando_ajuste`.
- **`emails.py`** — `build_ping_email(quantidade, painel_url)` (aviso de uma linha) e
  `build_publicado_email(peca, urls)` substituem os templates grandes. `build_error_email`
  permanece.
- **Aposentados:** `decision.py` (detecção de label/reply) — removido, exceto os
  helpers de tempo (`_horas_desde`); `labels.py`, `setup/setup_labels.py` — removidos;
  as 7 labels do Gmail podem ser apagadas; templates `email-aprovacao.html` e
  `email-revisar-copy.html` — removidos.

## 5. Ciclo de vida do servidor

4ª tarefa agendada **`Noviello-Painel`**: executa `pythonw.exe -m src.painel` no
**logon** do Windows, com repetição + `IgnoreNew` — se o processo está vivo, novas
instâncias são ignoradas; se caiu, a próxima tick (poucos min) o reinicia.
`install_tasks.ps1` ganha essa 4ª tarefa.

## 6. Email-ping

Quando uma peça fica pendente (produtor etapa A; watcher), envia-se um email curto:
assunto `[Painel] X peça(s) para revisar`, corpo de uma linha com o link
`http://localhost:8765`. Sem label, sem responder, sem decisão no email.

## 7. Erros e testes

- Retry/`tenacity` e log JSONL — inalterados.
- `pytest`: lógica pura do painel (montar a lista de pendências, gravar a decisão no
  estado), rotas Flask via `app.test_client()`, e a leitura de decisão no
  poller/producer.
- `DRY_RUN` continua governando a publicação.

## 8. Ordem de implementação

1. Campos `decisao`/`ajuste_texto` em `state.py` e `producer_state.py`.
2. `painel.py` + `templates/painel.html` (lista pendências, serve artes, grava decisão).
3. `poller.py` — ler `estado.decisao` em vez do Gmail.
4. `producer.py` — `processar_revisao` ler `estado.decisao`.
5. `pipeline.py` — `handle_approve`/`handle_adjust` sem labels/replies.
6. `emails.py` — `build_ping_email` + `build_publicado_email`; watcher/producer enviam ping.
7. Aposentar `decision.py`, `labels.py`, `setup_labels.py`, templates de email grandes.
8. `install_tasks.ps1` — 4ª tarefa `Noviello-Painel`; apagar as 7 labels do Gmail.
9. Teste end-to-end: produzir uma peça, decidir tudo pelo painel.
