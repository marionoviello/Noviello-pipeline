# Diretriz `#BrandLockProtocol` — Trava de Identidade Visual Noviello

> **Quando se aplica:** SEMPRE, antes de entregar qualquer saída visual gerada em
> HTML/CSS/SVG/JSX — artigo de blog, carrossel, banner, criativo de anúncio, e-mail,
> landing page. É uma trava de pré-entrega, não uma sugestão.
>
> **Validador no projeto:** `python scripts/brandlock.py <arquivo.html>` (robusto a
> Unicode astral; versão bash em `scripts/brandlock.sh` para Linux/Mac). Só entregar
> com saída `OK`.

---

## 1. Cores — ALLOWLIST FECHADA (nunca denylist)

Só existem estas cores. Qualquer hex fora desta lista é erro, mesmo que "pareça" da marca.

| Token | Hex | Uso |
|---|---|---|
| Claret | `#68192E` | Acentos, bordas, bullets, botões, divisórias, numerais |
| Chocolate Cosmos | `#540D1D` | Fundos escuros, títulos sobre fundo claro |
| Anti-flash White | `#F1F3F2` | Fundos claros, texto sobre fundo escuro |
| Branco | `#FFFFFF` | Containers, cards |
| Texto corpo | `#1A1A1A` | Parágrafos |
| Texto secundário | `#444444` | Metadados, legendas, cargo |

**Único derivado permitido:** Claret em baixa opacidade via `rgba(104,25,46,α)` para
preenchimentos/linhas suaves (ex.: `rgba(104,25,46,.045)`, `rgba(104,25,46,.14)`).
Nada de novos hex para "clarear" cor.

**PROIBIDO (erros reais já cometidos):** creme/`#FAF7F5`/`#FAF8F6`, dourado/`#D4AF37`,
beige, light pink, earthy gray, `#9A8A84`, `#3a0a14`, `#281019`, `#5A4650`, azul
`#2C4A6B`, verde `#4A7B5C` e qualquer derivação não tabelada. **Dourado não é cor da
marca em peça não-Agro** (nem como filete).

```css
/* Bloco-base obrigatório */
.noviello-artigo{
  --claret:#68192E;--cosmos:#540D1D;--anti-flash:#F1F3F2;--white:#FFFFFF;
  --ink:#1A1A1A;--ink-soft:#444444;
  --claret-tint:rgba(104,25,46,.045);--claret-line:rgba(104,25,46,.14);
}
```

Em **fundo escuro** (hero, capa, CTA), o "filete"/detalhe que seria claret deve ser
`anti-flash` para contrastar (claret some sobre claret). Em **fundo claro**, o filete
é claret.

---

## 2. Imagética — ZERO clichê jurídico, ZERO emoji

**Nunca usar** balança (⚖), martelo/gavel, espadas, Têmis, colunas gregas, livro (📖),
nem nenhum emoji como ícone — seja como glyph CSS (`content:"\2696"`), SVG ou imagem.

**Marcadores aprovados** (transmitem hierarquia sem figura):
- Quadrado claret rotacionado 45° (`width:7px;height:7px;background:var(--claret);transform:rotate(45deg)`) — em fundo escuro, usar anti-flash.
- Régua/linha fina claret (26–38×2px) antes de kickers.
- Numeral em Cinzel claret (`01`, `02`, `P`, `R`).
- Barra lateral esquerda claret (`border-left:3px solid var(--claret)`).

---

## 3. Tipografia — TRAVA

Só Cinzel + Poppins + Cormorant Garamond (este último apenas itálico, para dek/subtítulo
editorial e citação em destaque). Nada de Inter, Arial, Roboto ou system fonts.

```css
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,400;1,500;1,600&family=Poppins:wght@300;400;500;600;700&display=swap');
```

---

## 4. Logo — TRAVA

| Fundo da peça | Asset correto | Nunca |
|---|---|---|
| Claro / branco / Anti-flash | logo **claret** (`noviellologoheader.png`) | logo branco em fundo claro |
| Escuro / Claret / Cosmos | logo **branco** (`noviellologofooter.png`) | logo claret em fundo escuro |

- **Nunca recriar o logo** em SVG, texto ou code. Sempre o arquivo original.
- Em fundo claro sem URL da versão claret: colocar o logo branco dentro de um **selo
  claret** (fundo escuro local) — assim o branco fica sobre escuro, regra cumprida.

---

## 5. Identificação OAB (não confundir)

- **Peça institucional / marketing** (carrossel, banner, criativo, rodapé): `OAB/SP nº 21.788` (sociedade).
- **Artigo editorial com byline do autor** (bio "Dr. Mario..."): `OAB/SP 370.796` (pessoal).

---

## 6. Pré-entrega — VALIDADOR

Rodar `python scripts/brandlock.py <arquivo.html>` antes de entregar. Checa: (a) cores
fora da allowlist, (b) emoji/ícone clichê (incl. astrais), (c) glyph clichê em CSS
`content`, (d) fontes não autorizadas.

**Checklist humano (o que o validador não pega):**
- [ ] Logo correto para o fundo (claret em claro / branco em escuro), arquivo original.
- [ ] Sem gradiente roxo/azul ou estética "AI slop"; só Claret↔Cosmos.
- [ ] Sem `rgba()` de cores fora da allowlist (ex.: rgba dourado/azul/verde) — o
      validador só pega hex; rgba precisa de olho humano. Único rgba permitido: claret.
- [ ] Contraste de texto ≥ 4.5:1 (WCAG AA).
- [ ] OAB correta para o tipo de peça (seção 5).
- [ ] Disclaimer Prov. 205/2021 presente em conteúdo público.

---

## Origem

Consolidado em 2026-05-29 após os erros recorrentes (creme/dourado e ícones ⚖/📖) no
ciclo ITBI LC 227. Substitui a tolerância anterior a "dourado no filete". Referência
de aplicação correta: `producao/artigo-itbi-lc227-ata-notarial/` (pós-correção).
