# Identidade Visual Oficial — Noviello Advocacia

> **Fonte autoritativa:** Manual da Marca oficial (`Manual_da_Marca.pdf`). Este documento é a consolidação das diretrizes oficiais. Em caso de conflito, o Manual da Marca PDF prevalece.

---

## 1. Arquivos Oficiais Disponíveis

Todos os arquivos da marca estão em `noviello-brand-assets/`:

| Arquivo | Uso |
|---|---|
| `Manual_da_Marca.pdf` | Referência oficial completa (24 páginas) |
| `papelaria/papel-de-carta-padrao.docx` | **BASE OFICIAL** para todo documento formal |
| `logos/logo-branco.png` | Vetor branco para fundos escuros |
| `logos/logo-branco.png` | Raster branco |
| `logos/logo-greyscale.jpg` | Greyscale raster |
| `logos/logo-greyscale-transparente.png` | Greyscale com transparência |
| `logos/logo-greyscale.jpg` | Vetor greyscale |
| `fonts/Cinzel.ttf` | Títulos |
| `fonts/Poppins-{Regular,Medium,SemiBold,Bold}.ttf` | Corpo |

---

## 2. Paleta de Cores Oficial

| Nome | HEX | CMYK | RGB | Uso |
|---|---|---|---|---|
| **Claret** | `#68192E` | 0, 76, 56, 59 | 104, 25, 46 | Cor principal. Títulos, fundos, CTAs, destaques |
| **Chocolate Cosmos** | `#540D1D` | 0, 85, 65, 67 | 84, 13, 29 | Sombras, bordas, hover, texto em destaque sobre fundo claro |
| **Anti-flash White** | `#F1F3F2` | 1, 0, 0, 5 | 241, 243, 242 | Fundos suaves, espaços em branco |
| **Battleship Gray** | ver manual | — | — | Cinza secundário, elementos de apoio |

**Cores derivadas aceitáveis** (para uso controlado):
- Cinza quente para corpo de texto: `#3D3D3D`
- Claret muito claro para highlight boxes: `#F5E6EA`

---

## 3. Tipografia Oficial

### Cinzel
- **Aplicação:** TODOS os títulos, manchetes, logomarca, palavras de destaque em peças formais
- **Caráter:** inspirada em inscrições romanas clássicas — solidez, confiabilidade, elegância
- **Pesos:** Regular e Bold

### Poppins
- **Aplicação:** corpo de texto, parágrafos, subtítulos, CTAs, labels
- **Caráter:** moderna, geométrica, limpa, versátil
- **Pesos:** 400 (Regular), 500 (Medium), 600 (SemiBold), 700 (Bold)

**⚠️ REGRA ABSOLUTA:** Nunca substituir Cinzel por outra fonte serifada. Nunca substituir Poppins por outra sans-serif. Se a fonte não estiver disponível no sistema, **baixar e instalar** antes de gerar o documento (fontes estão em `noviello-brand-assets/fonts/`).

---

## 4. Símbolo da Marca

- Formado por **duas curvas retiradas das letras "N" e "V"**
- Transmite fluidez, dinamismo, movimento — representa evolução e adaptação jurídica
- Simboliza flexibilidade e criatividade nas soluções
- Comunica sofisticação, elegância e refinamento
- **Área de proteção:** a distância mínima ao redor equivale ao tamanho do próprio símbolo "N". Esse espaço deve ser sempre respeitado.

---

## 5. Versões Autorizadas do Logo

### Monocromáticas
- **Branco** sobre fundo escuro (preto, claret, wine, navy, verde escuro, roxo escuro)
- **Preto** sobre fundo claro
- **Ambas permitem** o bloco retangular (com fundo) ou o logo solto (sem contorno)

### Greyscale
- Símbolo a **30% de preto** + texto a **70% de preto**
- Usar **apenas quando impossível aplicar a paleta oficial**

### Fundos coloridos autorizados
O manual aprova:
- **Fundo escuro:** vermelho escuro, azul marinho, roxo escuro, verde escuro (logo branco)
- **Fundo claro:** azul claro, verde claro, rosa claro, laranja claro (logo em claret ou preto)

---

## 6. Usos INCORRETOS (Proibidos)

❌ Alterar as cores do logo  
❌ Distorcer proporções  
❌ Rotacionar  
❌ Usar em modo outline  
❌ Aplicar versão escura em fundo escuro (sem contraste)  
❌ Aplicar versão clara em fundo claro (sem contraste)  
❌ Alterar a ordem dos elementos (símbolo + texto)  
❌ Usar fonte diferente de Cinzel/Poppins  
❌ Criar layout de documento formal fora do Papel de Carta Padrão

---

## 7. Papel de Carta Padrão — BASE OFICIAL

**Arquivo:** `noviello-brand-assets/papelaria/papel-de-carta-padrao.docx`

**Especificações:**
- Formato A4 (11906 × 16838 DXA)
- Margens: top 1417, right 1701, bottom 1417, left 1701 (DXA)
- Header (708 DXA do topo): logo real + elementos decorativos geométricos (paralelogramas claret/cinza no canto superior direito)
- Footer (794 DXA da base): ícones circulares claret de WhatsApp/telefone/email/globo + dados de contato em claret uppercase
- Decorações geométricas espelhadas no canto inferior esquerdo

**Uso obrigatório para:**
- Propostas comerciais / orçamentos
- Pareceres jurídicos
- Memorandos técnicos
- Ofícios
- Cartas ao cliente
- Contratos de honorários
- Qualquer documento formal assinado pelo escritório

**Workflow técnico para gerar documento sobre o papel de carta:**
```bash
# 1. Desempacotar o papel de carta (preserva header/footer/mídias)
python /mnt/skills/public/docx/scripts/office/unpack.py papel-de-carta-padrao.docx unpacked/

# 2. Editar apenas word/document.xml injetando conteúdo no body (header/footer intactos)

# 3. Reempacotar validando
python /mnt/skills/public/docx/scripts/office/pack.py unpacked/ output.docx --original papel-de-carta-padrao.docx
```

**Ordem correta de elementos XML no `<w:pPr>`:**  
`pStyle` → `keepNext` → `pageBreakBefore` → `pBdr` → `shd` → `spacing` → `ind` → `jc` → `rPr`

**Ordem correta em `<w:tcPr>`:**  
`tcW` → `gridSpan` → `tcBorders` → `shd` → `tcMar` → `vAlign`

---

## 8. Tom de Voz e Aplicação por Canal

| Canal | Tom | Identidade visual |
|---|---|---|
| Documentos formais (orçamento/parecer/ofício) | Formal, técnico, autoridade profissional | Papel de Carta Padrão obrigatório |
| Blog e newsletter corporativa | Formalidade moderna | Cabeçalho padrão do site |
| Instagram/TikTok (@novielloadv) | Humanizado, acessível | Carrosséis conforme specs seção 9 |
| LinkedIn | Técnico, peer-to-peer | Artigos + imagens com identidade |
| WhatsApp institucional | Cordial mas profissional | Assinatura padrão |

---

## 9. Especificações por Formato

### Carrossel Instagram
- Dimensão: 1080×1080 (quadrado) ou 1080×1350 (retrato)
- Margem de segurança: 60 px
- Slide 1: fundo claret `#68192E`, título Cinzel branco, subtítulo Poppins creme
- Slides intermediários: fundo creme `#FAF7F5`, título claret, corpo cinza `#3D3D3D`
- Slide final: fundo claret, logotipo centralizado, contato branco

### Reels / TikTok
- Dimensão: 1080×1920 (9:16 vertical)
- Safe zone: 250 px topo, 350 px base
- Texto: Poppins 500, mínimo 48pt, fundo semi-transparente `rgba(104,25,46,0.8)`
- Frame final: logo centralizado + @novielloadv + OAB/SP 370.796

### Documento Formal (orçamento/parecer)
- Base: Papel de Carta Padrão oficial
- Título principal: Cinzel bold 24pt claret (com border-bottom claret)
- Subtítulos: Cinzel bold 11pt claret uppercase (com border-bottom)
- Corpo: Poppins regular 10pt cinza quente `#3D3D3D`, entrelinha 1.5
- Tabelas: header claret `#68192E` + texto branco / corpo branco alternando com `#FAF7F5` / bordas `#E8E0E3`
- Totais: fundo Chocolate Cosmos `#540D1D` + texto branco
- Destaques/highlight: fundo claret claro `#F5E6EA` com borda claret
