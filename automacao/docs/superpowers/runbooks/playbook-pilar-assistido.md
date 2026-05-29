# Playbook do Pilar Assistido (modelo editorial oficial)

**Decidido em 2026-05-29.** Modelo de produção do conteúdo editorial da Noviello.

## O modelo

**Assistido sob demanda.** O Mario aciona o Claude Code quando quer produzir o
pilar da semana; o Claude gera o pacote completo, agenda e automatiza a
publicação. O Mario revisa antes de ir ao ar (gate de qualidade jurídica/OAB).

Por que assistido e não backlog antecipado nem autônomo total:
- **Backlog antecipado** exige manter estoque de rascunhos — trabalho recorrente
  que o escritório solo não sustenta (o backlog esvazia).
- **Autônomo total** geraria conteúdo jurídico sem revisão prévia — risco com a
  OAB. Conteúdo de advogado precisa do aval do responsável técnico.
- **Assistido** elimina a dor (o Claude produz, não o Mario) e mantém a revisão.

O Google Calendar "Noviello — Marketing" já tem os pilares nas descrições dos
eventos `[NOV-MKT]` / `[NOV-BLOG]` e lembra o Mario nos horários. Não precisa de
cadência automática.

## Gatilho

Mario diz algo como: *"produz o pilar [tema] da semana X"*. O tema vem da
descrição do evento do calendário (ex: "Pilar da semana: ITBI LC 227 + Ata
Notarial").

## Fluxo (o que o Claude executa)

1. **Pesquisa factual** (web_search/WebFetch) — confirmar a base normativa antes
   de escrever. Anti-alucinação: nunca inventar lei/jurisprudência. Registrar
   fontes verificadas. Se a norma não confirmar, parar e pedir material ao Mario.

2. **Artigo-âncora** via skill `noviello-blog-editor-chefe` (+ articulista quando
   Imobiliário/Urbanístico/Sucessório/Tributário). Renderizar no template
   `templates/artigo-noviello.html`. Regras fixas: sem travessões, sem emojis no
   corpo, voz ativa, "você" no blog principal, box ⚖ Saiba que e 📖 Exemplo.
   Logo branco no hero. **Sem imagem destacada no corpo** (ver item 6).

3. **Capa** (card 1200x630) no DNA da marca: gradiente claret→chocolate, logo
   branco no rodapé, Cinzel/Poppins. **Dourado SÓ como filete** (linhas finas),
   nunca em textos/chips/botões — resto nas cores do manual (Claret #68192E,
   Chocolate Cosmos #540D1D, Anti-flash White #F1F3F2 + creme/branco). Renderizar
   via Playwright HTML→JPG. Serve como `og:image` (compartilhamento).

4. **LinkedIn** (B2B): texto puro, sem "Direito Sênior", máx 3 hashtags, hook nos
   primeiros ~210 chars, sem travessões/asteriscos/emojis. Publisher
   `linkedin.py` modo texto (`formato: "texto"`). **Link vai no comentário —
   manual** (a API de comentário do LinkedIn é bloqueada por permissão, 403).

5. **Compliance OAB 205/2021** — rodar `verificador-de-etica-oab-em-publicidade`
   no artigo + LinkedIn antes de qualquer publicação.

6. **Agendar no WordPress** via REST API: `status=future`, `date` (hora BRT),
   `categories`, `slug`, `excerpt`. **`featured_media=0`** — o artigo já tem hero
   próprio; imagem destacada duplica a capa. Subir a capa como mídia e deixá-la
   só como `og:image` (compartilhamento), fora do corpo.

7. **Automatizar a publicação**: tarefa agendada pontual no Windows no horário do
   pilar que (a) garante o blog publicado (força `publish` se o WP-cron atrasar),
   (b) posta o LinkedIn (texto puro), (c) envia email de confirmação, (d)
   auto-remove. Padrão em `samples/_publicar_li_itbi.py`.

8. **Registrar no anti-duplicata** (`publicacoes_unicas`): chave `wp:<id>` +
   `processo:<X>` se o artigo citar processo. Evita republicação cross-canal.

## Apresentação ao Mario antes de publicar

Enviar por email (capa embutida + anexos: artigo HTML, capa, preview, LinkedIn,
metadados) e aguardar o "ok". Só agendar/publicar após o aval — ele é o
responsável técnico (OAB/SP 370.796).

## Referência de execução

O ciclo ITBI LC 227 (29/05/2026) é o exemplo de referência: pasta
`producao/artigo-itbi-lc227-ata-notarial/` + commits `54477e3`..`4cb0907`.

## Cadência automática

**Desativada** (modelo assistido não a usa). A tarefa `Noviello-Cadencia`
permanece registrada mas desabilitada — reativar só se um dia adotar o modelo
backlog antecipado. O `Noviello-Backup` segue ativo (diário).
