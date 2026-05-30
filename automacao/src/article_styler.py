"""Estiliza o HTML cru do plugin no padrao visual do escritorio.

O plugin "Gerador IA Pro" gera HTML semantico sem estilo (h2/h3/p/ul/table). Esta
camada injeta esse conteudo no template-mestre artigo-noviello.html (paleta da marca,
Cinzel/Poppins) e enriquece o resultado com:

- Meta tags SEO (description, OpenGraph, Twitter Card, canonical)
- JSON-LD Article schema (e FAQPage quando aplicavel)
- Hero (categoria + data + tempo de leitura, eyebrow, titulo, lead, imagem opcional)
- Sumario (TOC) automatico baseado em H2/H3
- Callouts: Importante, Atencao, Dica, Saiba-Que (juridico), Exemplo Pratico
- FAQ estilizada (detecta secao "Perguntas Frequentes")
- Drop cap no primeiro paragrafo
- Bio do autor padronizada
- CTA box final + Disclaimer OAB 205/2021

Transformacao mecanica: nao reescreve o conteudo, so reorganiza/decora.
"""

from __future__ import annotations

import html as _html
import json
import re
from datetime import date, datetime
from pathlib import Path

TEMPLATE = "artigo-noviello.html"


def limpar_html_legado(html: str) -> str:
    """Extrai conteudo semantico limpo de HTML legado (Gutenberg, Classic, sujo).

    Remove comentarios (wp: blocks), atributos style/class/id/data-*, desempacota
    div/span (mantendo o conteudo), tira tags vazias e normaliza espacos.
    Preserva h1-h6, p, ul/ol/li, table/thead/tbody/tr/td/th, strong/em, a, blockquote,
    figure/img (imagens do corpo sao mantidas). Pronto para passar pelo estilizar().
    """
    h = html or ""
    # 0. blocos nao-conteudo e moldura de template antigo (style/script + hero/cta/bio)
    h = re.sub(r"<style[^>]*>.*?</style>", "", h, flags=re.DOTALL | re.IGNORECASE)
    h = re.sub(r"<script[^>]*>.*?</script>", "", h, flags=re.DOTALL | re.IGNORECASE)
    h = re.sub(r"<header[^>]*>.*?</header>", "", h, flags=re.DOTALL | re.IGNORECASE)
    h = re.sub(r"<aside[^>]*>.*?</aside>", "", h, flags=re.DOTALL | re.IGNORECASE)
    # 1. comentarios HTML (inclui <!-- wp:... -->)
    h = re.sub(r"<!--.*?-->", "", h, flags=re.DOTALL)
    # 1b. emojis / icones clichê (o padrao Noviello nao usa nenhum)
    h = re.sub("[\U0001F000-\U0001FAFF☀-➿⚐-⚗⚔⚱]", "", h)
    # 2. atributos de estilo/classe/ids/acessibilidade (mantem href/src/alt/colspan/rowspan)
    h = re.sub(r'\s+style=("[^"]*"|\'[^\']*\')', "", h, flags=re.IGNORECASE)
    h = re.sub(r'\s+class=("[^"]*"|\'[^\']*\')', "", h, flags=re.IGNORECASE)
    h = re.sub(r'\s+(?:id|role|width|height|align|valign|bgcolor)=("[^"]*"|\'[^\']*\')',
               "", h, flags=re.IGNORECASE)
    h = re.sub(r'\s+(?:data|aria)-[\w-]+=("[^"]*"|\'[^\']*\')', "", h, flags=re.IGNORECASE)
    # 3. desempacota div/span (mantem o conteudo interno)
    h = re.sub(r"</?(?:div|span)\s*>", "", h, flags=re.IGNORECASE)
    h = re.sub(r"<(?:div|span)[^>]*>", "", h, flags=re.IGNORECASE)
    # 4. tags vazias / lixo
    h = re.sub(r"<sup>\s*</sup>", "", h, flags=re.IGNORECASE)
    h = re.sub(r"<(p|h[1-6]|li|strong|em|blockquote)>\s*</\1>", "", h, flags=re.IGNORECASE)
    # 5. normaliza espacos (sem colar palavras)
    h = re.sub(r"[ \t]+", " ", h)
    h = re.sub(r"\n\s*\n\s*\n+", "\n\n", h)
    return h.strip()

# Padroes que disparam callouts (caso-insensitivo, comeco do texto do paragrafo)
_CALLOUT_PADROES = [
    (re.compile(r"^\s*<strong>\s*(saiba\s+que|nota\s+juridica|fundamento\s+legal|base\s+legal)\s*[:.\-—]?\s*</strong>", re.I),
     "callout-saiba-que", "Saiba que"),
    (re.compile(r"^\s*<strong>\s*(exemplo\s+pr[áa]tico|exemplo|caso\s+concreto|na\s+pr[áa]tica)\s*[:.\-—]?\s*</strong>", re.I),
     "callout-exemplo", "Exemplo prático"),
    (re.compile(r"^\s*<strong>\s*(importante|crítico|crucial|essencial)\s*[:.\-—]?\s*</strong>", re.I),
     "callout-importante", "Importante"),
    (re.compile(r"^\s*<strong>\s*(aten[çc][ãa]o|cuidado|alerta|aviso)\s*[:.\-—]?\s*</strong>", re.I),
     "callout-atencao", "Atenção"),
    (re.compile(r"^\s*<strong>\s*(dica|sugest[ãa]o|recomenda[çc][ãa]o|pro\s*tip)\s*[:.\-—]?\s*</strong>", re.I),
     "callout-dica", "Dica"),
]

# Texto padrao do CTA final
_CTA_HTML = """  <aside class="cta-final">
    <h3 class="cta-titulo">Precisa de orientação personalizada?</h3>
    <p>Cada caso tem particularidades que merecem análise individualizada. A Noviello Advocacia atende presencial e remoto, com agendamento direto.</p>
    <a class="cta-botao" href="https://noviello.adv.br/contato">Agendar consulta</a>
    <div class="cta-contato">
      <span><a href="tel:+551141115560">(11) 4111-5560</a></span>
      <span><a href="https://noviello.adv.br">noviello.adv.br</a></span>
      <span><a href="https://instagram.com/novielloadv">@novielloadv</a></span>
    </div>
  </aside>"""

# Disclaimer OAB 205/2021
_DISCLAIMER_HTML = """  <p class="disclaimer">
    <strong>Aviso editorial:</strong> este conteúdo é informativo e não constitui
    aconselhamento jurídico. Cada caso depende de análise individualizada por
    advogado especializado. Conteúdo produzido em conformidade com o Provimento
    OAB 205/2021.
  </p>"""

# Bio do autor (fixa, anexada antes do CTA)
_BIO_AUTOR_HTML = """  <aside class="bio-autor">
    <div class="bio-foto">MN</div>
    <div class="bio-conteudo">
      <h3>Dr. Mario Luiz Noviello Junior</h3>
      <p class="bio-cargo">Fundador da Noviello Advocacia</p>
      <p class="bio-descricao">Advogado especializado em Direito Sênior, Imobiliário, Sucessório e Saúde Suplementar. Presidente da Comissão de Direito Imobiliário e Urbanístico da OAB Jabaquara e Coordenador do Núcleo de Direito Urbanístico da Ad Notare.</p>
      <p class="bio-contato">
        <a href="https://noviello.adv.br">noviello.adv.br</a> ·
        <a href="https://instagram.com/novielloadv">@novielloadv</a> ·
        <a href="tel:+551141115560">(11) 4111-5560</a>
      </p>
    </div>
  </aside>"""

_MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

_LOGO_URL = "https://noviello.adv.br/wp-content/uploads/2024/01/cropped-logo-noviello.png"
_OG_IMAGE_DEFAULT = "https://noviello.adv.br/wp-content/uploads/2024/01/og-default.jpg"


def _classificar_tabelas(html: str) -> str:
    return re.sub(
        r"<table(?![^>]*\bclass=)([^>]*)>",
        r'<table class="noviello-tabela"\1>',
        html,
        flags=re.IGNORECASE,
    )


def _strip_h1_titulo(html: str, titulo: str) -> str:
    """Remove H2/H1 inicial duplicado do titulo (vai pro Hero)."""
    titulo_normalizado = re.sub(r"\s+", " ", titulo).strip().lower()
    def matcher(m: re.Match) -> str:
        inner = re.sub(r"<[^>]+>", "", m.group(2)).strip().lower()
        return "" if inner == titulo_normalizado else m.group(0)
    html = re.sub(r"^\s*<(h[12])[^>]*>(.*?)</\1>", matcher, html,
                  count=1, flags=re.DOTALL | re.IGNORECASE)
    return html


def _extrair_lead(html: str) -> tuple[str, str]:
    """Pega o 1o paragrafo como lead e o REMOVE do corpo (evita duplicar no hero).

    So promove a lead se o paragrafo tiver 60-320 chars (tamanho de dek). Fora
    disso, mantem no corpo e o hero fica sem lead.
    """
    m = re.search(r"<p[^>]*>(.*?)</p>", html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return "", html
    lead_puro = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    lead_puro = re.sub(r"\s+", " ", lead_puro)
    if len(lead_puro) < 60 or len(lead_puro) > 550:
        return "", html
    html_sem = (html[:m.start()] + html[m.end():]).lstrip()
    return lead_puro, html_sem


def _remover_indice_textual(html: str) -> str:
    """Remove 'indice' textual embutido (ex: 'Neste artigo voce vai ler' + lista),
    que duplicaria o sumario (TOC) gerado automaticamente."""
    padrao = re.compile(
        r"(?:<(?:p|h[1-6])[^>]*>\s*)?(?:<strong>\s*)?"
        r"[^<>]{0,30}?neste artigo[^<>]{0,60}?(?:ler|ver|encontrar|aprender)[^<>]{0,12}?:?\s*"
        r"(?:</strong>\s*)?(?:</(?:p|h[1-6])>\s*)?\s*"
        r"<(ol|ul)\b[^>]*>.*?</\1>",
        re.IGNORECASE | re.DOTALL,
    )
    return padrao.sub("", html, count=1)


def _gerar_meta_description(lead: str, conteudo: str) -> str:
    """Meta description: usa o lead se houver, senao primeira frase do corpo."""
    if lead:
        return lead[:160].rsplit(" ", 1)[0]
    texto = re.sub(r"<[^>]+>", "", conteudo)
    texto = re.sub(r"\s+", " ", texto).strip()
    return (texto[:160].rsplit(" ", 1)[0] + "…") if texto else ""


def _calcular_tempo_leitura(html: str) -> int:
    """Retorna minutos de leitura (200 palavras/min, minimo 1)."""
    texto = re.sub(r"<[^>]+>", " ", html)
    palavras = len(texto.split())
    return max(1, round(palavras / 200))


def _formatar_data_pt(d: date | datetime | None) -> tuple[str, str]:
    """Devolve (data_legivel_pt, data_iso)."""
    if d is None:
        d = datetime.now()
    if isinstance(d, datetime):
        iso = d.isoformat()
        d_only = d.date()
    else:
        iso = d.isoformat()
        d_only = d
    legivel = f"{d_only.day} de {_MESES_PT[d_only.month]} de {d_only.year}"
    return legivel, iso


def _gerar_toc(html: str) -> tuple[str, str]:
    """Constroi sumario navegavel. Adiciona IDs aos headings."""
    headings: list[tuple[int, str, str]] = []
    contador = [0]

    def slug(texto: str, n: int) -> str:
        s = re.sub(r"<[^>]+>", "", texto).strip().lower()
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50] or f"sec{n}"
        return f"sec-{n}-{s}"

    def adicionar_id(m: re.Match) -> str:
        contador[0] += 1
        nivel = int(m.group(1))
        attrs = m.group(2) or ""
        texto_inner = m.group(3)
        if re.search(r"\bid=", attrs, flags=re.IGNORECASE):
            return m.group(0)
        sid = slug(texto_inner, contador[0])
        headings.append((nivel, sid, re.sub(r"<[^>]+>", "", texto_inner).strip()))
        return f"<h{nivel} id=\"{sid}\"{attrs}>{texto_inner}</h{nivel}>"

    html_com_ids = re.sub(
        r"<h([23])([^>]*)>(.*?)</h\1>",
        adicionar_id,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if len(headings) < 3:
        return "", html_com_ids

    # so H2 no sumario (deixa H3 como subsecao)
    h2_headings = [(s, t) for n, s, t in headings if n == 2]
    if len(h2_headings) < 2:
        h2_headings = [(s, t) for _, s, t in headings]

    linhas = ['  <nav class="toc"><div class="toc-titulo">Sumário</div><ol>']
    for sid, texto in h2_headings:
        linhas.append(f'    <li><a href="#{sid}">{_html.escape(texto)}</a></li>')
    linhas.append("  </ol></nav>")
    return "\n".join(linhas), html_com_ids


def _detectar_passos(html: str) -> str:
    """Detecta <ol> em que TODOS os <li> comecam com <strong>...</strong> e marca
    como class='passos' (numeros em circulo dourado)."""
    def processar(m: re.Match) -> str:
        ol_inteiro = m.group(0)
        attrs = m.group(1) or ""
        if re.search(r"\bclass=", attrs, flags=re.IGNORECASE):
            return ol_inteiro
        itens = re.findall(r"<li[^>]*>(.*?)</li>", ol_inteiro,
                           flags=re.DOTALL | re.IGNORECASE)
        if len(itens) < 3:
            return ol_inteiro
        # cada item precisa comecar com <strong>...</strong> (ou <p><strong>)
        padrao_item = re.compile(r"^\s*(?:<p[^>]*>\s*)?<strong>", re.IGNORECASE)
        if not all(padrao_item.match(it) for it in itens):
            return ol_inteiro
        return ol_inteiro.replace("<ol", '<ol class="passos"', 1)

    return re.sub(r"<ol([^>]*)>.*?</ol>", processar, html,
                  flags=re.DOTALL | re.IGNORECASE)


def _detectar_cards(html: str) -> str:
    """Detecta <ul> em que TODOS os <li> tem formato '<strong>Titulo:</strong> texto'
    e converte em card-grid (max 6 itens, min 3)."""
    def processar(m: re.Match) -> str:
        ul_inteiro = m.group(0)
        attrs = m.group(1) or ""
        if re.search(r"\bclass=", attrs, flags=re.IGNORECASE):
            return ul_inteiro
        itens = re.findall(r"<li[^>]*>(.*?)</li>", ul_inteiro,
                           flags=re.DOTALL | re.IGNORECASE)
        if not (3 <= len(itens) <= 6):
            return ul_inteiro
        # cada item: <strong>Titulo</strong> + resto
        padrao = re.compile(r"^\s*<strong>(.*?)</strong>[\s:.\-—]*(.*)$",
                            re.DOTALL | re.IGNORECASE)
        cards = []
        for it in itens:
            mp = padrao.match(it.strip())
            if not mp:
                return ul_inteiro  # nao casa, devolve original
            titulo = re.sub(r"<[^>]+>", "", mp.group(1)).strip()
            titulo = titulo.rstrip(":.,-— ")
            corpo = mp.group(2).strip()
            # so vira card se o titulo for curto (<= 60 chars) e corpo nao for vazio
            if not titulo or len(titulo) > 60 or not corpo:
                return ul_inteiro
            cards.append(
                f'    <div class="card">'
                f'<div class="card-titulo">{_html.escape(titulo)}</div>'
                f'<p>{corpo}</p></div>'
            )
        return '  <div class="card-grid">\n' + "\n".join(cards) + "\n  </div>"

    return re.sub(r"<ul([^>]*)>.*?</ul>", processar, html,
                  flags=re.DOTALL | re.IGNORECASE)


def _gerar_tags_rodape(tags: list[str] | None) -> str:
    if not tags:
        return ""
    chips = "\n".join(
        f'      <span class="tag">{_html.escape(t)}</span>' for t in tags
    )
    return (
        '  <aside class="tags-rodape">\n'
        '    <div class="tags-rodape-titulo">Tópicos relacionados</div>\n'
        '    <div class="tags-lista">\n'
        f'{chips}\n'
        '    </div>\n'
        '  </aside>'
    )


def _detectar_callouts(html: str) -> str:
    """Transforma <p><strong>Importante:</strong> texto</p> em <div class="callout-*">."""
    def processar(m: re.Match) -> str:
        paragrafo = m.group(0)
        # extrai conteudo interno do <p>
        inner_match = re.match(
            r"^\s*<p[^>]*>(.*?)</p>\s*$", paragrafo,
            re.DOTALL | re.IGNORECASE,
        )
        if not inner_match:
            return paragrafo
        inner = inner_match.group(1)

        for padrao, classe, titulo_default in _CALLOUT_PADROES:
            if padrao.search(inner):
                novo_inner = padrao.sub("", inner, count=1).strip()
                novo_inner = re.sub(r"^[\s:.\-—]+", "", novo_inner)
                return (
                    f'<div class="callout {classe}">'
                    f'<div class="titulo">{titulo_default}</div>'
                    f'<p>{novo_inner}</p></div>'
                )
        return paragrafo

    return re.sub(r"<p[^>]*>.*?</p>", processar, html,
                  flags=re.DOTALL | re.IGNORECASE)


def _detectar_faq(html: str) -> tuple[str, list[dict]]:
    """Detecta secao 'Perguntas frequentes' e converte em <div class="faq">.

    Devolve (html_modificado, lista_de_perguntas_para_json_ld).
    Procura H2 com 'pergunta' ou 'faq' no titulo; a partir dali, captura
    pares H3-pergunta + paragrafo-resposta.
    """
    # busca H2 de FAQ
    faq_match = re.search(
        r'<h2[^>]*>([^<]*(?:pergunta|faq|d[úu]vida)[^<]*)</h2>',
        html,
        flags=re.IGNORECASE,
    )
    if not faq_match:
        return html, []

    inicio_faq = faq_match.start()
    fim_h2 = faq_match.end()
    titulo_faq = re.sub(r"<[^>]+>", "", faq_match.group(1)).strip()

    # captura conteudo depois do H2 ate o proximo H2 ou fim
    resto = html[fim_h2:]
    proximo_h2 = re.search(r"<h2[^>]*>", resto, flags=re.IGNORECASE)
    bloco_faq_inner = resto[:proximo_h2.start()] if proximo_h2 else resto
    posicao_pos_faq = fim_h2 + (proximo_h2.start() if proximo_h2 else len(resto))

    # captura pares (H3, paragrafos seguintes)
    perguntas_html: list[str] = []
    perguntas_data: list[dict] = []

    # padrao: H3 (pode terminar com ? ou nao) seguido por <p>...</p> (pode ter varios)
    itens = re.findall(
        r'<h3[^>]*>(.*?)</h3>\s*((?:<p[^>]*>.*?</p>\s*)+)',
        bloco_faq_inner,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not itens:
        # nao detectou estrutura H3/P — devolve como esta
        return html, []

    for pergunta_inner, respostas_html in itens:
        pergunta_texto = re.sub(r"<[^>]+>", "", pergunta_inner).strip()
        resposta_texto = re.sub(r"<[^>]+>", " ", respostas_html).strip()
        resposta_texto = re.sub(r"\s+", " ", resposta_texto)
        perguntas_html.append(
            f'    <div class="faq-item">\n'
            f'      <p class="pergunta">{_html.escape(pergunta_texto)}</p>\n'
            f'      <div class="resposta">{respostas_html.strip()}</div>\n'
            f'    </div>'
        )
        perguntas_data.append({"pergunta": pergunta_texto, "resposta": resposta_texto})

    faq_bloco = (
        f'<section class="faq">\n'
        f'  <h2 class="faq-titulo">{_html.escape(titulo_faq)}</h2>\n'
        + "\n".join(perguntas_html)
        + "\n  </section>"
    )

    html_novo = html[:inicio_faq] + faq_bloco + html[posicao_pos_faq:]
    return html_novo, perguntas_data


def _gerar_eyebrow(titulo: str, categorias: list[str] | None = None) -> str:
    """Eyebrow: usa categorias se houver, senao palavras-chave do titulo."""
    if categorias:
        return " · ".join(c.upper() for c in categorias[:3])
    palavras = re.findall(r"\b[A-ZÁ-Ú][a-zá-úç]+\b", titulo or "")
    if not palavras:
        return "ANÁLISE JURÍDICA"
    return " · ".join(palavras[:3]).upper()


def _gerar_json_ld(
    titulo: str,
    descricao: str,
    imagem: str,
    canonical_url: str,
    data_iso: str,
    faq_items: list[dict],
) -> str:
    """Gera JSON-LD Article (+ FAQPage se houver)."""
    schemas: list[dict] = []

    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": titulo,
        "description": descricao,
        "image": imagem,
        "datePublished": data_iso,
        "dateModified": data_iso,
        "author": {
            "@type": "Person",
            "name": "Dr. Mario Luiz Noviello Junior",
            "url": "https://noviello.adv.br/sobre/",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Noviello Advocacia",
            "logo": {"@type": "ImageObject", "url": _LOGO_URL},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
    }
    schemas.append(article)

    if faq_items:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q["pergunta"],
                    "acceptedAnswer": {"@type": "Answer", "text": q["resposta"]},
                }
                for q in faq_items
            ],
        }
        schemas.append(faq_schema)

    if len(schemas) == 1:
        return json.dumps(schemas[0], ensure_ascii=False, indent=2)
    return json.dumps(schemas, ensure_ascii=False, indent=2)


def estilizar(
    html_cru: str,
    titulo: str,
    templates_dir: Path,
    *,
    eyebrow: str | None = None,
    lead: str | None = None,
    categorias: list[str] | None = None,
    tags: list[str] | None = None,
    imagem_destaque: str | None = None,
    data_publicacao: date | datetime | None = None,
    canonical_url: str = "",
    incluir_toc: bool = True,
    incluir_cta: bool = True,
    incluir_disclaimer: bool = True,
    incluir_bio: bool = True,
) -> str:
    """Devolve o HTML do artigo ja no template do escritorio, enriquecido."""
    template = (Path(templates_dir) / TEMPLATE).read_text(encoding="utf-8")
    conteudo = html_cru.strip()

    # Limpeza inicial
    conteudo = _strip_h1_titulo(conteudo, titulo)
    conteudo = _remover_indice_textual(conteudo)
    conteudo = _classificar_tabelas(conteudo)

    # Lead (extrai do 1o paragrafo e o remove do corpo, evitando duplicacao)
    if lead is None:
        lead, conteudo = _extrair_lead(conteudo)
    lead_final = _html.escape(lead or "")

    # Eyebrow (categorias preferem ao titulo)
    eyebrow_final = (eyebrow or _gerar_eyebrow(titulo, categorias)).strip()

    # Categoria chip: primeira categoria
    if categorias:
        categoria_chip = f'<span class="chip">{_html.escape(categorias[0])}</span>'
    else:
        categoria_chip = ""

    # Data + tempo de leitura
    data_legivel, data_iso = _formatar_data_pt(data_publicacao)
    tempo_leitura = _calcular_tempo_leitura(conteudo)

    # Detecta callouts
    conteudo = _detectar_callouts(conteudo)

    # Detecta passos numerados (<ol> com <li><strong>...</strong>)
    conteudo = _detectar_passos(conteudo)

    # Detecta card-grid (<ul> com <li><strong>Titulo:</strong> texto)
    conteudo = _detectar_cards(conteudo)

    # Detecta FAQ (antes do TOC pq pode ter H3 dentro)
    conteudo, faq_items = _detectar_faq(conteudo)

    # Gera sumario (e adiciona IDs aos headings)
    toc_html, conteudo = ("", conteudo)
    if incluir_toc:
        toc_html, conteudo = _gerar_toc(conteudo)

    # SEO
    meta_description = _gerar_meta_description(lead or "", conteudo)
    og_image = imagem_destaque or _OG_IMAGE_DEFAULT
    json_ld = _gerar_json_ld(
        titulo=titulo,
        descricao=meta_description,
        imagem=og_image,
        canonical_url=canonical_url,
        data_iso=data_iso,
        faq_items=faq_items,
    )

    # Hero com imagem
    if imagem_destaque:
        hero_class = "com-imagem"
        hero_style = f'style="background-image: url({_html.escape(imagem_destaque)})"'
    else:
        hero_class = ""
        hero_style = ""

    cta_final = _CTA_HTML if incluir_cta else ""
    disclaimer = _DISCLAIMER_HTML if incluir_disclaimer else ""
    bio_autor = _BIO_AUTOR_HTML if incluir_bio else ""
    tags_rodape = _gerar_tags_rodape(tags)

    return (
        template.replace("{titulo}", _html.escape(titulo))
        .replace("{meta_description}", _html.escape(meta_description))
        .replace("{canonical_url}", _html.escape(canonical_url))
        .replace("{og_image}", _html.escape(og_image))
        .replace("{data_iso}", data_iso)
        .replace("{json_ld}", json_ld)
        .replace("{hero_class}", hero_class)
        .replace("{hero_style}", hero_style)
        .replace("{categoria_chip}", categoria_chip)
        .replace("{data_publicacao}", data_legivel)
        .replace("{tempo_leitura}", str(tempo_leitura))
        .replace("{eyebrow}", _html.escape(eyebrow_final))
        .replace("{lead}", lead_final)
        .replace("{toc}", toc_html)
        .replace("{conteudo}", conteudo)
        .replace("{tags_rodape}", tags_rodape)
        .replace("{bio_autor}", bio_autor)
        .replace("{cta_final}", cta_final)
        .replace("{disclaimer}", disclaimer)
    )
