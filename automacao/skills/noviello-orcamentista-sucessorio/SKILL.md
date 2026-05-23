---
name: noviello-orcamentista-sucessorio
description: Orçamentista de inventário e planejamento sucessório da Noviello Advocacia. Use para orçamentos de inventário (judicial, extrajudicial, cumulativo art. 672 CPC), doações, ITCMD em SP, honorários sucessórios, Mandado de Segurança, cálculo de acréscimos legais (multa/correção/juros) quando óbito supera 60 dias.
---

# Orçamentista Sucessório — Noviello Advocacia

Especialista em orçamento de inventários, doações e planejamento sucessório com bens imóveis em São Paulo. Produz orçamentos formais em Word sobre o papel timbrado oficial do escritório.

---

## 1. REGRA CRÍTICA — HONORÁRIOS

### Fórmula universal
**Honorários advocatícios = 4% × Valor Venal (VV) do imóvel**

### Pacote completo em inventário com Mandado de Segurança
Quando o caso envolver inventário + MS para redução do ITCMD:

**4% × VV total é o PACOTE COMPLETO** — cobre inventário extrajudicial + Mandado de Segurança + redução do ITCMD em TODAS as sucessões envolvidas.

**NUNCA separar em "honorários do inventário + honorários do MS".** É um serviço único integrado, entregue em uma escritura única com um MS único.

### Base de cálculo em inventário cumulativo
Em inventário cumulativo (art. 672 CPC) com múltiplas sucessões sobre o MESMO imóvel, a base dos honorários = **100% do VV do imóvel como um todo**, não frações. O raciocínio: a escritura é única, o MS é único, o serviço é integrado.

### Forma de pagamento padrão (inventário)
- **30% de sinal** na assinatura do contrato
- **70% na conclusão** da escritura pública
- Honorários de êxito opcionais: **20% sobre economia tributária** obtida no MS

---

## 2. REGRA CRÍTICA — DOCUMENTO DE ORÇAMENTO

**TODO orçamento produzido por esta skill DEVE ser entregue em arquivo Word (.docx) construído SOBRE o papel de carta oficial do escritório.**

### Workflow obrigatório

```bash
# 1. Instalar fontes oficiais (se ainda não instaladas no sistema)
mkdir -p ~/.fonts && cp assets/fonts/*.ttf ~/.fonts/ && fc-cache -f ~/.fonts/

# 2. Desempacotar o papel de carta (preserva header com logo + footer com contato)
python /mnt/skills/public/docx/scripts/office/unpack.py \
  assets/papelaria/papel-de-carta-padrao.docx unpacked/

# 3. Editar APENAS word/document.xml — injetar conteúdo do orçamento no body
#    (header1.xml e footer1.xml ficam intocados)

# 4. Reempacotar validando
python /mnt/skills/public/docx/scripts/office/pack.py \
  unpacked/ orcamento_NOME.docx --original assets/papelaria/papel-de-carta-padrao.docx

# 5. Converter para PDF para envio ao cliente
python /mnt/skills/public/docx/scripts/office/soffice.py \
  --headless --convert-to pdf orcamento_NOME.docx
```

### Regras XML críticas para não dar erro na validação
- Ordem em `<w:pPr>`: `pStyle` → `keepNext` → `pageBreakBefore` → `pBdr` → `shd` → `spacing` → `ind` → `jc` → `rPr`
- Ordem em `<w:tcPr>`: `tcW` → `gridSpan` → `tcBorders` → `shd` → `tcMar` → `vAlign`

### Estrutura padrão do orçamento (4 páginas A4)

**Página 1 — Apresentação:**
- Título "ORÇAMENTO" em Cinzel claret 24pt com border-bottom claret
- Subtítulo descritivo do caso em itálico
- Bloco DESTINATÁRIO: nome, imóvel, matrícula, herdeiros, VV, VVR
- Seção APRESENTAÇÃO (prosa explicando o caso e a estratégia)
- Seção OBJETO DOS SERVIÇOS (bullets quadrados claret)

**Página 2 — Orçamento Detalhado:**
- Tabela 1: ITCMD por sucessão (base s/MS, c/MS, ITCMD s/MS, c/MS)
- Tabela 2: Composição do Investimento (cenário s/MS × c/MS)
- Linha total destacada em Chocolate Cosmos `#540D1D`
- Caixa RECOMENDAÇÃO em claret com valor final grande em Cinzel

**Página 3 — Honorários + Pagamento:**
- Tabela HONORÁRIOS ADVOCATÍCIOS com numerais Cinzel grandes
- **IMPORTANTE:** linha única descrevendo o pacote completo (NÃO separar inventário/MS)
- Seção FORMA DE PAGAMENTO: 30% sinal + 70% conclusão
- Facilidades de cartão no Tabelionato/RI
- À vista obrigatório para ITCMD + custas processuais
- Seção HONORÁRIOS DE ÊXITO: 20% sobre economia

**Página 4 — Condições + Aceitação:**
- Condições Gerais (bullets)
- Seção ACEITAÇÃO
- Linha de assinatura Dr. Mario Luiz Noviello Junior — OAB/SP 370.796

---

## 3. CÁLCULO DE ITCMD-SP

**Alíquota:** 4%

**Base de cálculo:**
- **Sem MS:** Valor Venal de Referência (VVR) — fornecido pela SEFAZ-SP
- **Com MS:** Valor Venal (VV) — IPTU municipal, geralmente ~20% menor que VVR

**Em inventário cumulativo (duas sucessões sobre o mesmo imóvel):**
- Cada sucessão incide sobre sua fração (ex: ½ e ½)
- ITCMD calcula-se sobre cada fração separadamente
- Ex: VV total R$ 598.432 → cada sucessão incide sobre R$ 299.216 → ITCMD por sucessão = R$ 11.968,64 (com MS)

**Mandado de Segurança único:**
Impetrado para reduzir a base de cálculo do ITCMD em TODAS as sucessões do mesmo processo. Custas processuais = **8 UFESPs** (3 OJ + 5 custas).

**UFESP 2026 = R$ 38,42** → MS = R$ 307,36

---

## 3-B. ACRÉSCIMOS LEGAIS SOBRE O ITCMD (Lei 10.705/2000)

**REGRA CRÍTICA:** Sempre perguntar a data do óbito de cada autor da herança e aplicar os acréscimos legais quando aplicável.

### Fato gerador
A abertura da sucessão (data do óbito), pelo princípio da saisine (art. 1.784 CC).

### Multa por atraso (art. 21, I)

| Prazo entre óbito e abertura do inventário | Multa |
|---|---|
| Até 60 dias | 0% |
| 61 a 180 dias | **10%** (escala legal) |
| Acima de 180 dias | **20%** |

### Correção monetária (art. 15)
Pela variação da UFESP desde o óbito até o pagamento.

### Juros de mora (art. 20)
SELIC acumulada após 180 dias. Em orçamentos projetivos, usar **1% ao mês** como estimativa conservadora.

### Estratégias Noviello

**Estratégia conservadora (PADRÃO para orçamentos projetivos):** quando o óbito já supera 60 dias, aplicar 20% de multa + correção UFESP + juros 1%/mês, protegendo o cliente de surpresas.

**Estratégia rigorosa:** seguir exatamente a escala legal (0%/10%/20%).

### Ferramenta

Use `scripts/calculadora_acrescimos.py`:

```python
from calculadora_acrescimos import calcular_acrescimos_itcmd

resultado = calcular_acrescimos_itcmd(
    data_obito="2024-08-20",
    itcmd_base=23937.28,     # ITCMD original (VV × 4%)
    data_pagamento="2026-07-15",  # opcional, default = hoje
    estrategia="conservadora",    # ou "rigorosa"
)
print(resultado["itcmd_total"])  # R$ 35.666,70
```

### Atenção — Cancelamento de Usufruto
O cancelamento do usufruto por óbito do usufrutuário **NÃO é fato gerador de ITCMD** (é consolidação da propriedade em favor do nu-proprietário). **Não se aplicam multa, correção ou juros sobre o cancelamento.**

### Integração no Orçamento

Quando houver acréscimos, adicionar linha na Composição do Investimento:
```
| Acréscimos legais sobre o ITCMD (multa + correção + juros) | R$ X.XXX,XX | R$ X.XXX,XX |
```

E nota técnica de rodapé explicando. Ver `references/calculo-acrescimos-itcmd.md` para detalhes completos.

---

## 4. EMOLUMENTOS CARTORÁRIOS SP (2026)

### Tabelionato de Notas — Escritura de Inventário
Base: valor da transmissão (VVR sem MS ou VV com MS)

| Faixa | Valor base (até R$) | Emolumentos |
|---|---|---|
| j | 300.000,00 | R$ 2.723,02 |
| l | 400.000,00 | R$ 4.176,24 |
| m | 500.000,00 | R$ 3.284,18 (RI) |
| n | 800.000,00 | R$ 3.846,10 (RI) |
| o | 800.000,00 | R$ 5.427,43 (notas) |
| p | 1.200.000,00 | R$ 6.026,36 (notas) |

**Em escritura cumulativa única** (art. 672 CPC): cada sucessão cobrada em sua faixa — NÃO soma os valores para escalonar. Economia real vem de:
- Honorários únicos (não dois contratos)
- MS único (não 2 × 8 UFESPs)
- Certidões compartilhadas (não duplicadas)
- Tempo processual único

### Registro de Imóveis — Tabela II ARISP 2026
Partilhas sucessivas respeitando a cadeia hereditária:
- Registro da 1ª partilha (tio → espólio mãe): na faixa da fração
- Registro da 2ª partilha (mãe → herdeiros finais): na faixa do acervo total
- Averbações sem valor (cancelamento usufruto): R$ 75,60

### Registro Civil (Tabela V) 2026
- **Certidão breve relato: R$ 46,35** (PADRÃO Noviello — suficiente na maioria dos casos)
- Certidão inteiro teor: R$ 92,98 (só se serventia exigir expressamente)
- Averbação acrescida: R$ 23,17
- Matrícula RI atualizada: R$ 79,16

---

## 5. CHECKLIST DOCUMENTAL PADRÃO

### Documentos dos herdeiros (para cada)
- Certidão de nascimento (herdeiros solteiros) — breve relato
- Certidão de casamento (herdeiros casados) — breve relato com averbações
- RG e CPF
- Comprovante de residência

### Documentos dos autores da herança (falecido)
- Certidão de óbito — breve relato
- Certidão de casamento — breve relato
- Certidões negativas federais, estaduais, municipais, trabalhistas

### Documentos do imóvel
- Matrícula atualizada (30 dias) — R$ 79,16
- Carnê IPTU atual
- Certidão de Valor Venal / Valor Venal de Referência (SEFAZ-SP)
- Certidão negativa de tributos municipais

### Fórmula de cálculo de custo documental
```
Subtotal certidões = nº certidões × R$ 46,35
Subtotal RI = nº imóveis × R$ 79,16
Subtotal bruto = certidões + RI
Buffer averbações (+20%) = subtotal × 0,20
TOTAL DOCUMENTOS = subtotal × 1,20
```

---

## 6. REGRAS DE ARREDONDAMENTO E FORMATAÇÃO

- Valores monetários: sempre R$ X.XXX,XX (duas casas decimais, ponto milhar, vírgula decimal)
- Percentuais: X% (sem casa decimal em %)
- Datas: dd/mm/aaaa ou "Cidade, dd de mês de aaaa" (extenso)

---

## 7. ESTRATÉGIAS ESPECIAIS

### Inventário cumulativo (art. 672 CPC)
**Requisitos (incisos I a III):**
- I — identidade de herdeiros
- III — dependência entre partilhas (herdeiro pré-morto, sucessões encadeadas)

**Jurisprudência confirmatória:** TJSP/CSM, Apel. 1003972-10.2024.8.26.0037 (2025).

**Benefícios:**
- Uma única escritura pública
- Um único MS (não um por sucessão)
- Honorários integrados (4% × VV total)
- Certidões compartilhadas
- Tempo processual drasticamente reduzido

### Doação com reserva de usufruto
- Base ITCMD nua-propriedade = 2/3 do valor
- Base ITCMD extinção usufruto = 1/3 do valor
- Base inventário/partilha futura = 100%

### Cancelamento de usufruto por óbito
- Averbação simples no RI: R$ 75,60 (sem escritura autônoma quando integrado à escritura de inventário cumulativo)
- Em escritura separada: escritura sem valor declarado R$ 615,30

---

## 8. EXEMPLOS CALCULADOS (referência)

### Ex: Inventário cumulativo de imóvel em SP
Dados: VV R$ 598.432 | VVR R$ 769.291 | 2 sucessões sobre o mesmo imóvel

**ITCMD:**
- s/MS: 2 × (VVR × 50% × 4%) = 2 × R$ 15.385,82 = R$ 30.771,64
- c/MS: 2 × (VV × 50% × 4%) = 2 × R$ 11.968,64 = R$ 23.937,28

**Emolumentos Tabelionato (cumulativa):**
- s/MS: faixa o + faixa p = R$ 5.427,43 + R$ 6.026,36 = R$ 11.453,79
- c/MS: faixa l + faixa o = R$ 4.176,24 + R$ 5.427,43 = R$ 9.603,67

**Registros RI (partilhas sucessivas):**
- s/MS: R$ 3.284,18 + R$ 3.846,10 + R$ 75,60 (averb.) = R$ 7.205,88
- c/MS: R$ 2.723,02 + R$ 3.284,18 + R$ 75,60 = R$ 6.082,80

**MS único:** 8 × R$ 38,42 = R$ 307,36

**Honorários (pacote completo):** 4% × R$ 598.432 = **R$ 23.937,28**

**INVESTIMENTO TOTAL:**
- s/MS: R$ 73.852,92
- c/MS: R$ 64.352,72
- **Economia líquida: R$ 9.500,20**

---

## 9. ARQUIVOS E ASSETS DESTA SKILL

| Asset | Caminho | Uso |
|---|---|---|
| Papel de Carta | `assets/papelaria/papel-de-carta-padrao.docx` | **BASE OBRIGATÓRIA** de todo orçamento |
| Logos oficiais | `assets/logos/` | Versões branco e greyscale |
| Fontes oficiais | `assets/fonts/` | Cinzel + Poppins (instalar antes de gerar PDF) |
| Tabelas emolumentos | `references/tabela-emolumentos-sp.md` | ARISP 2026 + Notas 2026 |
| Cálculo de acréscimos ITCMD | `references/calculo-acrescimos-itcmd.md` | Regras completas Lei 10.705/00 |
| Calculadora Python | `scripts/calculadora_acrescimos.py` | Função `calcular_acrescimos_itcmd()` |

---

## 10. ATUALIZAÇÃO ANUAL (janeiro de cada ano)

No início de cada ano, verificar e atualizar:
- [ ] UFESP do novo ano (Comunicado DICAR)
- [ ] Tabela ARISP (Tabelionato de Notas e Registro de Imóveis)
- [ ] Tabela V do Registro Civil
- [ ] Alíquotas do ITCMD (se houver reforma estadual)
- [ ] Valor Venal de Referência (pode ser revisto pela SEFAZ-SP)

---

## 11. ARMADILHAS FREQUENTES

❌ **Separar honorários em inventário + MS** — é pacote único  
❌ **Calcular honorários sobre fração ideal** em vez de 100% do VV — em inventário cumulativo, base é o imóvel todo  
❌ **Criar layout de orçamento alternativo** — sempre papel de carta oficial  
❌ **Esquecer o cancelamento do usufruto** quando há usufrutuário falecido — averbação R$ 75,60  
❌ **Usar certidão inteiro teor** como padrão — breve relato (R$ 46,35) é suficiente na maioria dos casos  
❌ **Somar valores de sucessões** para escalonar a faixa do Tabelionato — cada sucessão em sua faixa  
❌ **Calcular 2 × custas de MS** em inventário cumulativo — MS é único  
❌ **Renderizar PDF sem instalar as fontes Cinzel/Poppins** no sistema antes  
❌ **Esquecer os acréscimos legais do ITCMD** quando o óbito supera 60 dias — multa, correção UFESP e juros 1%/mês (ver seção 3-B)  
❌ **Aplicar multa/juros no cancelamento de usufruto** — não há fato gerador de ITCMD na consolidação da propriedade pela morte do usufrutuário

---

## 12. INTEGRAÇÃO COM OUTRAS SKILLS

- **Carregue junto:** `noviello-imobiliario-inventario-imoveis` (para aspectos jurídicos do inventário)
- **Se envolver regularização:** `noviello-imobiliario-regularizacao-reurb`
- **Para peças textuais do inventário:** `noviello-imobiliario-contratos-minutas`
- **Para análise de riscos:** `noviello-imobiliario-master`
