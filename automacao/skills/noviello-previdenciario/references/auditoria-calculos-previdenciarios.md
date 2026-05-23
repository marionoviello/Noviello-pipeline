# Auditoria de Cálculos Previdenciários — Manual Operacional Noviello

Esta é a reference mais importante da skill `noviello-previdenciario` para quem **audita cálculos**: cálculos do próprio INSS (carta de concessão), cálculos feitos por plataformas comerciais (Prévius/Lógike, Previdenciarista/Prev, Cálculo Jurídico/CJ) e simulações independentes.

**Princípio operacional:** o advogado previdenciário sério **nunca confia cegamente** no cálculo apresentado — nem do INSS, nem do software. Auditar significa rodar a lógica em cima dos dados-fonte (CNIS, carta, PPP, holerite) e identificar divergências.

---

## Sumário

1. Conceitos-base do cálculo previdenciário
2. Documentos-fonte e como lê-los
3. Atualização monetária — índices e regras
4. Fator previdenciário — fórmula completa
5. Plataformas comerciais — o que cada uma faz
6. Matriz de erros típicos do INSS
7. Matriz de erros típicos de plataformas
8. Checklist de auditoria — protocolo passo a passo
9. Revisões antigas — mapa por DIB (com status atual da Vida Toda)
10. Reafirmação da DER e melhor benefício
11. Fluxograma decisório completo
12. Output da auditoria

---

## 1. Conceitos-base do cálculo previdenciário

### 1.1 PBC — Período Básico de Cálculo

Conjunto de meses cujos salários-de-contribuição (SC) entram na média.

| Período | PBC |
|---|---|
| **Pré-Lei 9.876/99** (DIB até 28/11/1999) | Últimos **36 SC** apurados em até **48 meses** anteriores ao mês do afastamento/DER |
| **Pós-Lei 9.876/99** (DIB de 29/11/1999 a 12/11/2019) | Todas as contribuições desde **07/1994**, considerando **80% maiores** SC |
| **Pós-EC 103/2019** (DIB de 13/11/2019 em diante) | Todas as contribuições desde **07/1994**, considerando **100% das SC** (sem descarte) |

**Divisor mínimo (Lei 14.331/2022, art. 26-A introduzido pela Lei 14.331):** se o segurado tem **menos de 108 contribuições** no PBC, divide-se a soma por 108 (e não pelo número real de contribuições). Reduz a média artificialmente — tese impugnável em casos específicos.

### 1.2 SC — Salário-de-Contribuição

Valor sobre o qual incide a alíquota previdenciária. Limitado ao teto da época. Compreende:
- Salário do empregado (urbano/doméstico).
- Pró-labore do contribuinte individual.
- Valor declarado pelo facultativo.
- Salário-de-contribuição do segurado especial (quando contribuir como CI).

**Crítico:** SC abaixo do SM da época não é válido (exceto para alguns segurados especiais). SC acima do teto da época deve ser **limitado** ao teto.

### 1.3 SB — Salário-de-Benefício

Resultado da **média aritmética** dos SC do PBC, atualizados monetariamente. É a base para o cálculo da RMI.

### 1.4 RMI — Renda Mensal Inicial

Valor inicial do benefício na DIB.

```
RMI = SB × Coeficiente
```

**Coeficientes pós-EC 103 (regra geral):**
- Aposentadorias programadas: 60% + 2% × (TC - 20H/15M).
- Auxílio por incapacidade temporária: 91% × SB.
- Aposentadoria por incapacidade permanente: 60% + 2% (igual a programadas), exceto:
  - Acidente do trabalho → 100%.
  - Doença profissional → 100%.
  - Doenças graves do art. 26 Lei 8.213 → 100%.
- Pensão por morte: 50% + 10% × dependentes (até 100%).

**Coeficientes pré-EC 103 (regra antiga):**
- Aposentadoria por TC: 100% × SB × Fator Previdenciário (FP).
- Aposentadoria por idade: 70% + 1% × ano contribuído (máx. 100%) × SB; FP opcional.
- Aposentadoria especial: 100% × SB (sem FP).
- Aposentadoria por invalidez: 100% × SB.
- Auxílio-doença: 91% × SB (limitado à média dos 12 últimos SC).
- Auxílio-acidente: 50% × SB.

### 1.5 RMA — Renda Mensal Atual

Valor atualizado da RMI ao longo dos anos (reajustes anuais pelo INPC, salvo benefícios no piso, que seguem o SM).

```
RMA = RMI × ∏(1 + reajuste anual i)
```

### 1.6 Limites legais

- Piso: 1 salário mínimo (CF art. 201 §2º).
- Teto: teto INSS vigente na DIB (R$ 8.475,55 em 2026).

---

## 2. Documentos-fonte — como lê-los

### 2.1 CNIS (Cadastro Nacional de Informações Sociais)

Disponível no Meu INSS em **PDF**. Estrutura:
- **Vínculos:** lista cronológica de empregos, com CNPJ do empregador, data de admissão e demissão, PIS/PASEP, observações ("PEXT", "PVAL", "PADM-EMPR" indicam pendência).
- **Salários-de-contribuição:** mês a mês, com valor bruto declarado.
- **Indicadores:** marcadores de pendência:
  - **PEXT:** vínculo extemporâneo (registrado em data muito posterior — sob suspeita).
  - **PVAL:** vínculo cuja validade depende de comprovação adicional.
  - **PADM-EMPR:** pendência administrativa do empregador.
  - **PREM-EXT:** remuneração extemporânea.
  - **IREC-INDPEND:** indicador de recolhimento pendente.

**Auditoria do CNIS:**
- Vínculos faltantes? Comparar com CTPS, holerites, contratos.
- SC anômalos (zerados, abaixo do SM da época, valores inconsistentes)? Pedir documentação ao empregador ou contestar judicialmente.
- Períodos sem registro mas com prova? Reconhecimento via JT (sentença trabalhista) ou ação previdenciária.
- Períodos rurais sem registro? Documentação probatória (DAP, CCIR, declaração de sindicato).
- Tempo militar? Certidão da Força Armada.

### 2.2 Carta de Concessão (CC)

Emitida pelo INSS após concessão do benefício. Disponível no Meu INSS em PDF. Contém:
- **Dados do segurado** e da espécie/número do benefício.
- **DIB e DER** (com diferença, se houve reafirmação).
- **Tempo de contribuição apurado** (em dias).
- **Período Básico de Cálculo (PBC).**
- **Salários-de-contribuição utilizados** mês a mês com seus respectivos índices de atualização.
- **Salário-de-benefício** apurado.
- **Coeficiente aplicado.**
- **Fator previdenciário** (se aplicado).
- **RMI calculada.**
- **Memória de cálculo.**

**Auditoria da CC:**
- Conferir se TODOS os SC do CNIS entraram no PBC.
- Conferir se foi aplicado o teto da época (SC limitado).
- Conferir se a atualização foi feita pelo INPC correto.
- Conferir o **divisor** usado (número real de SC vs. divisor mínimo 108).
- Conferir o **coeficiente** aplicado vs. o devido.
- Conferir se o **FP** foi aplicado e calculado corretamente.
- Conferir se houve **regra mais favorável** ignorada.

### 2.3 Telas do Plenus (sistema interno do INSS)

Acessíveis em ações judiciais via ofício ao INSS ou em consulta administrativa. Telas-chave:

| Tela | Conteúdo |
|---|---|
| **REVSIT** | Situação de Revisão do Benefício |
| **CONREV** | Informações de Revisão de Benefício (revisões já feitas administrativamente) |
| **REVDIF / REVINF** | Discriminativo de Diferença de Revisão de Benefícios |
| **REVHIS** | Consulta do Histórico de Revisão |
| **CALCBEN** | Cálculo do Benefício |
| **HISCRE** | Histórico de Créditos (pagamentos) |
| **CNISA** | Cadastro Nacional de Informações com Anotações |

**Aplicação prática:** verificar se uma revisão (Buraco Negro, Buraco Verde, IRSM, Teto) já foi feita administrativamente — antes de ajuizar tese cobrindo período já corrigido.

### 2.4 PPP (Perfil Profissiográfico Previdenciário)

Documento emitido pelo empregador para comprovar exposição a agentes nocivos (atividade especial). Estrutura:
- Dados do empregador.
- Histórico de funções.
- Para cada função: agente nocivo (ruído em dB, calor em IBUTG, agentes químicos, biológicos), técnica de medição (NEN, NHO-01), responsável pela medição (engenheiro do trabalho), avaliação quantitativa/qualitativa.

**Auditoria do PPP:**
- Verificar se há identificação clara do agente nocivo.
- Para ruído: verificar metodologia (NEN — Nível de Exposição Normalizado vs. simples leitura).
- Para calor: IBUTG calculado conforme NHO-01.
- Para químicos: agente listado nos anexos do Decreto 3.048/99 (ou no anexo IV do Decreto 2.172/97 para período anterior).
- Falta de PPP? Tentar **LTCAT** (Laudo Técnico de Condições Ambientais do Trabalho), DSS-8030, SB-40, formulários antigos.

### 2.5 Microfichas e documentação antiga

- **Microfichas:** extratos antigos do INSS (1970s-1990s) com contribuições mensais. Hoje digitalizadas. Em alguns casos não estão no CNIS — pedir ao INSS via ofício.
- **Carnê GPS antigo:** comprovante de recolhimento como CI/facultativo.
- **CTPS:** carteira de trabalho física com anotações.
- **Holerite e contracheque:** prova de SC real (útil quando CNIS apresenta valor menor).
- **GFIP / RAIS:** declarações do empregador ao governo.

---

## 3. Atualização monetária — índices e regras

### 3.1 Índice de atualização dos SC (art. 33 do Decreto 3.048/99)

**INPC (Índice Nacional de Preços ao Consumidor — IBGE)** é o índice oficial de atualização dos SC. Publicado mensalmente pelo MPS por volta do dia 10 (a partir de 2009 — antes era diferente).

### 3.2 Período pré-INPC — controvérsia

| Período | Índice oficial INSS | Índice favorável (jurisprudência) |
|---|---|---|
| 21/06/1977 a 10/1984 | ORTN | Discutível — Tema 999 STJ definiu critérios |
| 10/1984 a 10/1989 | ORTN/OTN | INPC (mais favorável, contadorias judiciais) |
| 10/1989 a 02/1991 | OTN/BTN | Variação INPC |
| 03/1991 em diante | INPC | INPC |

**A escolha do índice altera a RMI** — ferramenta importante de revisão das aposentadorias antigas.

### 3.3 IRSM 39,67% — fevereiro/1994

Tema crítico. O IRSM (Índice de Reajuste do Salário Mínimo) de 02/1994 foi calculado em **39,67%**. O Plano Real entrou em vigor em **01/03/1994** com a URV. O governo **não aplicou** o IRSM de fev/94 sobre os SC anteriores que entrariam no PBC, gerando perda inflacionária.

**Tese:** incluir o IRSM 39,67% em 02/1994 na correção dos SC anteriores. STJ pacífico desde 2007 (REsp 1.087.366).

**Aplicabilidade:**
- DIB entre **01/03/1994 e 31/03/1997**.
- O mês de fev/1994 deve constar no PBC.

### 3.4 Reajustes anuais (RMA)

**Lei 8.213/91 art. 41-A:** benefícios em manutenção são reajustados anualmente pelo INPC, na mesma data do reajuste do SM.

| Ano | Reajuste benefícios > SM | Reajuste SM |
|---|---|---|
| 2024 | 3,71% | (variável) |
| 2025 | 4,77% | 7,5% |
| **2026** | **3,90%** | **6,79%** |

**Primeiro reajuste pós-DIB** = pro rata (proporcional aos meses do ano em que o benefício esteve vigente).
**Reajustes seguintes** = INPC integral.

**Benefícios no piso (1 SM)** sobem com o SM, não com o INPC. Em 2026: SM passou para R$ 1.621,00.

---

## 4. Fator Previdenciário — fórmula e aplicação

### 4.1 Fórmula (art. 29 §7º Lei 8.213)

```
       Tc × a       ┌    Id + Tc × a ┐
f  =  ───────── × │ 1 + ─────────────│
         Es        └          100        ┘
```

Onde:
- **f** = fator previdenciário.
- **Tc** = tempo de contribuição (em anos, com decimais).
- **a** = alíquota constante = **0,31** (20% patronal + 11% segurado).
- **Es** = expectativa de sobrevida na idade do segurado (tabela IBGE).
- **Id** = idade do segurado na DIB.

### 4.2 Tabela IBGE de expectativa de sobrevida

Atualizada anualmente pelo IBGE (geralmente em 01/12 — Tábua Completa de Mortalidade do Brasil). A nova tábua começa a valer no dia seguinte para benefícios com nova DIB; benefícios já concedidos não se alteram.

**Crítica constitucional pendente:** tabela única para ambos os sexos viola isonomia (homens têm menor expectativa de sobrevida). Tese de revisão sustenta que homem deveria ter FP mais favorável.

### 4.3 Quando aplicar o FP

| Benefício | FP |
|---|---|
| Aposentadoria por TC pré-EC 103 | **Obrigatório** (salvo regra 85/95) |
| Aposentadoria por idade pré-EC 103 | **Opcional** (apenas se favorável; FP > 1) |
| Aposentadoria especial | **NÃO se aplica** |
| Aposentadoria por invalidez | **NÃO se aplica** |
| Auxílio-doença | **NÃO se aplica** |
| Pensão por morte | **NÃO se aplica** |
| Pós-EC 103 | **NÃO se aplica** (substituído pelo coeficiente 60% + 2%) |

### 4.4 Regra 85/95 progressiva (Lei 13.183/2015) — afasta o FP

Para aposentadoria por TC, soma idade + TC:

| Período | Pontos H | Pontos M |
|---|---|---|
| 18/06/2015 a 30/12/2018 | 95 | 85 |
| 31/12/2018 a 30/12/2020 | 96 | 86 |
| 31/12/2020 a 30/12/2022 | 97 | 87 |
| 31/12/2022 a 30/12/2024 | 98 | 88 |
| 31/12/2024 a 30/12/2026 | 99 | 89 |
| 31/12/2026 em diante | 100 | 90 |

(Vigente até a EC 103, que substituiu pelas novas regras de transição.)

### 4.5 Cálculo exemplificativo

Homem, 60 anos, 35 anos de TC (Tc=35), DIB em 2018. Expectativa de sobrevida na idade 60 (tábua 2017): Es ≈ 22,2 anos.

```
f = (35 × 0,31 / 22,2) × [1 + (60 + 35 × 0,31)/100]
f = (10,85 / 22,2) × [1 + (60 + 10,85)/100]
f = 0,4887 × [1 + 0,7085]
f = 0,4887 × 1,7085
f ≈ 0,835
```

→ **FP = 0,835** (RMI será 83,5% do SB). Redutor significativo.

---

## 5. Plataformas comerciais — o que cada uma faz

### 5.1 Prévius 3.0+ (desenvolvido pela Lógike)

**Recursos centrais:**
- Importação de **CNIS em PDF** automatizada.
- Importação de **Carta de Concessão** e **HISCRE**.
- **Comparação automática mês a mês** entre CNIS e CC, identificando diferenças.
- Aplicação automática de regras pré e pós-EC 103.
- Cálculo de **todas as regras de transição** simultaneamente, indicando o melhor benefício.
- Aplicação do **IRSM 39,67% em 02/1994**.
- Conversão de tempo especial em comum.
- Correção de diferenças por TR (a partir de 07/2009 — para JF).
- Mudanças de moeda automatizadas (Cruzeiro, Cruzado, NCz, Real).
- Importação de SC via Excel.
- Cálculo de **todas as revisões clássicas** (Vida Toda, Teto EC 20/41, IRSM, Buraco Negro, Buraco Verde, art. 29 §5º, art. 29 II, melhor renda pensão, atividades concomitantes, alteração alíquota auxílio-acidente, etc.).
- Cálculo de **planejamento previdenciário** (projeção futura).
- Cálculo de período de graça e qualidade de segurado.
- Cálculo de honorários previdenciários.
- Cálculo de prazo decadencial.
- Cálculo de restituição de IRRF (doença grave).
- Cálculo de restituição de contribuição acima do teto.
- Precatórios (Tema 810, Tema 96 INSS).

**Site:** logi.ke / fusionsj.com.br
**Modelo:** licença anual.

### 5.2 Previdenciarista (Prev) — previdenciarista.com

**Recursos centrais:**
- Cálculo a partir do **CNIS importado** ou via extensão direta do **Meu INSS** (1 clique).
- **Comparação lado a lado** de todos os benefícios disponíveis (planejamento futuro).
- Cálculo de liquidação de sentença previdenciária.
- Calculadoras gratuitas (algumas no domínio público):
  - Fator Previdenciário Online.
  - Pedágio para aposentadoria (RGPS e RPPS).
  - Honorários Advocatícios Previdenciários.
  - Nível de Ruído Normalizado.
  - Restituição de IR sobre aposentadoria.
  - Acumulação de benefícios.
  - Contribuição Previdenciária e Alíquota Efetiva.
  - Prazo Decadencial.
- IA integrada ao fluxo (geração de petições, organização de documentos, posts de marketing).
- Petições editáveis pré-elaboradas.
- Banco de laudos (constantemente atualizado).
- Sistema de captação de leads previdenciários.
- Vitrine de advogado (perfil público).

**Site:** previdenciarista.com (com submarca "Prev").

### 5.3 Cálculo Jurídico (CJ) — calculojuridico.com.br

**Recursos centrais:**
- Cálculo online (acesso via web, qualquer dispositivo).
- Importação do CNIS.
- Cálculo de RMI, revisão, planejamento.
- **Cálculo de revisões antigas** (ORTN, Buraco Negro, Buraco Verde, IRSM, Teto, etc.).
- Suporte a benefícios pós-Reforma e pré-Reforma com escolha do regime aplicável.
- Configurações avançadas dos SC (limitação ao teto, limitação ao SM, ORTN vs. INPC para 1984-1989, descarte de SC sem TC associado, etc.).
- Coeficiente teto (divisão da média pelo teto na DIB) para revisões.
- Cálculo de prescrição quinquenal automatizado.
- Educação contínua (blog, YouTube).

**Site:** calculojuridico.com.br

### 5.4 Outras ferramentas relevantes

- **RMI-PREV (TRF4):** planilha Excel gratuita para simular RMI de benefícios com DIB entre 29/11/1999 e 12/11/2019 (regra Lei 9.876). Atualizada mensalmente. Útil como **second opinion** independente.
- **Site MPS — Índices de atualização:** publicação mensal oficial dos índices INPC para correção dos SC. Uso obrigatório como fonte primária.
- **TJDFT — Manual de Cálculo Previdenciário:** documento de domínio público com explicações da lógica de cálculo.

### 5.5 O que os softwares **NÃO fazem** (e o advogado deve fazer)

- **Verificar se o CNIS está completo** (vínculos faltantes, períodos sem registro). É trabalho documental e investigativo.
- **Avaliar PPP**: se o documento em mãos efetivamente comprova o agente nocivo conforme normativa do período. É análise jurídica.
- **Avaliar tempo rural**: provas materiais, oitiva de testemunhas, ITR, declarações sindicais — coleta humana.
- **Identificar tese jurídica aplicável**: software calcula, mas não escolhe a tese. Decisão é do advogado.
- **Avaliar viabilidade de revisão pós-modulação STF**: cada tese tem modulações específicas (ex.: Vida Toda foi superada em 11/2025 — softwares com bases desatualizadas podem ainda calcular sem alerta).
- **Comparar resultados entre plataformas** quando há divergência: comparar sempre 2-3 fontes em casos de alta complexidade.

---

## 6. Matriz de erros típicos do INSS

### 6.1 Erros de tempo de contribuição

| Erro | Como detectar | Como contestar |
|---|---|---|
| Vínculo não computado (PEXT, PVAL) | Conferir CNIS vs. CTPS / contratos | Documentação ao INSS; se negada, ação |
| Período rural ignorado | Cliente disse que trabalhou na roça e não está no CNIS | Provas materiais + testemunhas + DAP |
| Tempo militar não computado | Verificar período militar com cliente; ofício à FA | Certidão da Força Armada |
| Tempo especial recusado por PPP "incompleto" | INSS exigiu requisito não previsto na época | Tese de aplicação retroativa do regime mais favorável |
| Atividades concomitantes não somadas | Cliente trabalhou em duas empresas no mesmo período | Inclusão de SC concomitantes (Tema 999 STJ — soma limitada ao teto) |
| Períodos de auxílio-doença/aposentadoria por invalidez não computados como TC | INSS desconsiderou intervalos de afastamento por incapacidade | STJ pacífico: período de benefício por incapacidade conta como TC se intercalado com atividade |

### 6.2 Erros de salário-de-contribuição

| Erro | Como detectar | Como contestar |
|---|---|---|
| SC zerado em meses com atividade | CNIS mostra SC = 0 em meses com vínculo | Pedir holerite, GFIP, RAIS ao empregador |
| SC abaixo do real (sub-recolhimento) | Holerite mostra valor superior ao do CNIS | Sentença trabalhista com inclusão de verbas remuneratórias |
| SC limitado ao teto da época incorretamente | INSS aplicou teto errado | Conferir tabela histórica de teto |
| SC não atualizado pelo IRSM 39,67% (02/1994) | DIB entre 03/1994 e 03/1997 com fev/94 no PBC | Tese IRSM (revisão) |
| Verbas trabalhistas reconhecidas judicialmente não incluídas | Sentença JT com horas extras, adicional de insalubridade etc. | Revisão com inclusão de verbas |

### 6.3 Erros no cálculo da média (SB)

| Erro | Como detectar | Como contestar |
|---|---|---|
| 80% maiores não selecionados (pré-EC 103) | Conferir SC selecionados na CC; deveria haver descarte de 20% menores | Revisão de cálculo |
| Aplicação do divisor mínimo (108) quando indevido | Cliente tem ≥108 SC mas o divisor usado foi 108 | Revisão |
| Não aplicação do divisor 108 quando devido (pré-Lei 14.331/2022) | Após 26/04/2022 o divisor 108 voltou a valer | Verificar legislação vigente na DIB |
| ORTN aplicada quando INPC seria mais favorável (1984-1989) | Conferir índices na CC | Revisão |

### 6.4 Erros no coeficiente e FP

| Erro | Como detectar | Como contestar |
|---|---|---|
| FP aplicado quando regra 85/95 isentaria | Conferir pontos na DIB | Revisão para afastar FP |
| FP calculado com Es errada (ano inadequado) | Conferir tábua IBGE vigente na DIB | Revisão |
| Coeficiente pós-EC errado (60% + 2% × X) | Conferir TC excedente | Revisão |
| Aplicação de regra geral pós-EC quando regra antiga ou de transição era mais favorável | Direito adquirido até 12/11/2019 ignorado | Revisão pelo melhor benefício |
| Regra de transição mais vantajosa não simulada | INSS escolheu uma regra; outra daria RMI maior | Reafirmação da DER ou revisão pelo melhor benefício |

### 6.5 Erros de regras de transição

| Erro | Como detectar | Como contestar |
|---|---|---|
| Pedágio calculado errado | Conferir tempo faltante em 13/11/2019 vs. pedágio aplicado | Revisão |
| Pontos calculados com data errada | Idade + TC contados em data inadequada | Reafirmação da DER |
| Idade progressiva calculada com tabela errada | Idade exigida no ano não confere com tabela | Conferir tabela oficial |
| INSS não simulou todas as regras | CC mostra apenas uma regra; advogado simula 5 e encontra divergência | Revisão pelo melhor benefício / Ação judicial |

### 6.6 Erros documentais

| Erro | Como detectar | Como contestar |
|---|---|---|
| Microficha não consultada | Cliente lembra de contribuições antigas; não estão no CNIS | Pedir microficha via ofício |
| CNIS desatualizado | Vínculos recentes não aparecem | Solicitar atualização ao empregador / RFB |
| Sentença trabalhista não incluída | JT reconheceu vínculo/verbas e INSS ignorou | Revisão para inclusão |
| Atividade especial sem PPP no INSS | Empregador omitiu | Pedir PPP via JT ou ação direta |

---

## 7. Matriz de erros típicos de plataformas

### 7.1 Erros de input

| Erro | Sintoma | Correção |
|---|---|---|
| Importação de CNIS com SC zerados | Plataforma importa "0" para meses sem dado | Editar manualmente os SC reais |
| Importação de CTPS com datas erradas | OCR do PDF da CTPS digital impreciso | Conferir cada vínculo manualmente |
| Não importação de microfichas | Plataforma não tem essa função | Inserir manualmente os SC antigos |
| Conversão de moeda incompleta | Anos pré-1994 com SC em moeda antiga (Cruzeiro, Cruzado) | Verificar se a plataforma converte automaticamente |

### 7.2 Erros de configuração

| Erro | Sintoma | Correção |
|---|---|---|
| Limitação ao teto desabilitada | Média acima do teto da época | Habilitar a limitação |
| Limitação ao SM desabilitada | SC abaixo do SM aceito | Habilitar |
| ORTN vs. INPC para 1984-1989 | Plataforma usa ORTN por padrão (menos favorável) | Selecionar INPC quando favorável |
| Descarte de SC sem TC associado desativado | Plataforma considera SC mesmo sem vínculo formal | Avaliar caso a caso |
| Espécie de benefício errada | "Aposentadoria por idade" quando deveria ser "TC" | Corrigir e refazer |

### 7.3 Erros de tese / desatualização

| Erro | Sintoma | Correção |
|---|---|---|
| Plataforma calcula Vida Toda como viável | Software com base não atualizada para superação de 11/2025 | **Desconsiderar** — Vida Toda foi superada |
| Plataforma não aplica modulação Tema 1102 | Apuração não considera modulação de 04/2024 | Verificar manualmente |
| Tabela IBGE desatualizada para FP | Es de ano antigo aplicada a DIB recente | Verificar versão da plataforma |
| Coeficientes pós-EC 103 errados | Aplicação incorreta de 60% + 2% | Recalcular manualmente |
| Pedágio 50%/100% calculado errado | Lógica do pedágio confusa para alguns casos | Conferir manualmente |

### 7.4 Divergências entre plataformas (red flag)

Quando duas plataformas dão RMI diferentes para o mesmo cenário, há uma divergência genuína a investigar:
- Diferença pequena (≤2%): pode ser arredondamento, divisor, último mês.
- Diferença média (2-5%): provavelmente um índice de atualização diferente ou um SC discrepante.
- Diferença grande (>5%): erro grave em alguma das plataformas — auditar manualmente cada etapa.

**Procedimento:** rodar 3 fontes (Prévius + CJ + RMI-PREV/TRF4) e comparar.

---

## 8. Checklist de auditoria — protocolo passo a passo

### 8.1 Auditoria de cálculo do INSS (Carta de Concessão)

```
□ Solicitar Carta de Concessão (PDF) e CNIS atualizado pelo Meu INSS.
□ Solicitar HISCRE e telas REVSIT, CONREV, REVHIS (se houver indício de revisão prévia).
□ Conferir IDENTIFICAÇÃO:
  □ DIB e DER (há diferença? houve reafirmação?)
  □ Espécie do benefício (B41, B42, B91, B92, B25, BPC, etc.)
  □ Tempo de contribuição apurado (em dias)
□ Conferir PBC:
  □ Período: 07/1994 até DER (regra Lei 9.876+)
  □ Quantidade de SC considerados
  □ Divisor utilizado
□ Conferir cada SC:
  □ Bate com CNIS?
  □ Bate com holerite/contracheque (amostra)?
  □ Aplicação correta do teto da época?
  □ SC < SM da época descartados?
□ Conferir ATUALIZAÇÃO:
  □ Índice INPC aplicado mês a mês confere?
  □ IRSM 39,67% em 02/1994 aplicado (se DIB entre 03/1994 e 03/1997)?
□ Conferir SB:
  □ Média = soma dos SC atualizados ÷ divisor?
  □ Se Lei 9.876, descarte dos 20% menores SC?
□ Conferir RMI:
  □ Coeficiente aplicado correto?
  □ FP calculado corretamente (se aplicável)?
  □ Regra 85/95 ou 86/96 (pré-EC 103) afastaria o FP?
  □ Limites: piso (1 SM) e teto (R$ 8.475,55 em 2026 ou da DIB) respeitados?
□ Conferir TEMPO DE CONTRIBUIÇÃO:
  □ Vínculos do CNIS computados?
  □ Tempo especial reconhecido (se aplicável)?
  □ Conversão tempo especial em comum até 12/11/2019 aplicada?
  □ Tempo rural reconhecido (se aplicável)?
  □ Períodos de auxílio-doença intercalados computados?
□ Conferir REGRA APLICADA:
  □ INSS testou todas as regras possíveis?
  □ Regra antiga (direito adquirido até 12/11/2019)?
  □ Regras de transição (5 hipóteses)?
  □ Regra geral pós-EC?
  □ Aplicação foi pela melhor regra ou houve regra mais vantajosa não considerada?
□ Conferir REVISÕES já feitas administrativamente (CONREV, REVHIS):
  □ Buraco Negro (DIB entre 05/10/1988 e 05/04/1991)?
  □ Buraco Verde (DIB entre 06/04/1991 e 31/12/1993, ou a partir de 01/03/1994)?
  □ IRSM (DIB entre 03/1994 e 03/1997 com fev/94 no PBC)?
  □ Teto (EC 20/98 e EC 41/03)?
□ Calcular RMI hipotética em pelo menos 2 plataformas independentes.
□ Comparar com RMI da CC.
□ Diferença ≥ 5%? Vale revisão. Diferença ≤ 2%? Arredondamento, sem ação.
```

### 8.2 Auditoria de cálculo de plataforma comercial

```
□ Identificar a plataforma e a versão (data da última atualização).
□ Conferir BASE DE DADOS:
  □ Tábua IBGE de mortalidade está atualizada?
  □ Tabela INPC está atualizada?
  □ Coeficientes pós-EC 103 corretos?
  □ Tabelas de teto histórico atualizadas?
  □ Vida Toda está sinalizada como SUPERADA (11/2025)?
□ Conferir INPUTS:
  □ CNIS importado completo?
  □ SC editados manualmente (microficha, holerite)?
  □ Tempo especial inserido com PPP?
  □ Tempo rural inserido com documentação?
  □ Sentenças trabalhistas com inclusão de verbas?
□ Conferir CONFIGURAÇÕES:
  □ Limitação ao teto: ON?
  □ Descarte de SC < SM: configurado?
  □ ORTN vs. INPC: escolha mais favorável?
  □ Regra escolhida está correta para a DIB?
□ Conferir OUTPUTS:
  □ SB calculado bate com cálculo manual de amostra?
  □ Coeficiente e FP aplicados corretos?
  □ RMI dentro dos limites legais?
□ Cross-check com 2ª plataforma:
  □ Mesma RMI (±2%)?
  □ Divergência > 5%? Auditar manualmente.
□ Conferir GAPS:
  □ Vínculos não importados que existem?
  □ Tempo especial elegível mas não inserido?
  □ Microfichas não consultadas?
□ Avaliar TESES:
  □ Quais revisões podem ser invocadas (DIB do cliente)?
  □ Vida Toda: SUPERADA — não usar para novas ações.
  □ Modulação Tema 1102 protege ações pré-04/2024 contra cobrança?
```

---

## 9. Revisões antigas — mapa por DIB com status atual

| Revisão | DIB elegível | Tese | Status 2026 | Decadência |
|---|---|---|---|---|
| **ORTN** | 17/06/1977 a 04/10/1988 | Recálculo dos primeiros 24 SC do PBC com ORTN/OTN/BTN | Vigente — IN INSS específica | Discutível (inflacionário) |
| **Buraco Negro** | 05/10/1988 a 05/04/1991 | Art. 144 Lei 8.213 — recálculo da RMI com novos índices e coeficientes | **Vigente** — TRF4 entendimento pacificado | **Sem decadência** (revisão de RMI por lei superveniente) |
| **Buraco Verde** | 06/04/1991 a 31/12/1993 | Limitação ao teto aplicada após média (deveria ser após RMI); Tema 930 STF | **Vigente** | **Sem decadência** (inflacionário) |
| **Buraco Verde Estendido** | A partir de 01/03/1994 | Mesma lógica do Buraco Verde estendida pela jurisprudência | Vigente | Sem decadência |
| **IRSM 39,67%** | 01/03/1994 a 31/03/1997 (com fev/94 no PBC) | Inclusão do IRSM de 02/1994 na correção dos SC | Vigente — STJ pacífico (REsp 1.087.366) | Decadência 10 anos da DIB |
| **Teto EC 20/98** | DIB anterior a 16/12/1998 com SB > teto da época | Liberação do excedente engessado | Vigente — Tema 76/STF | Decadência 10 anos |
| **Teto EC 41/03** | DIB anterior a 31/12/2003 com SB > teto | Idem | Vigente — Tema 76/STF | Decadência 10 anos |
| **Art. 29 II** (atividade especial) | Pré-EC 103 | RMI calculada com fórmula de TC quando deveria ser pela atividade | Vigente | Decadência 10 anos |
| **Art. 29 §5º** (períodos sem contribuição) | Pré-EC 103 | Cômputo de períodos de benefício como TC | Vigente | Decadência 10 anos |
| **Atividades concomitantes** | Pré-EC 103 com 2+ vínculos simultâneos | Soma dos SC concomitantes — Tema 999/STJ | Vigente | Decadência 10 anos |
| **Inclusão do 13º no PBC** | Pré-Lei 8.870/94 | 13º indevidamente excluído do PBC | Vigente | Decadência 10 anos |
| **Vida Toda** | DIB entre 28/11/1999 e 12/11/2019 | Inclusão de SC pré-07/1994 quando favorável | **🔴 SUPERADA — STF 26/11/2025 (Embargos no Tema 1102 + ADIs 2.110/2.111)** | N/A — não cabe nova ação |
| **Melhor Benefício** | Qualquer DIB | Aplicação da data mais favorável dentro do período de elegibilidade — Súmula 5 TNU + Tema 334 STF | Vigente | Decadência 10 anos |
| **Reafirmação da DER** | DER em curso ou processo judicial | Mover DER para data mais favorável superveniente — Tema 995/STJ | Vigente — Súmula 124 TNU | Aplicável durante processo |

### 9.1 Vida Toda — alerta especial 2026

**A tese da Revisão da Vida Toda está DEFINITIVAMENTE SUPERADA.** Histórico:

- **2018-2019:** STJ Tema 999 — favorável.
- **Dez/2022:** STF Tema 1102 (RE 1.276.977) — favorável (5x4) à possibilidade de opção pela regra definitiva.
- **2024:** STF julgou ADIs 2.110/DF e 2.111/DF declarando **constitucional o art. 3º da Lei 9.876/99**, derrubando o fundamento da Vida Toda.
- **05/04/2024:** publicação da ata de julgamento das ADIs (data de corte da modulação).
- **10/04/2025:** modulação dos efeitos — irrepetibilidade dos valores recebidos até 05/04/2024 + isenção de custas/honorários para ações pendentes até essa data.
- **26/11/2025:** STF concluiu embargos no Tema 1102 — **cancelou a tese de 2022** e fixou nova:

> *"A declaração de constitucionalidade do art. 3º da Lei n. 9.876/1999 impõe que o dispositivo legal seja observado de forma cogente. O segurado do INSS que se enquadre no dispositivo não pode optar pela regra definitiva prevista no art. 29, I e II, da Lei n. 8.213/1991, independentemente de lhe ser mais favorável."*

**Modulação aplicável:**
- Valores recebidos até 05/04/2024 são **irrepetíveis** (não devolução).
- Para ações pendentes até 05/04/2024 sem trânsito em julgado: julgar improcedente, **mas sem cobrança de honorários, custas e perícias** dos autores.
- Processos com trânsito em julgado favorável antes de 05/04/2024: **mantidos** (boa-fé do segurado).

**Aplicação Noviello:**
- **Não propor nova ação de Vida Toda em 2026.** Risco de improcedência liminar (CPC art. 332).
- **Auditar ações em curso** do escritório: verificar modulação aplicável.
- **Comunicar clientes** com Vida Toda em curso: explicar status, riscos, e que a modulação protege contra devolução e custas.
- **Em revisões hipotéticas de plataforma:** se a plataforma simular Vida Toda como vantajosa, **descartar** — não é tese ajuizável.

---

## 10. Reafirmação da DER e Melhor Benefício — instrumentos vivos

### 10.1 Reafirmação da DER (Tema 995/STJ + Súmula 124 TNU)

**Aplicação prática:** durante processo administrativo ou judicial, se o cliente cumpre novo requisito (idade, novo tempo, regra mais favorável), **pleitear que a DER seja reafirmada** para a data em que o requisito foi atingido.

**Vantagens:**
- Não exige novo protocolo administrativo.
- Garante parcelas vencidas a partir da nova DER.
- Possibilita escolha da regra ótima dentro do período de tramitação.

**Pedido típico:** "Subsidiariamente, requer a reafirmação da DER para [data], em que o segurado atingiu os requisitos da regra [X], com fundamento no Tema 995/STJ."

### 10.2 Revisão pelo Melhor Benefício (Súmula 5 TNU + Tema 334 STF)

**Aplicação:** se entre a primeira data de elegibilidade e a DER houve datas com cálculo mais favorável, pleitear que a RMI seja calculada na data ótima.

**Pedido:** simulação retroativa da RMI em cada data possível dentro do período. Aplicação da mais favorável.

---

## 11. Fluxograma decisório de auditoria

```
Cliente já aposentado chega para auditoria
                        ↓
            Solicitar:
            • Carta de Concessão (PDF)
            • CNIS atualizado (PDF)
            • HISCRE
            • Comprovante de pagamento atual
            • Documentação não computada (PPP, microfichas, etc.)
                        ↓
            Verificar DIB:
   ┌────────────────┬──────────────┬──────────────┐
   │ DIB ≤ 04/10/88 │ 05/10/88 a   │ 06/04/91 a   │
   │     (ORTN)     │ 05/04/91     │ 31/12/93 ou  │
   │                │ (Buraco Negro)│ a partir 01/03/94│
   │                │              │ (Buraco Verde)│
   └───────┬────────┴──────┬───────┴──────┬───────┘
           │               │              │
           ↓               ↓              ↓
       Verificar       Sem decadência  Sem decadência
       teses           — propor revisão — propor revisão
       específicas

   ┌──────────────┬──────────────────────┬────────────────┐
   │ 03/94 a 03/97│ Antes EC 20 (98) ou  │ 28/11/99 a     │
   │ (IRSM)       │ EC 41 (03) com SB    │ 12/11/19       │
   │              │ > teto época         │ (Vida Toda     │
   │              │ (Revisão Teto)       │ SUPERADA)      │
   └──────┬───────┴──────────┬───────────┴────────┬───────┘
          ↓                  ↓                    ↓
       Ver fev/94         Tema 76/STF —       🔴 NÃO ajuizar
       no PBC            propor revisão       — STF derrubou
       — propor          (10 anos decadência) em 11/2025
       revisão
       (10 anos)
                        ↓
   Calcular RMI hipotética em 2-3 plataformas independentes:
   • Prévius
   • Cálculo Jurídico
   • RMI-PREV (TRF4) como controle
                        ↓
   Comparar com RMI da Carta de Concessão:
   • Diferença ≤ 2% → arredondamento, sem ação
   • Diferença 2-5% → avaliar custo/benefício
   • Diferença > 5% → propor revisão
                        ↓
   Revisão pelo melhor benefício (Súmula 5 TNU)
   Atividades concomitantes (Tema 999 STJ)
   Tempo especial não reconhecido
   13º no PBC (pré-1994)
   Art. 29 II (incapacidade)
                        ↓
   Definir tese principal + subsidiárias
                        ↓
   Comunicar cliente:
   • Ganho potencial mensal
   • Atrasados (5 anos prescrição)
   • Custos e prazos
   • Riscos
                        ↓
   Decisão: ação revisional (rito ordinário JF
   ou JEF se ≤ 60 SM) com pedido de tutela
   se urgência
```

---

## 12. Output da auditoria — formato Noviello

Ao final da auditoria, entregar ao cliente em **parecer enxuto** (pelo papel timbrado) contendo:

```
1. Identificação do benefício atual:
   - Espécie e número.
   - DIB.
   - RMI original e RMA atual.

2. Diagnóstico:
   - O que foi auditado (CNIS, CC, HISCRE, telas Plenus).
   - Pontos verificados (cada item do checklist §8).

3. Achados:
   - Erros identificados (com citação da regra/precedente).
   - RMI hipotética alternativa (com fonte do cálculo).
   - Diferença mensal.
   - Atrasados estimados (5 anos × diferença mensal).

4. Teses aplicáveis:
   - Revisão X — fundamento, prognóstico, decadência.
   - Revisão Y (subsidiária).

5. Inviabilidades identificadas:
   - Vida Toda (superada em 11/2025) — explicar que não é ajuizável.

6. Recomendação:
   - Ação revisional? Recurso administrativo? Reafirmação DER?
   - Custo (honorários conforme tabela OAB).
   - Prazo estimado.
   - Riscos.

7. Documentação adicional necessária:
   - Lista do que ainda precisa ser obtido.

8. Validade:
   - "Considerando legislação e jurisprudência vigentes em [mês/ano]."
```

**Padrão Noviello:** documento técnico, sem ostentação, assinado por "Noviello Advocacia" ou Mario Luiz Noviello Junior conforme o caso. Sem markdown agressivo. Citações normativas precisas.

---

## 13. Cross-references

- Para parâmetros 2026 (SM, teto, alíquotas): `parametros-2026.md`.
- Para escolha da regra de aposentadoria: `ec-103-2019-transicao.md`.
- Para outras revisões (síntese): `revisoes-judiciais.md` (atualizado com status Vida Toda 11/2025).
- Para forma de petição: SKILL.md desta skill + `noviello-imobiliario-contratos-minutas` + `noviello-preliminar-procuracao-eletronica`.
- Para precificar a auditoria como pacote: tabela OAB + comunicação clara ao cliente sobre custo-benefício.

---

## 14. Manutenção desta reference

Atualizar quando:
- Nova decisão STF/STJ que altere o status de uma revisão (ex.: superação da Vida Toda em 11/2025 — já incorporado).
- Nova tabela IBGE de mortalidade (anual, geralmente 01/12).
- Atualização do INPC mensal (auto-atualiza nas plataformas; verificar quando há lacuna).
- Nova versão das plataformas (Prévius, Previdenciarista/Prev, Cálculo Jurídico) com mudanças relevantes.
- Nova lei que altere a fórmula (improvável no curto prazo, mas monitorar).
- Mudança no divisor mínimo (Lei 14.331/2022 → próxima alteração legislativa).
- Nova tese de revisão consolidada na jurisprudência.
