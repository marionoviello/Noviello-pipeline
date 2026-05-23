# Manual de instruções — Sistema Editorial Noviello

> Como operar cada peça do sistema construído. Manual de bolso para retomar uso a qualquer momento.

**Versão**: 1.0 · 17/05/2026
**Autor**: Mario Noviello + Claude (Anthropic)

---

## Índice

1. [Visão geral do sistema](#1-visão-geral-do-sistema)
2. [Pasta de trabalho](#2-pasta-de-trabalho)
3. [O calendário "Noviello — Marketing"](#3-o-calendário-noviello--marketing)
4. [As skills Noviello e o squad editorial](#4-as-skills-noviello-e-o-squad-editorial)
5. [Scheduled tasks (automações que rodam sozinhas)](#5-scheduled-tasks)
6. [O dashboard custom](#6-o-dashboard-custom)
7. [Pipeline de produção de uma peça (passo a passo)](#7-pipeline-de-produção-de-uma-peça)
8. [Aprovação WhatsApp (quando ativada)](#8-aprovação-whatsapp)
9. [Operar Meta Ads via Claude Code](#9-meta-ads-via-claude-code)
10. [Auditar Google Ads (independente da agência)](#10-auditoria-google-ads)
11. [Rodar análises competitivas Manus](#11-análises-manus)
12. [Adicionar nova pauta ao calendário](#12-adicionar-nova-pauta)
13. [Atalhos e comandos rápidos](#13-atalhos-e-comandos-rápidos)
14. [Quando algo der errado](#14-quando-algo-der-errado)

---

## 1. Visão geral do sistema

O sistema Noviello tem 6 níveis (detalhamento técnico em `memory/context/arquitetura-macro.md`):

```
N1 Fonte da verdade        → Calendário Google + CLAUDE.md + memory/ + TASKS.md
N2 Inputs                  → Skills Noviello (50+) + NotebookLM
N3 Produção                → Texto (Claude) + Visual (Skills + Canva + Freelancer + Veo 3 + HeyGen)
N4 Distribuição            → @novielloadv + @novielloadv.agro + LinkedIn + WordPress
N5 Aprovação e orquestração → WhatsApp + N8N (em implementação)
N6 Rastreio                → Linktree UTM + métricas + dashboard
```

**Fluxo de um pilar semanal:**

```
DOMINGO 18h     → PREPARO da semana (Mario com Claude)
SEGUNDA 09h     → BRIEFING semanal blog
SEGUNDA 08h30   → Post LinkedIn (B2B abertura)
SEGUNDA 19h     → Post IG @novielloadv (B2C abertura)
TERÇA 14h       → REDAÇÃO do artigo WP
TERÇA 20h       → VÉSPERA do post de quarta
QUARTA 08h30    → Post LinkedIn (desdobramento)
QUARTA 19h      → Post/Carrossel IG @novielloadv
QUINTA 10h      → PUBLICAÇÃO WP (artigo da semana)
QUINTA 20h      → VÉSPERA do post de sexta
SEXTA 11h       → RADAR legislativo
SEXTA 19h       → Post IG @novielloadv (fecho + CTA "leia o artigo")
SÁBADO          → Stories diários + Reels agro (sáb 11h)
```

Paralelo @novielloadv.agro: 3 publicações/semana (seg post, qua carrossel, sáb Reels).

---

## 2. Pasta de trabalho

Toda a operação fica em uma pasta no seu computador:

```
C:\Users\mario\Documents\Noviello-Produtividade\
```

Organização interna:

```
Noviello-Produtividade\
├── CLAUDE.md                          ← memória de trabalho do Claude
├── TASKS.md                           ← plano operacional de 90 dias
├── TODO-MARIO.md                      ← suas pendências de execução
├── MANUAL.md                          ← este documento
├── STATUS-FINAL-SESSAO.md             ← resumo da sessão de criação
├── dashboard.html                     ← UI padrão da skill productivity
├── noviello-dashboard.html            ← dashboard custom (artifact)
├── noviello-agro.skill                ← skill empacotada (instalar)
├── noviello-publisher-instagram.skill ← skill empacotada (instalar)
├── memory\
│   ├── glossary.md                    ← decoder ring (siglas, nomes, termos)
│   ├── people\mario.md
│   ├── projects\noviello-advocacia.md
│   ├── projects\avalimob.md
│   └── context\                       ← 13 documentos operacionais
└── skills\
    ├── noviello-agro\                 ← skill descompactada
    └── noviello-publisher-instagram\  ← skill descompactada
```

**Regra de ouro**: o Claude lê automaticamente os arquivos relevantes desta pasta quando você abrir uma nova conversa no Cowork mode. Você não precisa "fornecer contexto" — basta perguntar.

---

## 3. O calendário "Noviello — Marketing"

### O que é
Calendário Google dedicado, descrição "Calendário editorial — campanha 8 semanas". É a **fila de produção** do sistema editorial. Tudo dispara a partir dele.

### Tags de evento
- `[NOV-MKT]` — Publicação ou véspera/preparo de post
- `[NOV-BLOG]` — Pipeline blog (briefing, redação, publicação)
- `[NOV-AGRO]` — Publicação para @novielloadv.agro (24 eventos criados)
- `[NOV-RADAR]` — Varredura legislativa semanal e mensal

### Como adicionar/editar
1. Abrir https://calendar.google.com
2. Selecionar o calendário "Noviello — Marketing" no lado esquerdo
3. Criar evento com o título no padrão de tag acima
4. Descrição do evento: incluir pilar + formato + skills a carregar + perfil-alvo
5. Cor recomendada: cada tag tem uma cor (NOV-AGRO = verde, NOV-MKT = padrão, NOV-BLOG = marrom, NOV-RADAR = amarelo/dourado)

### Eventos recorrentes criados
Para @novielloadv.agro, 3 eventos/semana × 8 semanas = 24 publicações agendadas até 13/07/2026:
- Segunda 09h00 — Post estático
- Quarta 19h00 — Carrossel educativo
- Sábado 11h00 — Reels

---

## 4. As skills Noviello e o squad editorial

### Filosofia squad
Em vez de 1 skill "fazer tudo", várias skills especialistas cada uma com 1 papel. Princípio do OpenSquad e dos workflows que mostramos nos vídeos de referência.

### Mapa de papéis

| Papel | Skill | Quando carregar |
|-------|-------|-----------------|
| **Orquestrador editorial** | `noviello-blog-editor-chefe` | Sempre que produzir artigo blog ou definir pilar semanal |
| **Pesquisador legislativo** | `noviello-imobiliario-radar-legislativo` | Radar semanal/mensal de mudanças normativas |
| **Especialista jurídico — Imobiliário** | `noviello-imobiliario-master` (HUB) | Qualquer demanda imobiliária |
| **Sub-especialista — Inventário** | `noviello-imobiliario-inventario-imoveis` | Inventário com imóvel |
| **Sub-especialista — Sucessório/Orçamento** | `noviello-orcamentista-sucessorio` | Orçamento de inventário, holding |
| **Sub-especialista — Sênior** | `noviello-direito-senior` | Demanda 60+ |
| **Sub-especialista — Agronegócio** | `noviello-agro` (criada nesta sessão) | Demanda agro |
| **Sub-especialista — Saúde Suplementar** | `noviello-saude-suplementar` | Negativa plano, reajuste abusivo |
| **Articulista (artigos longos)** | `noviello-articulista-juridico` | Sempre junto do blog-editor-chefe |
| **Copywriter Instagram/TikTok** | `noviello-copy-carrossel-engine` | Carrosséis, Reels, posts B2C |
| **Copywriter LinkedIn/B2B** | `noviello-copywriter` | Posts LI, copy de anúncio, landing pages |
| **Designer visual estático** | `noviello-carrossel-creator` | Renderização de slides via Playwright |
| **Designer brief técnico** | `noviello-designer-editor` | Especificação visual, código JSX/SVG |
| **Revisor OAB** | `verificador-de-etica-oab-em-publicidade` | OBRIGATÓRIO antes de toda publicação |
| **Voz e tom** | `noviello-voz-padrao` | Toda produção textual externa |
| **Identidade institucional** | `noviello-identidade` | Bio, currículo, apresentação |
| **Auditor Meta Ads** | `noviello-meta-ads-auditor` | Auditoria mensal Meta |
| **Auditor Google Ads** | `noviello-google-ads-auditor` | Auditoria mensal Google |
| **Operador Meta Ads** | `meta-ads-ratos` | Criar, pausar, ajustar campanhas Meta |
| **Operador Google Ads** | `google-ads-ratos` | Mineração de termos, alterações Google |
| **Publicador Instagram** | `noviello-publisher-instagram` (criada nesta sessão) | Levar peça pronta ao IG |
| **Comandos modais** | `noviello-comandos-modais` | Quando usar /brief, /parecer, /papel, /fontes, /oab205 etc. |
| **Skill creator** | `skill-creator` | Criar/editar outras skills |

### Como carregar uma skill
Em qualquer conversa Cowork, basta mencionar a área ou palavras-gatilho. O Claude carrega automaticamente. Você também pode pedir explicitamente: "carrega a skill noviello-imobiliario-master".

### Combinações típicas

| Caso | Skills a carregar (em sequência) |
|------|-----------------------------------|
| Carrossel sobre inventário | `noviello-imobiliario-inventario-imoveis` + `noviello-copy-carrossel-engine` + `noviello-carrossel-creator` + `verificador-de-etica-oab-em-publicidade` + `noviello-publisher-instagram` |
| Carrossel agro sobre crédito rural | `noviello-agro` + `noviello-copy-carrossel-engine` + `noviello-carrossel-creator` + `verificador-de-etica-oab-em-publicidade` + `noviello-publisher-instagram` |
| Artigo WP sobre holding familiar | `noviello-blog-editor-chefe` + `noviello-articulista-juridico` + `noviello-imobiliario-holding-tributario` + `noviello-voz-padrao` |
| Post LinkedIn técnico para incorporador | `noviello-imobiliario-master` + `noviello-imobiliario-urbanistico-paulista` + `noviello-copywriter` + `noviello-voz-padrao` |
| Petição inicial cível | `noviello-petitorio-recursal` + skill da matéria + `noviello-pje-tribunais-gotchas` + `noviello-checklist-protocolo` |
| Orçamento de inventário | `noviello-orcamentista-sucessorio` + `noviello-arisp-emolumentos` |

---

## 5. Scheduled tasks

### O que são
Tarefas que rodam automaticamente no horário programado, sem você acionar. Cada uma é independente e tem prompt completo embarcado.

### As 4 criadas

| Nome | Quando | O que faz |
|------|--------|-----------|
| `noviello-briefing-matinal` | Todo dia 07h | Agenda do dia + prazos próximos + foco recomendado |
| `noviello-retro-semanal` | Sexta 17h | Fechamento da semana + plano da próxima |
| `noviello-radar-mensal-imobiliario` | 1ª segunda do mês 09h | Varredura legislativa + jurisprudência últimos 30d |
| `noviello-auditoria-ads-mensal` | Dia 15 do mês 09h | Auditoria Meta Ads + Google Ads |

### Como gerenciar
- Painel: barra lateral do Cowork → "Scheduled"
- Ver lista: comando `/list scheduled tasks` ou ferramenta `list_scheduled_tasks`
- Editar prompt: arquivo `C:\Users\mario\OneDrive\Documentos\Claude\Scheduled\{taskId}\SKILL.md`
- Pausar/reativar: painel Scheduled
- Run now: botão no painel (para testar sem esperar o horário)

### Atenção
Scheduled tasks rodam **só quando o app Cowork está aberto**. Se estiver fechado, executa ao abrir. Para garantir execução pontual de tarefa crítica, deixar o app aberto na hora.

---

## 6. O dashboard custom

### O que é
Página HTML interativa que abre no painel lateral do Cowork. Mostra estado do sistema com dados ao vivo do calendário.

### Como abrir
Opção 1 — no Cowork: barra lateral → "Artifacts" → "noviello-sistema-editorial"
Opção 2 — no navegador: abrir `C:\Users\mario\Documents\Noviello-Produtividade\noviello-dashboard.html`

### O que mostra
1. **Countdown 10/06** — dias até o cutover agro
2. **Status do squad** — checklist do que foi criado e do que falta
3. **Próximos 7 dias** — eventos do calendário "Noviello — Marketing" (recarrega ao abrir)
4. **KPIs baseline** — placeholders a preencher na retro
5. **Tarefas críticas** — pendências em aberto
6. **Atalhos rápidos** — 6 botões que disparam prompts pré-formatados

### Atalhos disponíveis
- "▶ Briefing agora" — roda briefing matinal sob demanda
- "▶ Retro semanal" — roda retro fora do horário agendado
- "▶ Auditoria Meta Ads" — dispara auditoria
- "▶ Auditoria Google Ads" — dispara auditoria
- "⊕ Status do plano" — pergunta status do plano 90 dias
- "⊕ Próxima pauta agro" — abre próximo evento NOV-AGRO

---

## 7. Pipeline de produção de uma peça

### Receita-padrão (carrossel agro, exemplo concreto)

```
PASSO 1 — Definir pauta
  Mario abre dashboard ou consulta o calendário
  Vê próximo evento [NOV-AGRO] (ex: Qua 20/05 19h00 — Carrossel)
  Description do evento aponta pilar (ex: Crédito Rural)

PASSO 2 — Briefing técnico
  Abrir nova conversa Cowork
  Prompt: "Produzir carrossel agro para qua 20/05.
   Pilar: Crédito Rural. Tese: MCR 2-6-9 protege o produtor
   em frustração de safra. Carrossel 6 slides educativo."
  Claude carrega: noviello-agro + noviello-copy-carrossel-engine

PASSO 3 — Geração do texto editorial
  Claude produz:
   - Headline da capa
   - 4-5 slides de desenvolvimento (lei + exemplo + tese)
   - Slide CTA
   - Legenda completa (≤ 2200 chars)
   - Alt-texts por slide
   - Hashtags (≤ 30)

PASSO 4 — Geração visual
  Claude carrega: noviello-carrossel-creator + noviello-designer-editor
  Renderiza HTMLs dos 6 slides
  Executa Playwright para gerar PNGs 1080x1350
  Salva em pasta temporária

PASSO 5 — Revisão OAB
  Claude carrega: verificador-de-etica-oab-em-publicidade
  Roda checklist completo (Prov. 205/2021)
  Status: verde / amarelo / vermelho
  Vermelho → para, devolve para correção
  Amarelo → segue com nota
  Verde → segue

PASSO 6 — Aprovação manual de Mario
  (Por ora, manual; futuramente via WhatsApp+Make)
  Mario revisa preview e dá go/no-go

PASSO 7 — Publicação
  Claude carrega: noviello-publisher-instagram
  Skill executa:
   - Upload das 6 imagens para WordPress (URL pública)
   - Cria containers Graph API (6, com is_carousel_item=true)
   - Cria container CAROUSEL agrupando os 6
   - POST /media_publish
   - Retorna permalink

PASSO 8 — Logging
  Atualiza planilha-pauta (status: postado)
  Atualiza Linktree (se aplicável)
  Notifica Mario com permalink
```

### Variações por tipo de peça
- **Post estático**: pula etapa de carrossel, gera 1 imagem só
- **Reels**: troca skill carrossel-creator por Veo 3 + edição + voiceover HeyGen
- **Stories**: pula revisão OAB completa (sem caption); reaproveita arte do feed

### Tempo estimado de produção via squad

| Peça | Tempo |
|------|-------|
| Post estático simples | 15-20 min |
| Carrossel 6 slides | 40-50 min |
| Reels Veo 3 + HeyGen | 75-90 min |
| Artigo WP 2500 chars | 2-3 h |

Comparado a produção manual sem squad: 60-70% mais rápido.

---

## 8. Aprovação WhatsApp

### Quando estiver ativada (após bloco B do TODO)
Sistema dispara card no seu WhatsApp 24h antes da publicação (na véspera).

### Card que você recebe
```
🦅 NOVIELLO — pendente de aprovação
Perfil: @novielloadv.agro
Tipo: Carrossel (5 slides)
Pilar: Crédito Rural
Programado: Qua 20/05 19h00
📸 Preview: https://drive.google.com/...
📝 Legenda (157 chars + 8 hashtags): [...]
⚖️ OAB: ✅ Verde

Responda:
A → Aprovar e publicar agora
B → Ajustar (qual parte?)
C → Cancelar
```

### Como responder
- **A** → publica direto, recebe permalink em seguida
- **B** → bot pergunta o que ajustar (legenda / slide / horário / OAB), você responde, ele atualiza e devolve novo card
- **C** → bot pergunta motivo, arquiva, slot fica livre

### Janela de tempo
Você tem **23 horas** para responder. Re-aviso 4h e 12h depois. Sem resposta em 16h → arquivado como "expirado sem aprovação" automaticamente.

Detalhamento completo em `memory/context/fluxo-aprovacao-whatsapp.md`.

---

## 9. Meta Ads via Claude Code

### Setup uma vez
1. Instalar VS Code + extensão Claude Code
2. Token BM (gerado no bloco A.2 do TODO)
3. Carregar skill `meta-ads-ratos`
4. Conectar com o token

### Operações recorrentes

**Subir nova campanha** (prompt-padrão):
```
Crie campanha Meta Ads CBO chamada NOV_SENIOR_INVENTARIO_0526
com 2 conjuntos:
- AS_50MAIS_HERANCA_LOOKALIKE3PCT
- AS_50MAIS_HERANCA_INTERESSE_FAMILIA

Cada conjunto com 3 criativos (usar imagens da página).

Critérios automáticos:
- Pausar conjunto se CPA > R$ 40
- Aumentar budget +20% se ROAS > 3:1
- Pausar criativo se hook rate < 25%
- Pausar criativo se frequência > 3.5
```

**Auditoria semanal** (já automatizada na retro semanal):
```
Rode noviello-meta-ads-auditor sobre últimos 7 dias.
Identifique gargalo de funil dominante e recomende 3 ações.
```

**Iteração de criativo** (quando hook rate cai):
```
Anúncio [ID] está com hook rate caindo.
Sob noviello-meta-ads-auditor MODO B,
reescreva o BLOCO do gargalo, gere 2 variantes A/B
com hipóteses falsificáveis e plano de teste em 7 dias.
```

Detalhamento em `memory/context/protocolo-ads-claude-code.md`.

---

## 10. Auditoria Google Ads

### Por que rodar paralelo à agência
Validação cruzada do que a agência reporta. Identifica oportunidades que escapam do escopo deles. Aprendizado direto sobre a conta.

### Setup
1. Solicitar acesso de **leitura** à agência (não admin)
2. Carregar skill `google-ads-ratos`
3. Autenticar OAuth Google com sua conta
4. Confirmar Customer ID

### Auditoria mensal (já automatizada dia 15)
A scheduled task `noviello-auditoria-ads-mensal` cobre. Prompt manual equivalente:
```
Rode noviello-google-ads-auditor sobre últimos 30 dias.

1. Quality Score breakdown top 20 keywords
2. Impression Share total + Search Lost IS por campanha
3. Search Terms Report top 50 — identificar inadequados
4. CTR e CR por campanha
5. Performance Max performance

Output: 3 ações para sugerir à agência + 5 negativas.
```

### Mineração de termos
Mensal:
```
Use google-ads-ratos para pesquisar Keyword Planner.

Sementes Sucessório: "inventário extrajudicial sp",
"holding familiar custo", "doação com usufruto",
"ITCMD são paulo", "testamento como fazer".

Output: tabela ordenada por volume × CPC × concorrência.
30 keywords valiosas para sugerir adicionar/pausar.
```

---

## 11. Análises Manus

### Acesso
https://manus.im/login (login Mario, conta gratuita inicial)

### Os 5 prompts prontos
Estão em `memory/context/manus-ia-5-prompts.md`. Cole um por vez no Manus.

### Sequência sugerida (1 análise/semana, 5 semanas)
1. Escritórios concorrentes SP — base estratégica
2. Lacunas de pauta blogs jurídicos — alimenta blog
3. Landing pages planejamento sucessório — wireframe nova landing
4. Concorrência agro IG/YouTube — ajuste banco pautas agro
5. Mercado avaliação imobiliária B2B — reformulação Avalimob

### Output esperado
Cada análise gera **página navegável de insights** (URL pública do Manus). Salve o link em `memory/context/manus-resultados/{prompt}-{data}.md` para alimentar próximos ciclos.

### Consumo de créditos
Cada prompt consome 3-8 créditos. Versão gratuita tem cota diária. Se faltar crédito, dividir o prompt em batches (3 URLs por vez).

---

## 12. Adicionar nova pauta

### No calendário
1. Abrir Calendar → calendário "Noviello — Marketing"
2. Criar evento com tag `[NOV-MKT]`, `[NOV-AGRO]`, `[NOV-BLOG]`
3. Descrição do evento (modelo):
   ```
   Pilar: [Sênior | Imobiliário | Sucessório | Agro | Saúde]
   Formato: [Post | Carrossel | Reels | Stories]
   Tema: [tese central da pauta]
   Lei base: [fundamento jurídico]
   Skills: [skills a carregar]
   Perfil-alvo: [@novielloadv ou @novielloadv.agro]
   ```

### No banco de pautas
Adicionar em `memory/context/banco-de-pautas-agro-8sem.md` (agro) ou similar (outros pilares — ainda a criar arquivo dedicado para os 5 pilares principais).

### No backlog
Manter uma planilha de pautas "à frente" — meta: 4 semanas adiantadas.

---

## 13. Atalhos e comandos rápidos

### Comandos modais (carregam skill `noviello-comandos-modais`)

| Comando | Função |
|---------|--------|
| `/brief` | Resposta no formato briefing técnico curto |
| `/parecer` | Resposta no formato parecer jurídico completo |
| `/sintese` | Resposta enxuta, sem desenvolvimento |
| `/cliente` | Linguagem acessível para cliente B2C |
| `/audiencia` | Notas para apresentação oral em audiência |
| `/diligencia` | Foco em ações operacionais imediatas |
| `/contraditorio` | Antecipa argumentos da parte contrária |
| `/distinguishing` | Aplica distinção/overruling em precedente |
| `/extrajudicial` | Foco em via não-litigiosa |
| `/fontes` | Reforça citação de norma com número e ano |
| `/papel` | Calibra para timbre formal de papel timbrado |
| `/copiarcolar` | Output pronto para copiar e colar em peça |
| `/criativo` | Mais autoral, menos engessado |
| `/orcamento` | Resposta com cálculo + composição de custos |
| `/schwartz` | Calibra copy por nível de consciência (Eugene Schwartz) |
| `/ogilvy` | Calibra copy para marca/posicionamento (David Ogilvy) |
| `/oab205` | Aplica verificação ética Prov. OAB 205/2021 |

Comandos podem combinar: `/parecer /papel /fontes` produz parecer formal com timbre e citação reforçada.

### Atalhos do dashboard
6 botões pré-configurados (ver seção 6).

### Prompts úteis para começar conversa
- "Mostre o status do sistema editorial Noviello — onde estamos no plano de 90 dias"
- "Produzir a próxima pauta agro do calendário"
- "Rode auditoria Meta Ads dos últimos 30 dias"
- "Atualizar memory/context/metricas-ancora.md com baseline da semana"

---

## 14. Quando algo der errado

### Onde estão os documentos de troubleshooting

| Problema | Onde consultar |
|----------|----------------|
| Erro Graph API (publicação IG) | `skills/noviello-publisher-instagram/references/rate-limits-troubleshooting.md` |
| Token expirado | `skills/noviello-publisher-instagram/references/autenticacao-graph-api.md` |
| OAB devolveu vermelho | `skills/noviello-publisher-instagram/references/compliance-oab-pre-publicacao.md` |
| URL de imagem não acessível | `skills/noviello-publisher-instagram/references/hospedagem-de-imagens.md` |
| Aprovação WhatsApp não chega | `memory/context/fluxo-aprovacao-whatsapp.md` |
| Métrica de Ads esquisita | `memory/context/protocolo-ads-claude-code.md` |
| Skill não está sendo carregada | Verificar se está instalada (painel skills do Cowork) |

### Diagnóstico geral
Em qualquer dúvida operacional, abrir nova conversa no Cowork e perguntar. O Claude tem acesso ao memory desta pasta e responde com base no contexto.

### Backup
Toda a pasta `C:\Users\mario\Documents\Noviello-Produtividade\` deve ser incluída no backup periódico (OneDrive sincroniza automaticamente, mas vale conferir). Os arquivos `.skill` são empacotáveis a qualquer momento via Python — só re-zipar a pasta `skills/{nome}/`.

### Versionamento
Não há git ativo na pasta hoje. Para versionar mudanças importantes, salvar uma cópia datada de arquivos críticos antes de grandes alterações:
```
TASKS.md → TASKS-2026-05-17.md
CLAUDE.md → CLAUDE-2026-05-17.md
```

Quando esse processo virar fricção, vale ativar git local com commits diários.

---

## Apêndice — Referência rápida de URLs

| O quê | URL |
|-------|-----|
| Sites Noviello | https://noviello.adv.br · https://imobiliario.noviello.adv.br |
| Calendário "Noviello — Marketing" | Calendar com ID `c_bec1d399...` |
| Linktree @novielloadv | (a criar) https://linktr.ee/novielloadv |
| Linktree @novielloadv.agro | (a criar) https://linktr.ee/novielloadv_agro |
| Meta Business Suite | https://business.facebook.com |
| Meta Graph API Explorer | https://developers.facebook.com/tools/explorer |
| Z-API | https://z-api.io |
| N8N | https://n8n.io |
| Manus | https://manus.im/login |
| HeyGen | https://heygen.com |
| MCR BACEN | https://www.bcb.gov.br/estabilidadefinanceira/mcr |
| INCRA — SNCR | https://sncr.serpro.gov.br |
| SICAR | https://www.car.gov.br |
| INCRA SIGEF | https://sigef.incra.gov.br |
| Plano Safra MAPA | https://www.gov.br/agricultura/pt-br/assuntos/plano-safra |

---

## Apêndice — Glossário rápido

Para o decoder completo de siglas, nomes e termos, ver `memory/glossary.md`.

| Sigla | Significado |
|-------|-------------|
| HIS / HMP | Habitação de Interesse Social / Mercado Popular (SP) |
| REURB | Regularização Fundiária Urbana (Lei 13.465/2017) |
| MCR | Manual de Crédito Rural (BACEN) |
| CCB | Cédula de Crédito Bancário |
| CPR | Cédula de Produto Rural |
| PRA | Patrimônio Rural em Afetação (Lei 13.986/2020) — **NÃO** confundir com PRA do Código Florestal |
| CIR | Cédula Imobiliária Rural |
| CCIR | Certificado de Cadastro de Imóvel Rural (INCRA) |
| CAR | Cadastro Ambiental Rural |
| SIGEF | Sistema de Gestão Fundiária (georreferenciamento) |
| FMP | Fração Mínima de Parcelamento |
| OODC | Outorga Onerosa do Direito de Construir |
| CEPAC | Certificado de Potencial Adicional de Construção |
| ITCMD | Imposto sobre Transmissão Causa Mortis e Doação |
| IBS / CBS | IVA Dual (Reforma Tributária LC 214/2025) |
| CPL | Custo Por Lead |
| ROAS | Return on Ad Spend |
| BUC | Business Use Case (rate limit Meta) |
| MCP | Model Context Protocol (Anthropic) |

---

**Fim do manual.**

Para atualizações deste documento, basta abrir nova conversa Cowork e pedir: "atualizar MANUAL.md com a nova função X". Claude lê o arquivo, edita e devolve.
