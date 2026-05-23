# Especificação — Pipeline de Aprovação e Publicação Multicanal

- **Data:** 2026-05-18
- **Autor:** Mario Noviello + Claude
- **Base:** `automacao/workflow-aprovacao-publicacao-v2-email.json` (manifesto v2.0)
- **ID:** `noviello.fluxo.aprovacao-publicacao-email`
- **Abordagem:** B — scripts Python idempotentes orquestrados pelo Agendador de Tarefas do Windows

## 1. Objetivo

Pegar uma peça de conteúdo já produzida e validada (HTML/JPG/copy + `MANIFEST.json`), enviar
um email de aprovação para `mario@noviello.adv.br`, detectar a decisão do Mario via labels do
Gmail e, quando aprovada, publicar nos canais ativos (Instagram, LinkedIn, WordPress). Tudo
roda localmente no PC Windows do Mario, sem custo recorrente e sem túnel público.

Fora de escopo: produção da peça (skills do ecossistema), geração de copy, verificação
OAB 205/2021 — tudo isso acontece **antes** deste pipeline.

## 2. Arquitetura

Dois scripts Python idempotentes, cada um disparado pelo Agendador de Tarefas do Windows
**a cada 1 minuto**. Sem daemon persistente. Cada execução é curta, isolada e segura para
repetir. As tarefas são registradas com a política "não iniciar nova instância se já estiver
em execução" (`MultipleInstancesPolicy = IgnoreNew`), o que elimina concorrência sem lock
no código.

```
[Mario roda skills → render-slide.py → MANIFEST.json em producao/<semana>/<pauta>/]
        │
        ▼  Task Scheduler · a cada 1 min
   watcher.py     (stages 01-03)
     • detecta MANIFEST novo (status=pronta_para_aprovacao, peca_id sem state)
     • valida paths + oab_205 + marca
     • monta email com slides embutidos (inline MIME) e envia via Gmail API
     • aplica label "Pendente" · grava state/<peca_id>.json
        │
        ▼  Mario abre o Gmail · move label _APROVADO / _AJUSTAR / _REAGENDAR (ou responde)
        │
        ▼  Task Scheduler · a cada 1 min
   poller.py      (stages 04-08)
     • para cada peça aguardando: GET thread, compara labelIds + nº de mensagens
     • _APROVADO   → publica nos canais ativos → linktree TODO → email confirmação
                     → atualiza Calendar → arquiva peça
     • _AJUSTAR    → salva AJUSTE-<ts>.txt, responde no thread, status=aguardando_ajuste
     • _REAGENDAR  → responde com 5 datas, status=aguardando_reagendamento
     • timeout: 12h sem ação → follow-up · 24h → erro
```

### Limitação aceita

Com o PC desligado ou em suspensão, as tarefas não rodam — recuperam-se na próxima
execução quando o PC volta. Aceitável: peças são produzidas e aprovadas durante o dia.
Publicação com hora cravada no Instagram exigiria o PC ligado naquele minuto; no WordPress
isso é resolvido com `status=future` (agendamento server-side). Escalar para nuvem fica
para um ciclo futuro.

## 3. Estrutura de arquivos

```
automacao/
  src/
    config.py           # carrega .env, resolve paths, ENABLED_CHANNELS, DRY_RUN
    state.py            # 1 JSON por peça em state/<peca_id>.json
    logger.py           # structlog → logs/<ano>-<mes>-publicacoes.jsonl
    gmail_client.py     # enviar, listar threads, obter thread, mover labels
    calendar_client.py  # atualizar evento do calendário "Noviello — Marketing"
    pipeline.py         # lógica compartilhada dos stages
    watcher.py          # entry point da tarefa agendada 1 (stages 01-03)
    poller.py           # entry point da tarefa agendada 2 (stages 04-08)
    publishers/
      __init__.py       # registro de publishers; resolve por ENABLED_CHANNELS
      instagram.py      # Graph API v21.0 — funcional hoje
      linkedin.py       # escrito; inativo até credencial existir
      wordpress.py      # escrito; inativo até credencial existir
  setup/
    gmail_auth.py       # fluxo OAuth de consentimento — roda 1x, gera refresh_token
    setup_labels.py     # cria as 6 labels do Gmail — roda 1x; grava state/labels.json
    install_tasks.ps1   # registra as 2 tarefas no Agendador de Tarefas
  manual_retry.py       # republica uma peça que falhou: python manual_retry.py <peca_id>
  templates/
    email-aprovacao.html
  state/                # <peca_id>.json, labels.json, channel_health.json
  logs/                 # <ano>-<mes>-publicacoes.jsonl
  requirements.txt
  ESPEC-pipeline-aprovacao.md   (este documento)
.env                    # raiz do projeto, fora de Git
```

## 4. Stack

- **Python 3.14** (já instalado), virtualenv em `automacao/.venv`
- `google-api-python-client`, `google-auth-oauthlib` — Gmail + Calendar
- `httpx` — Meta / LinkedIn / WordPress
- `tenacity` — retry exponencial
- `python-dotenv` — secrets
- `structlog` — logs JSONL

Não usa `watchdog`: o Agendador de Tarefas substitui o watcher de filesystem; `watcher.py`
apenas varre a pasta `producao/` uma vez por execução.

## 5. Configuração (`.env` na raiz do projeto)

```
# Google (Gmail + Calendar — OAuth único)
GMAIL_OAUTH_CLIENT_ID=
GMAIL_OAUTH_CLIENT_SECRET=
GMAIL_OAUTH_REFRESH_TOKEN=
GOOGLE_CALENDAR_ID=Noviello — Marketing

# Meta / Instagram (já configurado em env vars do Windows; .env pode sobrescrever)
META_PAGE_TOKEN=
META_IG_BUSINESS_ID=
META_PAGE_ID=

# LinkedIn (pendente)
LI_ACCESS_TOKEN=
LI_REFRESH_TOKEN=
LI_PERSON_URN=

# WordPress (pendente)
WP_USER=
WP_APP_PASSWORD_NOVIELLO=
WP_APP_PASSWORD_IMOBILIARIO=

# Comportamento
ENABLED_CHANNELS=instagram        # lista separada por vírgula
DRY_RUN=true                      # true = publishers simulam; email roda real
EMAIL_APROVADOR=mario@noviello.adv.br
```

`config.py` resolve credenciais Meta nesta ordem: `.env` → variável de ambiente do Windows.
Reconcilia o nome legado: se `META_IG_BUSINESS_ID` estiver vazio, usa `IG_USER_ID_NOVIELLOADV`
(nome criado por `scripts/setup-meta-token.ps1`).

## 6. Labels do Gmail

Criadas uma única vez por `setup_labels.py`, que grava o mapa nome→ID em `state/labels.json`.
O `poller.py` compara `labelIds` do thread contra esses IDs.

| Label | Quem aplica | Significado |
|---|---|---|
| `Noviello-Aprovacao` | — | container |
| `Noviello-Aprovacao/Pendente` | watcher | estado inicial de toda peça |
| `Noviello-Aprovacao/_APROVADO` | Mario | publicar |
| `Noviello-Aprovacao/_AJUSTAR` | Mario | fluxo de ajuste |
| `Noviello-Aprovacao/_REAGENDAR` | Mario | fluxo de reagendamento |
| `Noviello-Aprovacao/_PUBLICADO` | poller | publicado com sucesso |
| `Noviello-Aprovacao/_ERRO` | poller | falhou após 3 retries |

## 7. Contrato de entrada — `MANIFEST.json`

Conforme `io_contracts.MANIFEST_da_peca` do manifesto v2.0 (inalterado). Campos-chave:
`peca_id`, `tipo`, `pilar`, `titulo_curto`, `data_publicacao_alvo`, `status`,
`validacoes.{oab_205,marca,ortografia}`, `ativos.{instagram,linkedin,wordpress}`,
`cross_link`. Todos os paths de assets são absolutos.

## 8. Stages

### Stage 01 — Detectar (watcher.py)
Varre `producao/*/*/MANIFEST.json`. Para cada com `status=pronta_para_aprovacao` e
`peca_id` sem arquivo em `state/`: lê o MANIFEST, valida que todos os paths existem,
que `validacoes.oab_205 == "aprovado"` e `validacoes.marca == "v2-conforme"`. Falha de
validação → email de erro para Mario, peça não avança.

### Stage 02 — (eliminada)
**Desvio do manifesto.** Em vez de hospedar a imagem no WordPress/Drive, os slides são
embutidos no email como anexos inline MIME (`Content-ID` / `cid:`). Sem dependência
externa de hospedagem. Gmail aceita até 25 MB por mensagem.

### Stage 03 — Enviar email de aprovação (watcher.py)
Monta MIME `multipart/related`: corpo HTML (template) + todos os slides do carrossel
embutidos via `cid:`. Envia por `POST /gmail/v1/users/me/messages/send`. Aplica label
`Pendente`. Grava `state/<peca_id>.json` com `message_id`, `thread_id`, `label_atual`,
`messages_count`, `enviado_em`.

### Stage 04 — Detectar decisão (poller.py)
Para cada peça em estado `aguardando_aprovacao`: `GET /threads/{thread_id}`. Compara
`labelIds` e `messagesCount` com o state. Precedência: `_APROVADO` → approve;
`_AJUSTAR` → adjust; `_REAGENDAR` → reschedule; reply sem mover label → adjust (lê texto).
Timeout: `>12h` sem ação → reply de follow-up (uma vez); `>24h` → estado `timeout` + label `_ERRO`.

### Stage 05a/b/c — Publicar (poller.py, comando=approve)
Para cada canal em `ENABLED_CHANNELS` que tenha assets no MANIFEST, chama o publisher
correspondente. Canal pedido no MANIFEST mas não em `ENABLED_CHANNELS` → registra TODO,
não falha a peça.
- **instagram.py** — cria itens de carrossel, container `CAROUSEL`, aguarda `FINISHED`,
  `media_publish`, obtém permalink.
- **linkedin.py** — `initializeUpload` → PUT imagem → `POST /rest/posts`.
- **wordpress.py** — upload de mídia destaque → `POST /wp/v2/posts` com `status=publish`
  ou `future`. Host resolvido por `ativos.wordpress.site_destino`.

Com `DRY_RUN=true` o publisher loga o que faria e retorna proof simulado.

### Stage 06 — Linktree
Default: gera TODO no log e menciona "Linktree pendente" no email de confirmação.
Sem automação Playwright neste ciclo.

### Stage 07 — Email de confirmação (poller.py)
Responde o thread original (`In-Reply-To`) com os links publicados. Remove label
`Pendente`, aplica `_PUBLICADO`, arquiva o thread.

### Stage 08 — Persistir e arquivar
Move a pasta da peça para `producao/_publicado/<peca_id>-<timestamp>/`. Escreve
`PROOF.json` com todos os IDs/URLs. Atualiza o evento do Google Calendar. Append no
log JSONL. Remove o arquivo de state da peça.

### Stage ALT — Ajuste
Lê o texto do reply mais recente (corpo plain-text, sem trechos citados). Salva como
`AJUSTE-<timestamp>.txt` na pasta da peça. Marca `status=aguardando_ajuste`. Responde
no thread confirmando recebimento. Regeneração da peça é feita fora deste pipeline.

### Stage ALT — Reagendar
Responde no thread com 5 datas alternativas do calendário Marketing. Aguarda o próximo
reply com a data escolhida (parse ISO8601 ou DD/MM). Atualiza Calendar e
`MANIFEST.data_publicacao_alvo`. Move label de volta para `Pendente`.

## 9. Máquina de estados (`state/<peca_id>.json`)

```
detectada → aguardando_aprovacao → aprovada → publicando → publicada
                   │                                          (state removido)
                   ├── aguardando_ajuste
                   ├── aguardando_reagendamento
                   ├── timeout
                   └── erro
```

## 10. Tratamento de erros

- **Retry:** `tenacity`, 3 tentativas, backoff exponencial 2s/8s/32s, aplicável a
  HTTP 5xx, timeout de rede e 429.
- **Falha após 3 retries:** label `_ERRO`, reply no thread com erro curto + caminho do
  log. Retomada manual: `python manual_retry.py <peca_id>`.
- **Circuit breaker:** 3 falhas consecutivas no mesmo canal → canal pausado 1h
  (`state/channel_health.json`).
- **Idempotência:** chave = `peca_id`. Antes de publicar, verifica state local **e**
  ausência da label `_PUBLICADO` no Gmail. Replay nunca duplica.

## 11. Observabilidade

- Log estruturado JSONL em `logs/<ano>-<mes>-publicacoes.jsonl`, campos mínimos:
  `timestamp, peca_id, stage, status, duracao_ms, erro`.
- Os threads do Gmail funcionam como trilha de auditoria nativa (envio + decisão +
  confirmação + erros).

## 12. Plano de testes (faseado)

1. `gmail_auth.py` → consentimento OAuth → `refresh_token` no `.env`; envio de teste.
2. `setup_labels.py` → 6 labels criadas; conferir no Gmail; `state/labels.json` gerado.
3. `DRY_RUN=true`, `ENABLED_CHANNELS=instagram`: criar peça de amostra (MANIFEST + 2 JPGs);
   rodar `watcher.py` à mão → email chega com slides embutidos; mover label `_APROVADO`;
   rodar `poller.py` → publishers simulam; email de confirmação chega; state limpo.
4. Testar ramos `_AJUSTAR` e `_REAGENDAR` em dry-run.
5. `DRY_RUN=false`, só Instagram: publicação real de um carrossel de teste.
6. `install_tasks.ps1` → registra as 2 tarefas; verificar execução automática.

## 13. Ordem de implementação

1. Scaffolding: estrutura de pastas, `requirements.txt`, `.venv`, `config.py`, `state.py`,
   `logger.py`.
2. `gmail_auth.py` (OAuth) + `setup_labels.py`.
3. `gmail_client.py` + template de email + `watcher.py` (stages 01-03).
4. `poller.py` — detecção de decisão (stage 04) + ramos ajuste/reagendamento.
5. Publishers: `instagram.py` real; `linkedin.py` e `wordpress.py` escritos e gated por
   `ENABLED_CHANNELS`.
6. Stages 06-08 (linktree TODO, email de confirmação, calendar, arquivamento) + retry,
   circuit breaker, `manual_retry.py`.
7. `install_tasks.ps1` + teste end-to-end.

## 14. Pré-requisitos do Mario (tarefas interativas, fora do código)

- **Gmail:** criar projeto no Google Cloud Console, habilitar Gmail API + Calendar API,
  criar OAuth Client tipo Desktop, rodar `gmail_auth.py` uma vez para o consentimento.
- **WordPress:** gerar Application Password nos dois sites; preencher `.env`. Até lá,
  `wordpress` fica fora de `ENABLED_CHANNELS`.
- **LinkedIn:** criar/aprovar app com escopo `w_member_social`, obter tokens + Person URN.
  Até lá, `linkedin` fica fora de `ENABLED_CHANNELS`.
- **Meta:** já configurado e validado (`@novielloadv`, token long-lived até ~2026-07-06).
