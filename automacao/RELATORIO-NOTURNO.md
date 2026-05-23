# Relatório noturno — Pipeline de Aprovação e Publicação

**Sessão:** noite de 17→18/05/2026 + manhã de 18/05 + noite de 18→19/05 + 22-23/05.

---

## 📌 TODO ATIVO — retomar daqui (atualizado 23/05)

### Peça parada
- **`social-11689`** (Cláusula de vigência em locação) está em **`aguardando_ajuste`**. Não vai publicar. Pedido: arte mais rica (skylines, fotos, layout variado).

### Bloqueio: gerador de imagens IA
Você precisa credenciar **uma** dessas (escolha sua):
- [ ] **(A) Gemini** — `aistudio.google.com` → criar API key → me passar (vai pro `.env` como `GOOGLE_AI_API_KEY`). **Free, ~50 imgs/dia**.
- [ ] **(B) ChatGPT Plus + Codex CLI** — instalar Codex CLI + `codex auth login`. Sem custo extra.
- [ ] **(C) OpenAI API key** — `platform.openai.com` → criar key. **~$0.04-0.08 por imagem** (DALL-E 3).

### Depois que você credenciar
1. Eu integro o gerador escolhido
2. Crio variante de template com **`image-bg + overlay claret`** (foto fullbleed em alguns slides, blur ao fundo em outros)
3. Gero 5-8 imagens temáticas (skylines SP, fachadas, chaves, contratos, etc.)
4. Re-renderizo os 10 slides do `social-11689` com mix de layouts
5. Reseto state para `aguardando_aprovacao` + ping email
6. **Você revisa de novo no painel.** Se gostar → clica "Aprovar e publicar" → vai pro IG real (`DRY_RUN=false` já).

### Validações jurídicas a fazer ANTES de aprovar o `social-11689`
A IA citou no LinkedIn (você é o advogado — confirma):
- [ ] **STJ REsp 1.669.612/RJ** existe e é sobre cláusula de vigência?
- [ ] **Distinção averbação vs registro** (LRP art. 167) — corretamente atribuída?

### Backlog / não urgente
- [ ] Liberar **LinkedIn + WordPress** nos `ENABLED_CHANNELS` (hoje só `instagram`)
- [ ] Script `samples/_sincronizar_skills.ps1` para re-espelhar skills do Claude AppData → `automacao/skills/` (quando você atualizar skills no Claude)
- [ ] Mapping de áreas: locação não detecta pelo título — só por categoria WP. Avaliar enriquecer com heurística do título
- [ ] Renovação token Meta vence ~06/07/2026 — agendar lembrete
- [ ] Renovação token LinkedIn vence ~17/07/2026 — agendar lembrete

### Estado atual do sistema (verificado 23/05)
- **5 tarefas agendadas** Watcher / Poller / Producer / Painel / Tunnel — todas ativas
- **Painel** `https://painel.noviello.adv.br` no ar, Cloudflare Access OK
- **`DRY_RUN=false`** — próximo "Aprovar e publicar" no painel = post real no @novielloadv
- **`ENABLED_CHANNELS=instagram`** — só IG por enquanto
- **98 testes verde**
- **17 skills `noviello-*`** espelhadas em `automacao/skills/` (slogan "Advocacia Humanizada e Tecnológica" removido de todos os artefatos ativos)

---

## ATUALIZAÇÃO 19/05 — Painel de Aprovação (substitui o e-mail/label)

O mecanismo de decisão por **e-mail + label do Gmail foi aposentado**. No lugar dele
há agora um **painel local** — uma página web simples que abre em
**http://localhost:8765**, com botões **Aprovar** e **Ajustar**.

**Por que mudou:** o ciclo de aprovação por label do Gmail era frágil — qualquer
reenvio de e-mail "órfãava" a label que você já tinha aplicado, e não havia uma
visão única do que estava pendente. O painel resolve isso: ele mostra o estado
atual, sempre. Não há thread de e-mail para se perder.

**Como funciona agora:**

1. O painel roda sozinho como 4ª tarefa agendada (`Noviello-Painel`) — servidor
   que fica ligado e se reinicia sozinho se cair.
2. Quando há algo a decidir, chega um **e-mail curto de aviso** (só um "ping",
   com o link do painel). O e-mail não tem botão nem label — é só o aviso.
3. Você abre **http://localhost:8765**. O painel tem duas seções:
   - **Revisar copy** — rascunhos de carrossel/LinkedIn gerados pela IA.
   - **Aprovar peça** — peças prontas, montadas, esperando o OK final.
4. Em cada cartão: botão **Aprovar** ou, se quiser mudança, escreve no campo de
   texto e clica **Ajustar**.
5. O poller/produtor leem essa decisão na próxima passada e seguem o fluxo
   (publicar, ou regenerar com o seu ajuste).

**O que foi feito nesta sessão:**

- `src/painel.py` + `templates/painel.html` — o painel, no padrão visual da marca.
- `src/emails.py` reescrito — só os 3 e-mails de aviso (ping, publicado, erro).
  Removidos os templates de aprovação/label.
- `watcher`, `poller`, `producer`, `pipeline` reescritos — leem a decisão do
  painel, não mais do Gmail.
- Removidos `decision.py`, `labels.py`, `setup_labels*.py` e os templates de
  e-mail com botão.
- **As 7 labels obsoletas do Gmail foram apagadas** (Publicar, Reagendar,
  Copy OK, Aguardando aprovacao, Revisando copy, Publicado, Erro automacao).
- **4 tarefas agendadas instaladas e ativas:** `Noviello-Watcher` (1 min),
  `Noviello-Poller` (1 min), `Noviello-Producer` (2 min), `Noviello-Painel`
  (servidor persistente).
- **60 testes automatizados passando**, incluindo o teste ponta-a-ponta
  watcher → decisão no painel → poller publica → arquiva.

**Nada mudou para ir ao ar:** continua bastando virar `DRY_RUN=false` no `.env`.
O painel já está no ar em http://localhost:8765 (verificado, HTTP 200).

> As seções abaixo são históricas — onde mencionarem "label `_APROVADO`",
> "mover o e-mail para a label" ou "e-mail [Aprovar]", leia: **decidir no painel**.

---

## ENRIQUECIMENTO DA IA 22/05 — skills + corpus do blog

> **Sessão noturna autônoma** começada por autorização do Mario às 22/05.
> Mario revisa de manhã. `DRY_RUN=true` durante toda a sessão; nada vai ao ar.

### Decisões de design (Fase 1)

**Quais skills entram no system prompt SEMPRE:**

1. `brief-marca.txt` (mantido — base atual, 43 linhas, ja calibrado)
2. `noviello-marketing-creator` (285 linhas — o redator-chefe oficial)
3. `noviello-voz-padrao` (voz da casa)
4. `verificador-de-etica-oab-em-publicidade` (Prov. 205, anti-mercantilismo)

**Skill da área — selecionada dinamicamente pelo tema do artigo:**

Mapping `categoria WP → skill da área` (default conservador):

| Categoria WP | Skill carregada |
|---|---|
| Sucessório / Inventário | `noviello-orcamentista-sucessorio` |
| Imobiliário (genérico) | `noviello-imobiliario-master` |
| Urbanístico | `noviello-imobiliario-urbanistico-paulista` |
| Locação | `noviello-imobiliario-locacao` |
| Holding / Tributário | `noviello-imobiliario-holding-tributario` |
| Regularização / REURB | `noviello-imobiliario-regularizacao-reurb` |
| Saúde Suplementar | (sem skill específica ainda) |
| Previdenciário | (sem skill específica ainda) |
| Sênior / Geriátrico | `noviello-direito-senior` |
| (fallback) | nenhuma extra |

**Mapping ambíguo (artigo em 2+ categorias):** carrega TODAS as skills das
categorias mapeadas. Skills extras não machucam (custam um pouco mais em tokens
cacheados, mas o cache da Anthropic compensa).

**Corpus do blog:**

- Top **20** artigos publicados (orderby=date desc) via WP REST.
- Por artigo: **título + 500 chars** do conteúdo (limpo de HTML).
- Reservado para a IA poder cross-linkear, evitar repetir temas, etc.
- **Refresh: 24h** (cacheado em arquivo `state/corpus-cache.json`).
- Em prompt: bloco separado com `cache_control: ephemeral`.

**Estratégia de cache da Anthropic:**

A ordem dos blocos importa para o cache (`tools → system → messages`).

Order final:
1. **system prompt** (brief-marca + 4 skills sempre + skills da área) — 1 string única, cacheada estável.
2. **user block: corpus do blog** — `cache_control: ephemeral` (vida ~5 min; refresh do corpus em 24h faz invalidar uma vez por dia).
3. **user block: artigo de referência** — `cache_control: ephemeral` (já existe hoje).
4. **user block: instrução** — sem cache (varia por chamada).

Cache rate esperado em sequência de gerações: ~85% (após a primeira).

### Plano de execução (autônomo)

| Fase | Entrega | Status |
|---|---|---|
| 1. Desenho | Esta seção do relatório | ✅ |
| 2. Skill loader | `src/skills_loader.py` + testes | ⏳ |
| 3. Detecção de área | Mapping em `src/area_resolver.py` + testes | ⏳ |
| 4. Corpus do blog | `src/blog_corpus.py` + cache 24h + testes | ⏳ |
| 5. Refactor `anthropic_client.py` | Aceita múltiplos blocos com cache_control | ⏳ |
| 6. Testes integrados | Suíte completa verde | ⏳ |
| 7. Comparação v1 vs v2 | Holding (11748) regerada com sistema enriquecido — sem publicar | ⏳ |

### Resultados (concluído na madrugada 22→23/05)

| Métrica | Valor |
|---|---|
| Skills carregadas para a Holding (3 base + 3 da área) | `noviello-marketing-creator`, `noviello-voz-padrao`, `verificador-de-etica-oab-em-publicidade`, `noviello-imobiliario-holding-tributario`, `noviello-orcamentista-sucessorio`, `noviello-imobiliario-master` |
| `system_extra` (skills combinadas) | **63.431 chars** (~15.857 tokens) |
| Corpus do blog (top 20 artigos) | **14.023 chars** (~3.505 tokens) |
| Latência **v2 carrossel** (1ª chamada, cache miss completo) | **52,8s** |
| Latência **v2 LinkedIn** (2ª chamada, cache hit no system + corpus + artigo) | **17,6s** |
| Suíte de testes | **98 passando** (60 antigos + 6 lock + 11 skills_loader + 9 area_resolver + 11 blog_corpus + 1 do producer extra; v1 da Holding mantido em 6 mas substituído pela 7 da etapa de novo módulo) |
| **Comparação v1 vs v2** | `automacao/samples/comparacao-holding-v1-v2.md` |

### Arquivos criados / modificados

| Arquivo | Mudança |
|---|---|
| `src/skills_loader.py` | **novo** — leitura + cache + combinação de skills `.md` do stash |
| `src/area_resolver.py` | **novo** — mapping `slug WP → skills da área` (15 categorias) |
| `src/blog_corpus.py` | **novo** — busca top-N artigos do blog, cache 24h, fallback offline |
| `src/anthropic_client.py` | refactor: aceita `system_extra` + `contexto_blog`; system como lista cacheada; **streaming** para max_tokens=24K |
| `src/config.py` | + `skills_dir` + auto-discovery via `_default_skills_dir()` no AppData do Claude |
| `src/producer_state.py` | + `categorias_slugs` em `ProducaoState` (persiste pra regeneração) |
| `src/producer.py` | constante `SKILLS_BASE`; `main()` monta enriquecimento; `processar_artigo_novo`/`_regenerar_copy`/`processar_revisao` aceitam `system_extra` + `contexto_blog` |
| `tests/test_skills_loader.py` | **novo** (11 testes) |
| `tests/test_area_resolver.py` | **novo** (9 testes) |
| `tests/test_blog_corpus.py` | **novo** (11 testes) |
| `samples/_comparar_holding_v1_v2.py` | **novo** — script de shadow test (não publica, só compara) |
| `samples/comparacao-holding-v1-v2.md` | gerado pela execução — leitura recomendada |
| `samples/holding-v2-raw.json` | gerado — `{v2_carrossel, v2_linkedin, métricas}` cru |

### Observações que merecem sua atenção de manhã

1. **Disclaimer OAB 205 na legenda v2** — a IA passou a inserir automaticamente um aviso `⚠️ Este conteúdo é educativo e não substitui a análise individualizada...`. Vindo da `verificador-de-etica-oab-em-publicidade`. Considere se quer manter por default.
2. **v2 cita legislação mais granular** — LC 214/2025, Lei 15.270/2025, IBS/CBS — vindo das skills tributário/holding. Verifique se os números/leis estão exatos.
3. **v2 do carrossel ficou com 9 slides** (vs 10 da v1) — provavelmente porque a IA achou o conteúdo mais conciso na nova organização. Slide 8 ("Por onde começar?") é um excelente passo-a-passo.
4. **v2 do LinkedIn mais técnico/agressivo** — "Criar holding 'de prateleira' em 2026 é erro técnico", segmenta público ("patrimônios com 4+ imóveis"). v1 era mais formal/institucional. Decida o tom que prefere.
5. **Bug encontrado e corrigido durante a noite:** SDK Anthropic exige `messages.stream(...)` para `max_tokens >= ~16K`. Refatorei para streaming.
6. **max_tokens** subiu de 10K → 24K (carrossel) e 5K → 8K (LinkedIn) pra não truncar a legenda no meio (ocorreu na 1ª tentativa).

### Fix de manhã 23/05 — skills indisponíveis pela tarefa agendada

Health check pela manhã pegou: o producer rodando pela `Noviello-Producer`
scheduled task logava `skills_indisponiveis_modo_legado`, caindo no fallback
sem skills.

**Causa:** o path `AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\...`
é visível pra processos da sessão Claude, mas a tarefa agendada (sob `pythonw`
com `LogonType=Interactive`/`RunLevel=Limited`) recebe `False` no `.exists()` —
provavelmente protected/virtualizado.

**Fix:** mirrored as 17 skills relevantes para `automacao/skills/` (path estável
do projeto, owned by Mario, sem virtualização). `NOVIELLO_SKILLS_DIR` no `.env`
agora aponta pra esse mirror. Producer pela task verificada — skills carregam OK.

**Quando re-sincronizar:** se você atualizar/adicionar skills no Claude e quiser
que o producer use a nova versão, re-rodar o passo de cópia (procedimento simples;
posso guardar como `samples/_sincronizar_skills.ps1` se quiser).

### Decisões para você de manhã

| Pergunta | Default que adotei |
|---|---|
| Mantém as 3 skills base sempre? | Sim |
| Mantém o mapping de categorias do `area_resolver.py`? | Sim — conservador. Lista em `src/area_resolver.py`. Editar pra acrescentar mapeamentos é trivial. |
| Mantém o disclaimer OAB na legenda? | Manter (IA decidiu sozinha, é bom marker de compliance) |
| Próxima peça real (não-DRY_RUN) usa qual versão (v1 ou v2)? | Sua decisão |

### Decisões 23/05 — aplicadas após resposta do Mario

| # | Decisão | Estado |
|---|---|---|
| 1 | **v2 é o padrão** para todas as novas peças | ✅ producer já cabeado pra usar enriquecimento |
| 2 | **Disclaimer OAB sempre presente** na legenda IG | ✅ cravado em `anthropic_client.py` como instrução explícita no prompt (não depende mais de a IA "decidir" pelo skill) |
| 3 | Mapping de áreas em `area_resolver.py` | ✅ mantido sem ajustes (15 categorias) |
| 4 | **`DRY_RUN=false`** ativado | ✅ `.env` editado, email de confirmação enviado (msg_id `19e4e736a89a5825`) |

**Canais habilitados na transição:** `ENABLED_CHANNELS=instagram` apenas. LinkedIn e WordPress ficam fora até o Mario autorizar expansão.

### Pendente para amanhã (23/05 noite)

Mario marcou o post 11689 (Cláusula de vigência em locação) na Fila Social. Producer gerou copy v2 ótima (slides 1-10, legenda com disclaimer OAB, LinkedIn com citação STJ REsp 1.669.612/RJ + distinção averbação/registro). Após Playwright renderizar os 10 slides, Mario clicou **Ajustar** no painel com a observação:

> *"pode melhorar a arte, usar skylines, fotos, imagens, não precisa ser tudo nesse padrão, não deixe a página sem graça"*

**Peça parada em `aguardando_ajuste`** — não dispara publicação até decisão tomada. State em `state/social-11689.json`. Slides em `producao/2026-S21/social-11689/slide01.jpg` ... `slide10.jpg`.

**Decisão pendente:** qual gerador de imagens IA usar. Mario não tem credencial configurada (sem ChatGPT Plus Codex OAuth, sem Gemini API key, sem OpenAI API key). Opções apresentadas:
1. Gemini (Google AI Studio) — free tier, criar API key 2 min
2. ChatGPT Plus via Codex CLI — se Mario tem ChatGPT Plus, install + login 1x
3. DALL-E 3 — ~$0.04-0.08/imagem

Quando retomar: Mario decide a fonte; eu (a) credencio, (b) crio variante de template com `image-bg + overlay claret`, (c) gero 5-8 imagens temáticas (skylines SP, fachadas, chaves, contratos), (d) re-renderizo os 10 slides do `social-11689` com mix de layouts, (e) reset state pra `aguardando_aprovacao`, (f) ping email.

---

## LOCK 20/05 — fim do risco de duplo post

---

## LOCK 20/05 — fim do risco de duplo post

**Problema observado em 20/05 00:04:02 (durante a primeira publicação real):**
duas instâncias do `Noviello-Poller` dispararam no mesmo segundo (tick natural
+ trigger manual). Ambas leram a mesma `decisao=aprovar`, ambas entraram em
`handle_approve`. Não houve duplo post no @novielloadv porque um dos processos
foi morto a tempo — mas o risco estava cru. A política `IgnoreNew` do Task
Scheduler tem janela de race; não dá pra confiar nela como única defesa.

**Fix:** lock OS-level **por peça** em `src/state.py` (e `producer_state.py`):

- `LockBusy` (exception) + `_file_lock` (context manager) — usa `msvcrt.locking`
  no Windows e `fcntl.flock` no Unix. O OS libera o lock quando o file
  descriptor fecha, inclusive após crash. Sem orphan locks.
- `StateStore.lock(peca_id)` e `ProducaoStore.lock(post_id)` — context managers
  não-bloqueantes. Outro processo recebe `LockBusy` e **pula** a peça nessa
  tick; tenta de novo na próxima.
- Aplicado em **poller** (`processar_estado`), **producer** (`processar_revisao`
  + `processar_artigo_novo`) e **watcher** (`processar_manifest`).
- Re-load do estado **dentro do lock**, caso outro processo tenha modificado
  entre o `list_all()` e o lock.

**Testes:** `tests/test_lock.py` com 6 testes — incluindo
`test_dois_processos_competindo_pelo_lock` que reproduz a race real do 20/05
(2 subprocessos disputando a mesma peça) e prova o fix.

**66 testes passando** (60 anteriores + 6 do lock). Suite verde.

---

## ACESSO REMOTO 19/05 — painel pelo celular

O painel agora também é acessível de fora, em **https://painel.noviello.adv.br**,
para aprovar pelo celular.

**Como foi feito:**

- **Cloudflare Tunnel** (`cloudflared`) — mantido pela tarefa agendada
  `Noviello-Tunnel` (5ª tarefa). Ela chama `setup/run_tunnel_hidden.vbs`, um
  lançador que sobe o cloudflared **sem janela de console**; reinicia sozinho
  se cair (repetição de 5 min, política IgnoreNew). Sem admin.
  O painel em si NÃO mudou: continua em `localhost:8765`; o túnel só faz a ponte.
- **Cloudflare Access** protege o endereço: ao abrir `painel.noviello.adv.br`,
  aparece uma tela de login da Cloudflare; só `mario@noviello.adv.br` passa
  (login por código enviado ao e-mail). Sem isso, qualquer um com o link
  poderia aprovar publicações.
- Arquivos: `setup/cloudflared.exe`, `setup/run_tunnel_hidden.vbs`,
  `setup/install_tunnel.ps1` (script reproduzível), config em
  `C:\Users\mario\.cloudflared\config.yml`.

**O PC ainda precisa estar ligado** — todo o pipeline roda na máquina; o túnel
só leva o celular até ela.

**Nota:** a 1ª tentativa usou um serviço do Windows (`Cloudflared`), que ficou
instalado errado (sem apontar para a config). Foi substituído pela tarefa
`Noviello-Tunnel`. O serviço morto pode ser removido com, como admin:
`& "...\setup\cloudflared.exe" service uninstall`.

**Reinstalar/reconfigurar o túnel, se preciso:**
1. `& "automacao\setup\cloudflared.exe" tunnel login` (autoriza a conta — 1x).
2. `& "automacao\setup\install_tunnel.ps1"` (cria túnel, config, DNS e a tarefa).

---

## ATUALIZAÇÃO 18/05 — ponto de retomada

**As 4 integrações estão conectadas e autenticadas:**

| Integração | Estado |
|---|---|
| Gmail + Calendar | ✅ OAuth feito, escopo Calendar incluído, 7 labels criadas |
| Meta / Instagram | ✅ token do Windows, validado |
| WordPress `noviello.adv.br` | ✅ Application Password, autenticado (admin id 1) |
| LinkedIn (Mario Noviello) | ✅ token até ~17/07/2026, sem refresh — reautorizar em jul |

`imobiliario.noviello.adv.br` é só uma landing page — não é alvo de publicação.
`WP_APP_PASSWORD_IMOBILIARIO` fica vazio de propósito.

**Teste em DRY_RUN passou** — o ciclo watcher → email → label `_APROVADO` → poller →
publicação simulada → confirmação → arquivamento funcionou ponta a ponta.

**Estado atual do `.env`:** `DRY_RUN=true`, `ENABLED_CHANNELS=instagram,wordpress,linkedin`.

**Tarefas agendadas INSTALADAS e rodando** — `Noviello-Watcher` e `Noviello-Poller`,
a cada 1 min (verificado, resultado 0). O pipeline está operacional em modo simulado.

**Caminho de escrita do WordPress validado** — teste criou um post rascunho real
(`noviello.adv.br`, post id 11744, mídia id 11743). LIMPAR: apagar esse rascunho e a
imagem 1x1 no wp-admin.

### O que falta (retomar aqui)

1. **Único passo para ir ao ar de verdade:** virar `DRY_RUN=false` no `.env`. Fazer
   isso com a primeira peça real em mãos, acompanhando — é o teste ao vivo das APIs
   de escrita de Instagram e LinkedIn (que não dá para validar sem publicar).
2. Token do LinkedIn vence ~17/07/2026 — reautorizar (`setup/gmail_auth.py` é só
   Google; para o LinkedIn, repetir o fluxo de autorização da Fase 2).
3. A peça `2026-S20-TESTE` é lixo (imagens 1x1) — **nunca publicar de verdade**.
4. Futuro: avaliar TikTok como 4º canal (publisher novo + audit do app TikTok).

---

## PONTE DE PRODUÇÃO 18/05 — construída

A 2ª fase — transformar artigos do plugin "Gerador IA Pro" em peças prontas — está
**construída e testada** (spec em `ESPEC-ponte-producao.md`, plano em
`PLANO-ponte-producao.md`).

- Novo produtor: `src/producer.py` (3ª tarefa agendada `Noviello-Producer`, a cada
  2 min — **instalada**).
- Geração de copy via API Anthropic (`anthropic_client.py`) — modelo `claude-opus-4-7`,
  testado com chamada real.
- Estilização do artigo no template da marca, renderização do carrossel via Playwright.
- 84 testes automatizados passando.
- Credenciais: `ANTHROPIC_API_KEY` no `.env`, labels `Noviello-Producao/*` criadas.

**Fluxo:** você adiciona a categoria **"Fila Social"** a um artigo no WordPress →
o produtor gera o rascunho de carrossel + LinkedIn → email **"[Revisar copy]"** →
você ajusta por reply ou aplica a label **`_COPY_OK`** → a peça é montada e entra
no pipeline de aprovação (email "[Aprovar]") → publica (em `DRY_RUN` por enquanto).

### Falta para a ponte funcionar

1. **Criar a categoria "Fila Social"** no WordPress (`noviello.adv.br` → wp-admin →
   Posts → Categorias). É o único pré-requisito pendente.
2. Apagar o rascunho de teste do WP (post 11744 + mídia 11743), se ainda não apagou.
3. Teste end-to-end: marcar 1 artigo com "Fila Social" e acompanhar o ciclo.

---

## 1. O que foi construído

Pipeline completo (stages 01-08 + ramos de ajuste/reagendamento) em Python, na pasta
`automacao/`. Abordagem B: dois scripts idempotentes (`watcher` + `poller`) para o
Agendador de Tarefas do Windows.

- **25 arquivos Python** em `src/`, `setup/`, `samples/` + `manual_retry.py`
- **66 testes automatizados — todos passando** (`pytest`)
- **venv** em `automacao/.venv` com todas as dependências instaladas
- Todos os módulos compilam e importam sem erro

Documentos: `ESPEC-pipeline-aprovacao.md` (especificação), `PLANO-implementacao.md`
(plano), este relatório.

## 2. O que está testado vs. o que aguarda credencial

| Parte | Estado |
|---|---|
| Config, estado, logs, validação de MANIFEST | ✅ testado |
| Montagem do email (slides embutidos inline) | ✅ testado |
| Watcher — detecção, validação, envio (stages 01-03) | ✅ testado com Gmail falso |
| Poller — detecção de decisão (stage 04) | ✅ testado |
| Fluxo aprovar / ajustar / reagendar / timeout | ✅ testado ponta-a-ponta em DRY_RUN |
| Publishers IG/LI/WP — orquestração, circuit breaker | ✅ testado em DRY_RUN |
| Chamadas reais a Gmail / Meta / WP / LinkedIn | ⏳ aguarda credenciais (8:30) |

A peça de teste **já foi criada** em `producao/2026-S20-TESTE/`. Assim que o Gmail
estiver configurado, rodar o watcher vai enviar um email de aprovação real dela.

## 3. Os logins das 8:30 — passo a passo

### A. Google (Gmail + Calendar) — caminho crítico, faça primeiro

1. Acesse https://console.cloud.google.com → crie um projeto (ex.: "Noviello Automacao").
2. **APIs e Serviços → Biblioteca**: habilite **Gmail API** e **Google Calendar API**.
3. **Tela de consentimento OAuth**: tipo "Externo"; em "Usuários de teste" adicione
   `mario@noviello.adv.br`.
4. **Credenciais → Criar credencial → ID do cliente OAuth → Tipo: App para computador**.
5. Baixe o JSON e salve como
   `C:\Users\mario\Documents\Noviello-Produtividade\client_secret.json`.
6. Na pasta `automacao/`, rode:
   ```
   .venv\Scripts\python.exe setup\gmail_auth.py
   ```
   O navegador abre → autorize. O script imprime 3 linhas.
7. Cole essas 3 linhas no arquivo `.env`
   (`C:\Users\mario\Documents\Noviello-Produtividade\.env`),
   substituindo `GMAIL_OAUTH_CLIENT_ID=`, `GMAIL_OAUTH_CLIENT_SECRET=` e
   `GMAIL_OAUTH_REFRESH_TOKEN=`.
8. Crie as labels do Gmail:
   ```
   .venv\Scripts\python.exe setup\setup_labels.py
   ```

### B. WordPress

1. Em **noviello.adv.br** → wp-admin → Usuários → seu perfil → "Senhas de aplicativo":
   gere uma senha (nome: "Automacao"). Copie.
2. Repita em **imobiliario.noviello.adv.br**.
3. No `.env`, preencha:
   ```
   WP_USER=<seu usuario WP>
   WP_APP_PASSWORD_NOVIELLO=<senha do site noviello>
   WP_APP_PASSWORD_IMOBILIARIO=<senha do site imobiliario>
   ```

### C. LinkedIn

1. Em https://www.linkedin.com/developers/ crie um app, associado a uma Company Page.
2. Solicite o produto **"Share on LinkedIn"** (escopo `w_member_social`).
3. Gere um access token + refresh token e descubra seu Person URN
   (`urn:li:person:XXXX`).
4. No `.env`, preencha `LI_ACCESS_TOKEN`, `LI_REFRESH_TOKEN`, `LI_PERSON_URN`.

## 4. Teste end-to-end depois dos logins

Com o Gmail já configurado (passo A completo):

```
cd C:\Users\mario\Documents\Noviello-Produtividade\automacao
.venv\Scripts\python.exe -m src.watcher
```

→ Deve chegar um email **[Aprovar] TESTE — Peça de teste do pipeline** na sua caixa,
com os slides embutidos.

Mova esse email para a label **Noviello-Aprovacao/_APROVADO** e rode:

```
.venv\Scripts\python.exe -m src.poller
```

Como `DRY_RUN=true`, os publishers vão **simular** a publicação: chega um email de
confirmação no mesmo thread, a peça é arquivada em `producao/_publicado/` e o estado
é limpo. Nada vai ao ar.

Quando estiver confiante, edite o `.env`: `DRY_RUN=false` e
`ENABLED_CHANNELS=instagram,wordpress,linkedin`.

## 5. Ativar a automação (rodar sozinha)

Depois que o teste manual passar, registre as tarefas agendadas:

```
& "C:\Users\mario\Documents\Noviello-Produtividade\automacao\setup\install_tasks.ps1"
```

Isso cria `Noviello-Watcher` e `Noviello-Poller` no Agendador, rodando a cada 1 minuto.
A partir daí o fluxo é automático: peça nova → email → você decide → publica.

## 6. Notas importantes

- **Instagram depende do WordPress.** A Graph API exige uma URL pública para cada
  imagem do carrossel. O publisher resolve isso hospedando os slides na biblioteca de
  mídia do WordPress (site `noviello`). Ou seja: para o Instagram publicar de verdade,
  a credencial do WordPress (passo B) também precisa estar pronta. Em DRY_RUN isso não
  importa.
- **`DRY_RUN=true` é o padrão.** Nada é publicado de verdade até você virar para `false`.
- **PC ligado.** As tarefas só rodam com o PC ligado; recuperam-se sozinhas quando ele
  volta. Publicação com hora cravada no Instagram precisa do PC ligado na hora.
- **Renovação do token Meta:** vence por volta de 06/07/2026 — agendar lembrete.
- **Threading do Gmail:** o email de confirmação é enviado como resposta no mesmo
  thread. No teste das 8:30, confirme que ele aparece encadeado corretamente.

## 7. Comandos de referência

| Ação | Comando (a partir de `automacao/`) |
|---|---|
| Rodar a suíte de testes | `.venv\Scripts\python.exe -m pytest tests\ -q` |
| Criar peça de teste | `.venv\Scripts\python.exe samples\criar_peca_teste.py` |
| Rodar watcher à mão | `.venv\Scripts\python.exe -m src.watcher` |
| Rodar poller à mão | `.venv\Scripts\python.exe -m src.poller` |
| Republicar peça que falhou | `.venv\Scripts\python.exe manual_retry.py <peca_id>` |
| Instalar tarefas agendadas | `& setup\install_tasks.ps1` |
| Pausar a automação | `Disable-ScheduledTask -TaskName Noviello-Watcher` (e `-Poller`) |

Logs estruturados em `automacao/logs/<ano>-<mes>-publicacoes.jsonl`.
Estado das peças em andamento em `automacao/state/`.
