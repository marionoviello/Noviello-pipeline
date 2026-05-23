# Compliance OAB pré-publicação — checklist

## Base normativa
- **Provimento OAB 205/2021** — Publicidade na advocacia
- **Recomendação CFOAB 001/2024** — Uso de IA em peças e materiais

## Princípios fundantes (Prov. 205/2021)

| Princípio | O que significa na prática |
|-----------|---------------------------|
| Informação objetiva | Sem promessa de resultado nem garantia de êxito |
| Discrição | Sem captação inadequada, sem mercantilização da advocacia |
| Sobriedade | Sem expressões pejorativas, sensacionalistas, autoelogiosas, ou que sejam exageradas |
| Veracidade | Apenas informação verdadeira, comprovável |
| Vedação ao engano | Não pode induzir o consumidor a erro |

## Vedações expressas (Prov. 205 art. 7º)

| Vedado | Exemplo do que NÃO fazer |
|--------|--------------------------|
| Promessa de resultado | "Conseguimos sua aposentadoria em 30 dias" |
| Garantia de êxito | "Você vai ganhar a causa" |
| Convocação para causa coletiva | "Junte-se aos lesados pelo banco X" |
| Captação não-personalizada de cliente | Mensagens em massa para potenciais clientes |
| Vinculação a outros serviços/profissões | "Advocacia + contabilidade + consultoria" |
| Anúncio em outdoor / TV aberta com captação | (vedação histórica, com flexibilizações 205) |
| Concursos, sorteios, brindes | Qualquer mecânica que dependa de sorteio |
| Publicidade gratuita disfarçada de notícia | Press release sem identificar como advocacia |
| Indicação de valores de honorários a partir de | "Inventário a partir de R$ 500" |
| Comparação com outros profissionais | "Melhor escritório de SP" |

## Permitido (Prov. 205 art. 8º)

| Permitido | Exemplo aceitável |
|-----------|-------------------|
| Áreas de atuação | "Atuamos em Direito Imobiliário, Sucessório e Sênior" |
| Casos representativos sem identificar parte | "Atuamos em regularização fundiária" |
| Especializações e certificações | "OAB/SP 370.796, Coord. Núcleo Urbanístico Ad Notare" |
| Educação jurídica do público | "Como funciona o inventário extrajudicial" |
| Artigos técnicos | Os do blog Noviello |
| Boletins informativos | Newsletter da casa |
| Marketing de conteúdo | Carrosséis, Reels, posts educativos |

## Disclosure de IA (Recom. CFOAB 001/2024)

Quando aplicável:
- Conteúdo produzido com auxílio significativo de IA
- Avatar IA representando o advogado
- Voz clonada por IA (ElevenLabs)
- Imagens geradas por IA (Veo 3, Midjourney, DALL-E)
- Texto majoritariamente gerado por IA

Formato sugerido para Stories/post:
> "Conteúdo elaborado com auxílio de inteligência artificial e revisão técnica de Mario Noviello, OAB/SP 370.796."

Posicionamento:
- Rodapé do texto do post
- Ou primeiro slide do carrossel ("nota técnica")
- Ou primeiro Stories da sequência

## Checklist completo pré-publicação

```
COMPLIANCE PROV. 205/2021
[ ] Texto SEM promessa de resultado
[ ] Texto SEM garantia de êxito
[ ] Texto SEM captação direta a indivíduo identificado
[ ] Texto SEM convocação para causa coletiva
[ ] Texto SEM valores de honorários ("a partir de", tabela)
[ ] Texto SEM comparação com outros profissionais/escritórios
[ ] Texto SEM superlativos autoelogiosos ("o melhor", "líder", "número 1")
[ ] Texto SEM imitação de jornalismo (sem "notícia" disfarçada)
[ ] Texto SEM concurso, sorteio ou brinde

CONTEÚDO TÉCNICO
[ ] Citação de norma com número e ano correto
[ ] Sem fato jurídico inventado
[ ] Sem jurisprudência inexistente
[ ] Terminologia técnica adequada ao nicho
[ ] Tom respeitoso ao público-alvo

IDENTIFICAÇÃO
[ ] Marca "Noviello Advocacia" presente (logo)
[ ] OAB/SP 370.796 visível se houver foto/menção a Mario
[ ] Hashtags coerentes com o pilar

DISCLOSURE IA (se aplicável)
[ ] Texto de disclosure presente
[ ] Posição clara (rodapé / nota / primeiro slide)
[ ] Linguagem profissional, sem coloquialismos

ALT-TEXT
[ ] Alt-text por imagem (acessibilidade)
[ ] Alt-text descritivo do conteúdo, não da imagem em si
```

## Semáforo de revisão

| Cor | Status | Conduta |
|-----|--------|---------|
| 🟢 Verde | Tudo OK pelo Prov. 205 e Recom. 001/2024 | Publicar |
| 🟡 Amarelo | Ponto cinzento — pode ser interpretado de duas formas | Mario decide caso a caso; recomendado ajustar |
| 🔴 Vermelho | Violação clara (promessa, garantia, captação ostensiva) | TRAVAR publicação; corrigir antes |

## Casos cinzentos comuns no contexto Noviello

| Situação | Provável status | Como ajustar |
|----------|-----------------|--------------|
| "Você pode estar perdendo R$ X" | 🟡 | OK se for fato factual e linkado a fundamento; mas tom alarmista beira o sensacionalismo. Preferir versão educativa: "A lei prevê que..." |
| "Conheça 5 erros que produtores cometem" | 🟢 | OK — educação jurídica clássica |
| "Não cometa esse erro!" | 🟢 | OK se contextualizado |
| "Resolvemos seu inventário" | 🔴 | Promessa de resultado — não publicar |
| "Atuamos em inventário" | 🟢 | Área de atuação — permitido |
| "Mais de 500 clientes atendidos" | 🟡 | Aceito se verdadeiro e sem comparação; preferir não destacar |
| "Atendimento 24h" | 🔴 | Mercantilização — não publicar |
| "Especialista em..." | 🟢 | Se houver certificação/titulação que comprove |
| "Vamos ganhar essa causa juntos" | 🔴 | Promessa + captação coletiva |
| Carrossel "saiba seus direitos" | 🟢 | Educativo, clássico |
| Reels com Mario falando "se você caiu nesse golpe..." | 🟡 | OK se for educativo; vermelho se acabar em "clique aqui para ser cliente" |
| Mensagem de WhatsApp para lead identificado | 🟡 | Permitido se houver relacionamento prévio; vermelho se for prospecção fria |

## Quando carregar `verificador-de-etica-oab-em-publicidade`

A skill `verificador-de-etica-oab-em-publicidade` deve ser **sempre** consultada antes da publicação. Ela aplica o checklist acima com mais granularidade e devolve:
- Status (verde/amarelo/vermelho)
- Lista de pontos a corrigir
- Sugestão de reescrita quando aplicável

Esta skill (`noviello-publisher-instagram`) **NÃO publica** sem o aval da `verificador-de-etica-oab-em-publicidade`. É um gate inegociável.

## Documentação do compliance

Para cada publicação, registrar em `logs/compliance/{yyyy-mm-dd}/{pkg_id}.json`:

```json
{
  "pkg_id": "agro-2026-05-20",
  "oab_status": "verde",
  "oab_notes": "OK — sem promessa, sem garantia, tom educativo",
  "disclosure_ia": true,
  "disclosure_text": "Conteúdo elaborado com auxílio de IA...",
  "checklist_passed": ["promessa", "garantia", "captacao", "valores"],
  "reviewer": "verificador-de-etica-oab-em-publicidade",
  "reviewed_at": "2026-05-19T18:00:00Z"
}
```

Auditoria mensal cruza esses logs para identificar padrões e calibrar a skill de revisão.
