# Especificação — Ponte de Produção (artigo do plugin → peça pronta)

- **Data:** 2026-05-18
- **Autor:** Mario Noviello + Claude
- **Depende de:** `ESPEC-pipeline-aprovacao.md` (pipeline de aprovação/publicação, já no ar)
- **Abordagem:** estender o pipeline existente com uma 3ª etapa — o "produtor" —
  reusando Gmail client, state, config, labels e o renderizador `render-slide.py`.

## 1. Objetivo

Transformar um artigo gerado pelo plugin WordPress "Gerador IA Pro" numa **peça
multicanal pronta** (artigo estilizado + carrossel de Instagram + post de LinkedIn),
com um ponto de revisão de copy pelo Mario, entregando um `MANIFEST.json` que o
pipeline de aprovação já existente consome.

A ponte preenche a lacuna entre a produção de conteúdo (plugin) e o pipeline de
aprovação (que começa numa peça já pronta).

## 2. Fluxo

```
Plugin "Gerador IA Pro" gera artigo no WordPress (rascunho/pending)
   │  Mario adiciona a categoria "Fila Social" ao artigo
   ▼  producer.py  (3ª tarefa agendada, a cada 2 min)
ETAPA A — produzir rascunho de copy
   • varre o WP: artigos na categoria "Fila Social" sem state de producao
   • estiliza o HTML cru do artigo no template noviello-artigo
   • chama a API Anthropic: condensa o artigo em copy de carrossel (8-10 slides)
     + texto curto de LinkedIn — brief da marca + regras OAB embutidos no prompt
   • envia email "[Revisar copy]" com a copy slide a slide + texto LI
   • grava state de producao (status=aguardando_revisao_copy)
   ▼  Mario: ajusta por reply (regenera) OU aplica label _COPY_OK
ETAPA B — finalizar a peça
   • detecta _COPY_OK no thread de revisao
   • renderiza os slides do carrossel (slide-carrossel.html + render-slide.py) -> JPGs
   • monta a pasta da peca em producao/<ano>-S<semana>/<slug>/ + MANIFEST.json
   • state de producao -> concluido
   ▼
watcher.py -> email "[Aprovar]" -> poller.py -> publica   (pipeline existente)
```

Dois pontos de controle do Mario, ambos por email + label:
**[Revisar copy]** (a copy) e **[Aprovar]** (a peça pronta).

## 3. Componentes novos

```
automacao/src/
  producer.py          # 3a tarefa agendada — orquestra etapas A e B
  anthropic_client.py  # cliente da API Anthropic — gera copy de carrossel e LinkedIn
  article_styler.py    # envolve o HTML cru do plugin no template noviello-artigo
  carousel_render.py   # copy -> HTML de slide -> render-slide.py -> JPGs
  wp_source.py         # le artigos da categoria "Fila Social" via WP REST
  producer_state.py    # state da producao (reusa o padrao do StateStore)
automacao/templates/
  artigo-noviello.html # template-mestre do artigo (extraido do post 11723)
  slide-carrossel.html # template de um slide do carrossel, no padrao visual da marca
  email-revisar-copy.html  # corpo do email "[Revisar copy]"
automacao/setup/
  setup_labels_producao.py  # cria o conjunto de labels Noviello-Producao/
```

Ajustes em arquivos existentes:
- `config.py` — carrega `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `WP_CATEGORIA_FILA_SOCIAL`
- `labels.py` — adiciona o conjunto `Noviello-Producao/` (`_COPY_OK`, `_COPY_AJUSTAR`)
- `publishers/wordpress.py` — modo "publicar rascunho existente" (ver seção 7)
- `manifest.py` — campo opcional `ativos.wordpress.post_id_existente`
- `install_tasks.ps1` — registra a 3ª tarefa `Noviello-Producer`

## 4. Geração de copy (API Anthropic)

`anthropic_client.py` chama a Messages API. O prompt de sistema carrega o **brief da
marca Noviello** (tom de voz, pilares, terminologia "Sênior", proibições, públicos A/B)
e as **regras do Provimento OAB 205/2021** (sem promessa de resultado, sem
mercantilismo). O prompt de usuário recebe o texto do artigo e pede:

- **Carrossel:** 8 a 10 slides — slide 1 = capa/gancho, slides intermediários =
  desenvolvimento, último = CTA aprovado. Saída em JSON estruturado (lista de slides
  com `titulo` e `corpo`).
- **LinkedIn:** texto curto (até ~1.300 caracteres), tom Público B, com link para o
  artigo, sem hashtags excessivas.

Modelo: `ANTHROPIC_MODEL` no `.env` (padrão: Claude Sonnet — qualidade de copy;
o id exato do modelo é confirmado na implementação). Retry com `tenacity`.
A copy gerada é sempre revisada pelo Mario no email "[Revisar copy]" — a API produz
um rascunho, nunca a versão final.

## 5. Estilização do artigo

`article_styler.py` pega o HTML cru do plugin (só `<h2>/<h3>/<p>/<ul>/<ol>/<table>`)
e o injeta no `templates/artigo-noviello.html` — o template-mestre extraído do post
11723, contendo:
- bloco `<!-- wp:html -->` + `<style>` da marca (paleta claret/creme/dourado,
  fontes Cinzel + Poppins)
- wrapper `<div class="noviello-artigo">`
- tabelas recebem `class="noviello-tabela"`

A transformação é mecânica (mapeamento de tags), sem reescrever o conteúdo. O HTML
estilizado é o que será publicado no WordPress (substitui o conteúdo cru do rascunho).

## 6. Renderização do carrossel

`carousel_render.py`: para cada slide da copy aprovada, preenche
`templates/slide-carrossel.html` (layout 1080x1350 no padrão visual da marca) e chama
`scripts/render-slide.py` para gerar o JPG. Resultado: N arquivos `slideNN.jpg` na
pasta da peça.

Dependência: Playwright + Chromium instalados no venv.

## 7. Ajuste no publisher do WordPress

Hoje `wordpress.py` sempre **cria** um post novo. Como o artigo já existe no WP
(criado pelo plugin), publicar criaria um duplicado.

Novo comportamento: se `ativos.wordpress.post_id_existente` está presente no MANIFEST,
o publisher **atualiza** esse post — `POST /wp/v2/posts/{id}` com `status=publish`,
`content` = HTML estilizado, e **remove a categoria "Fila Social"** (mantendo as
categorias editoriais reais). Se o campo está ausente, mantém o comportamento atual
(criar post novo).

## 8. Contrato — MANIFEST gerado pela ponte

A ponte gera um MANIFEST conforme `ESPEC-pipeline-aprovacao.md`, com:
- `ativos.instagram`: imagens (JPGs renderizados), legenda (derivada do carrossel),
  hashtags, `tipo_post=carrossel`
- `ativos.wordpress`: `post_id_existente`, `site_destino`, `conteudo_html` (estilizado),
  `titulo`, `slug`, `status_alvo=publish`
- `ativos.linkedin`: imagem (slide de capa), texto (post LI gerado)
- `validacoes`: `oab_205=aprovado` (a copy passou pela revisão do Mario),
  `marca=v2-conforme`

## 9. Etapas de email e labels

Novo conjunto de labels, criado por `setup_labels_producao.py`:

| Label | Quem aplica | Significado |
|---|---|---|
| `Noviello-Producao` | — | container |
| `Noviello-Producao/_REVISAR` | producer | rascunho de copy aguardando revisão |
| `Noviello-Producao/_COPY_OK` | Mario | copy aprovada — finalizar peça |
| `Noviello-Producao/_COPY_AJUSTAR` | Mario | regenerar a copy (com instruções no reply) |
| `Noviello-Producao/_ERRO` | producer | falha na produção |

Email **"[Revisar copy] {pilar} — {titulo}"**: mostra a copy do carrossel slide a
slide e o texto de LinkedIn. Mario responde com ajustes (a ponte regenera via API,
reenvia no mesmo thread) ou aplica `_COPY_OK`.

## 10. Estado, idempotência, erros

- **State de produção**: um arquivo por artigo em `state/producao/<post_id>.json`.
  Chave de idempotência = `post_id` do WordPress. Artigo já com state não é
  reprocessado.
- **Estados**: `aguardando_revisao_copy → copy_aprovada → peca_montada`; ramos
  `erro`.
- **Retry**: `tenacity` 3x exponencial em falhas de API (Anthropic, WP).
- **Erro**: após falha, label `_ERRO` + email de alerta no thread.
- **DRY_RUN**: na produção, a chamada de API e a renderização rodam de verdade
  (é o que se quer testar); o `DRY_RUN` continua valendo só na publicação final,
  no pipeline existente.
- **Log**: JSONL, reusa `logger.py`.

## 11. Pré-requisitos do Mario

- Criar a chave de API Anthropic + adicionar crédito + definir limite de gasto
  mensal — **feito** (`ANTHROPIC_API_KEY` no `.env`)
- Criar a categoria **"Fila Social"** no WordPress
- (Claude instala Playwright + Chromium no venv)
- (Claude roda `setup_labels_producao.py` para criar as labels)

## 12. Ordem de implementação

1. `config.py` + `.env` (Anthropic, categoria) · `labels.py` (labels de produção) ·
   `setup_labels_producao.py`.
2. `wp_source.py` — leitura da Fila Social.
3. `article_styler.py` + `templates/artigo-noviello.html`.
4. `anthropic_client.py` — geração de copy (carrossel + LinkedIn).
5. `templates/slide-carrossel.html` + `carousel_render.py` (Playwright).
6. `producer.py` etapa A (produzir rascunho + email `[Revisar copy]`) +
   `producer_state.py` + `templates/email-revisar-copy.html`.
7. `producer.py` etapa B (detectar `_COPY_OK` → renderizar → montar MANIFEST).
8. Ajuste `publishers/wordpress.py` (modo publicar-rascunho-existente) + `manifest.py`.
9. `install_tasks.ps1` — 3ª tarefa · teste end-to-end com um dos 5 artigos reais.

## 13. Testes

`pytest` na lógica pura: estilização do artigo (HTML cru → template), parsing da copy
JSON da API, montagem do MANIFEST, detecção de decisão no thread de revisão. Clientes
de API (Anthropic, WP) com testes de fumaça. Teste end-to-end com um artigo real da
Fila Social, em `DRY_RUN`.
