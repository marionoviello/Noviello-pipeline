# Acréscimos Legais sobre o ITCMD — SP (Lei 10.705/2000)

## Base Legal
- **Lei Estadual 10.705/2000** — institui o ITCMD
- **Art. 15** — atualização monetária desde a data do óbito
- **Art. 17, § 1º** — prazo de recolhimento até 180 dias da abertura da sucessão
- **Art. 20** — juros de mora pela taxa SELIC quando ultrapassado o prazo
- **Art. 21, I** — multa por atraso na abertura do inventário

## Fato Gerador
O ITCMD tem como fato gerador **a abertura da sucessão** (data do óbito), por força do princípio da *saisine* (art. 1.784 do CC). Todos os acréscimos são contados a partir dessa data.

## Regra de Multa (art. 21, I)

| Prazo entre óbito e abertura do inventário | Multa sobre o ITCMD |
|---|---|
| Até 60 dias | **0%** (sem multa) |
| De 61 a 180 dias | **10%** |
| Acima de 180 dias | **20%** |

## Correção Monetária (art. 15)
Base de cálculo atualizada pela variação da **UFESP** desde o dia seguinte ao óbito até o pagamento.

Fórmula:
```
Base atualizada = Base original × (UFESP do mês de pagamento / UFESP do mês do óbito)
```

## Juros de Mora (art. 20)
Incidem quando o recolhimento ocorrer **após 180 dias** do óbito, calculados pela **taxa SELIC** acumulada no período.

**Simplificação adotada pela Noviello Advocacia em orçamentos projetivos:**
Aplicar **1% ao mês** (taxa conservadora próxima à SELIC média recente) sobre o ITCMD atualizado, contados desde o 181º dia do óbito.

**Nota ao cliente:** a taxa real a ser cobrada pela SEFAZ é a SELIC acumulada; o orçamento usa 1%/mês como estimativa conservadora para evitar surpresas.

## Política Noviello para Orçamentos

Mario pode adotar **duas estratégias**:

### Estratégia A — Rigorosa (conforme escala legal)
- 0–60 dias: sem acréscimos
- 61–180 dias: +10% multa + correção UFESP
- \>180 dias: +20% multa + correção UFESP + juros 1%/mês

### Estratégia B — Conservadora (padrão Noviello em orçamentos projetivos)
Quando o óbito já tem mais de 60 dias na data do orçamento:
- **+20% de multa** (mesmo entre 60–180 dias, para proteger o cliente de aumento futuro)
- **+ correção monetária UFESP**
- **+ juros de 1% ao mês** desde o óbito

A estratégia conservadora é recomendada quando:
- O óbito já tem mais de 60 dias na data do orçamento
- Há risco de o recolhimento ultrapassar 180 dias (bastante comum em inventários extrajudiciais com múltiplas sucessões)
- O cliente prefere não ter surpresas futuras

## Como Calcular

### Entrada
- `data_obito` — data do falecimento
- `itcmd_base` — ITCMD calculado sobre a base (VVR sem MS ou VV com MS) atualizada
- `data_projetada_pagamento` — estimativa de quando o imposto será recolhido (padrão: data do orçamento + 90 dias, ajustável)
- `estrategia` — "rigorosa" ou "conservadora"

### Saída
- `dias_desde_obito` — inteiro
- `multa` — valor em R$
- `correcao_monetaria` — valor em R$ (baseado na variação da UFESP)
- `juros_mora` — valor em R$
- `itcmd_total` — soma do imposto + acréscimos
- `nota_explicativa` — texto para inclusão no orçamento

## Exemplo de Cálculo

**Dados:**
- Óbito: 15/03/2024
- Data projetada de pagamento: 15/07/2026 (~853 dias após o óbito)
- ITCMD base: R$ 23.937,28 (com MS)
- UFESP 2024: R$ 35,36 | UFESP 2026: R$ 38,42
- Estratégia: conservadora

**Cálculo:**
```
Dias: 853 (muito acima de 180)
Multa: R$ 23.937,28 × 20% = R$ 4.787,46
Correção UFESP: R$ 23.937,28 × (38,42/35,36 - 1) = R$ 2.070,95
Juros (1%/mês × 28 meses): R$ 23.937,28 × 28% = R$ 6.702,44
ITCMD Total: R$ 37.498,13 (R$ 13.560,85 de acréscimos)
```

## Registro no Orçamento

Quando houver acréscimos, adicionar linha no **Orçamento Detalhado** da composição do investimento:
```
| Acréscimos legais sobre o ITCMD (multa + correção + juros) | R$ X.XXX,XX | R$ X.XXX,XX |
```

E uma **nota técnica de rodapé** explicando o cálculo:
> *Acréscimos legais aplicados nos termos dos arts. 15, 17 §1º, 20 e 21 da Lei 10.705/2000. Multa de X% pelo atraso superior a X dias; correção monetária pela variação da UFESP; juros de 1% ao mês (estimativa conservadora baseada na SELIC). A Fazenda Estadual aplicará a SELIC efetiva no momento do recolhimento.*

## Tratamento Diferente para Cancelamento de Usufruto

**Atenção:** O cancelamento do usufruto por óbito do usufrutuário **NÃO é fato gerador de ITCMD**, pois se trata de simples consolidação da propriedade em favor do nu-proprietário (ato previsto na escritura/registro original de constituição do usufruto). Portanto, **não há multa, correção ou juros sobre o cancelamento do usufruto**.
