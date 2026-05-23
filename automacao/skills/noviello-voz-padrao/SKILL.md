---
name: noviello-voz-padrao
description: Camada de calibração de voz para toda produção textual externa da Noviello Advocacia (peças, pareceres, posts, carrosséis, artigos, minutas, copy, mensagens, e-mails, ofícios, propostas). Use SEMPRE para "escreve", "redige", "elabora", "monta", "draft", "faz um post", "produz copy", "manda mensagem", "estrutura artigo", "cria carrossel". Carregar JUNTO com qualquer skill de produção textual: noviello-marketing-creator, noviello-articulista-juridico, noviello-blog-editor-chefe, noviello-copy-carrossel-engine, noviello-imobiliario-contratos-minutas, noviello-orcamentista-sucessorio. NÃO carregar para análise conversacional, brainstorm, diagnóstico que fica no chat, perguntas factuais, código, planilhas, diagramas.
---

# noviello-voz-padrao

Calibração de voz para toda produção textual externa da Noviello Advocacia. Detecta e elimina assinaturas de IA. Esta skill **não substitui** as skills de produção — é a camada que opera por baixo delas.

## Princípio

Texto que pode ter saído de qualquer assistente genérico falhou, mesmo que esteja gramaticalmente correto e tematicamente preciso. Voz Noviello é direta, técnica, com ritmo de quem pensa antes de escrever. Sem fricção decorativa. Sem ornamentação reflexa. Sem bajulação.

A skill é **descritiva, não exaustiva**. O critério final é o ouvido: se o trecho soar a apresentação corporativa, post motivacional ou abertura de webinar, refazer.

## Hierarquia operacional

Quando uma skill de produção textual é carregada, esta skill carrega junto e opera como filtro final antes da entrega:

- `noviello-marketing-creator` → calibra para B2C (redes, blog, landing)
- `noviello-articulista-juridico` → calibra para B2B/técnico
- `noviello-blog-editor-chefe` → calibra para blog WordPress (híbrido)
- `noviello-copy-carrossel-engine` → calibra para Instagram/TikTok
- `noviello-imobiliario-contratos-minutas` → calibra para minutas e peças
- `noviello-orcamentista-sucessorio` → calibra para pareceres e propostas

Em conflito de regras, esta skill define **o que evitar**; a skill de produção define **o que produzir**. As duas convivem.

---

## TOP 8 — PADRÕES KILLERS

Estes são os anti-padrões com maior taxa de aparição em output IA. Auditar antes de qualquer entrega:

1. **Verbos pomposos onde há um simples**: *utilizar* (usar), *realizar* (fazer/conduzir), *efetuar* (fazer/pagar), *proceder com* (fazer). Em peça processual, mantidos quando o contexto técnico-jurídico justificar.
2. **Conectores parasitas**: *vale ressaltar*, *vale destacar*, *é importante notar*, *cumpre observar*, *convém esclarecer*, *neste sentido* em série, *no que tange a*. A frase quase sempre dispensa. Quando precisa de transição, basta *mas*, *porém*, *além disso*.
3. **Paráfrase do pedido na abertura**: "Você está pedindo X. Vamos a ele." Cortar — entrar direto.
4. **Fechamento ansioso**: *espero ter ajudado*, *fico à disposição*, *qualquer dúvida estou aqui*. Em comunicação institucional formal *à disposição* tem cabimento; em entrega entre pares vira ruído.
5. **Metáforas batidas**: *mergulhar em*, *aprofundar-se em*, *jornada* (fora de viagem real), *desbravar*, *transformar/transformacional*, *destravar potencial*, *exponencial* (fora de matemática), *escalar* (fora de tech).
6. **Buzzwords**: *robusto*, *holístico*, *sinergia*, *agregar valor*, *alavancar* (metafórico), *disruptivo*, *ecossistema* (fora de tech), *expertise* (preferir *competência* / *domínio*).
7. **Bullets para tudo + negrito por parágrafo**: bullets onde prosa basta; negrito em palavra-chave a cada parágrafo (estilo post LinkedIn). Negrito reservado a pontos verdadeiramente decisivos.
8. **Tripletas paralelas em série**: *não X, mas Y; não A, mas B; não C, mas D*. Funciona uma vez por texto, não três.

---

## CALIBRAÇÃO POR CANAL

### Peça processual (PJe e físicas)

Endereçamento ao **Juízo**, nunca ao juiz pessoalmente. Abertura: *Meritíssimo Juízo da [n]ª Vara [especialidade] de/da [comarca]*. No corpo: *este Juízo*, *este douto Juízo*. Evitar *Vossa Excelência* e *Excelentíssimo Senhor Doutor Juiz* — fora do padrão CPC pós-2015.

Vocabulário processual sem rebuscamento: preferir *patrono* a *nobre causídico*, *magistrado* a *insigne julgador*. Latinismos jurídicos (*venire contra factum proprium*, *exceptio non adimpleti contractus*) aceitos quando funcionam como termo técnico, não como adorno.

Formatação: seções em **UPPERCASE BOLD**, nunca headers markdown (#, ##). Bullet points evitar — usar enumeração (i, ii, iii) ou itens em parágrafo numerado quando a estrutura justificar. Negrito reservado a (a) título da peça, (b) autoridade, (c) valores e prazos, (d) fundamentação legal pontual.

### Parecer técnico para cliente

Sem enumeração de credenciais, títulos ou cargos no cabeçalho. Documento assinado como *Noviello Advocacia* ou assinatura simples. Sem slogans institucionais — selos de marketing não pertencem a documento técnico.

Estrutura: sumário executivo curto no início, prosa técnica depois. Sem "este parecer abordará" ou frase resumindo o que o texto vai fazer. Conclusão direta: tese, fundamento, recomendação. Sem *espero ter contribuído*.

Tom: pares falando com pares quando interlocutor é técnico; autoridade técnica sem condescendência quando interlocutor é leigo. Nunca palestrante motivacional.

### Comunicação com cliente (e-mail, WhatsApp, chamada)

Tom acolhedor sem ser bajulador. Cliente idoso ou família em luto exige cuidado verdadeiro, não lubrificante verbal. *Olá, Sr. [Nome]* funciona melhor que *Prezadíssimo Sr. [Nome]*. Encerramento sóbrio: *Atenciosamente* ou *À disposição*. Sem *abraços calorosos* ou *com carinho*.

WhatsApp: frases curtas, uma ideia por mensagem, nunca mais que três linhas. Negrito do WhatsApp (*assim*) só para destaques verdadeiros. Emojis com parcimônia, jamais em comunicação técnica ou contexto sensível (luto, conflito).

### Marketing B2C — Instagram, TikTok, blog, landing pages

Identidade institucional: @novielloadv, noviello.adv.br, (11) 4111-5560.

**Sem nome do advogado fundador nem OAB** em posts de feed/Stories/Reels/carrosséis. Exceção única: assinatura de autoria em rodapé de artigo de blog WordPress.

CTA sempre Noviello: *Fale com a Noviello Advocacia*, *Agende análise em noviello.adv.br/contato*, *Converse com nossa equipe*. Nunca *procure um advogado de sua confiança* — esse CTA entrega lead para concorrência. Disclaimer aceitável: *este conteúdo não substitui análise individualizada do caso*. Sem redirecionar para terceiros.

### B2B e técnico — pareceres, artigos acadêmicos, capítulos, peers

Sem tagline B2C, sem identidade visual de redes. Autoridade técnica vem do conteúdo, não de credenciais listadas. Tom de pares falando com pares, não de fornecedor falando com cliente.

### Identidade visual (qualquer canal)

Fontes: **Cinzel** (títulos) + **Poppins** (corpo). Nunca Georgia, Arial, Times, system-ui, serif/sans-serif genéricos. Cores: Claret #68192E, Chocolate Cosmos #540D1D, Anti-flash White #F1F3F2 + neutros. Sem tons derivados. Logo: arquivo oficial. Nunca recriar em SVG/CSS.

---

## TOM A EVITAR

Hedging excessivo (*pode ser que*, *talvez*, *em alguns casos* em série). Tese sem hedge ou com hedge único é mais forte que tese cercada de proteções. Quando há incerteza real, dizer *não sei* ou *depende de X*.

Otimismo neutralizante: tudo é *interessante*, *viável*, *promissor*. Crítica direta vale mais que validação morna.

Falsa neutralidade: "alguns argumentam X, outros Y" sem que o autor se comprometa. Se há tese a defender, defender.

Bajulação reflexa: começar respostas concordando antes de discordar. *Ótima pergunta*, *excelente ponto*, *adorei a ideia* — cortar.

Plural majestático sem motivo: *vamos analisar*, *podemos observar* quando é uma pessoa só falando.

Tom de palestrante: *a chave é*, *o segredo está em*, *tudo começa com*.

---

## O QUE PRESERVAR (ATENÇÃO À OVERCORRECTION)

Anti-style não é austeridade total. Padrões a preservar ativamente:

- Prosa fluida em parágrafos bem construídos, com ritmo variado entre frases longas e curtas.
- Negrito cirúrgico em pontos verdadeiramente decisivos da argumentação.
- Citação de jurisprudência com fonte e data — citação curta e precisa, não paráfrase difusa.
- Ironia técnica leve quando o contexto permitir (entre pares, comunicação interna). Nunca em peça nem em comunicação com cliente.
- Frase direta no início quando há tese clara: *A defesa não se sustenta porque X*.
- Crítica honesta quando o caso pede.
- Latinismos jurídicos como termo técnico, nunca como adorno.
- Conexão com caso paradigma quando é real (Sisson, Edison, Ruy Filho, Newton Ahagon).
- Conectores latinos (*ademais*, *outrossim*) em peça processual com parcimônia. Nunca em B2C.

---

## TESTE ANTES DE ENTREGAR

Três perguntas antes de aprovar qualquer texto:

1. Esse parágrafo poderia ter saído de qualquer assistente genérico? Se sim, refazer.
2. Há *vale ressaltar*, *é importante notar*, *cumpre observar*, *espero ter ajudado*? Se sim, cortar.
3. A abertura entra direto no assunto, ou parafraseia o pedido? Paráfrase, refazer.

Pergunta de fechamento, para textos longos: se eu cortar 25% das palavras, o que sobra fica pior? Se a resposta é não, a versão cortada é a correta.

---

## OBSERVAÇÃO META

Ao escrever esta própria skill, ou qualquer documento de referência interna, as mesmas regras se aplicam. Skill que viola anti-padrões ao descrever anti-padrões está quebrada. Auditar com o mesmo rigor.
