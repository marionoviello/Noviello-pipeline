from src.article_styler import _classificar_tabelas, estilizar
from src.config import AUTOMACAO_DIR

TEMPLATES = AUTOMACAO_DIR / "templates"

HTML_CRU = (
    "<h2>Titulo da Secao</h2>"
    "<p>Um paragrafo com <strong>negrito</strong>.</p>"
    "<ul><li>item 1</li><li>item 2</li></ul>"
    "<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>"
)


def test_classificar_tabelas_adiciona_classe():
    out = _classificar_tabelas("<table><tr><td>x</td></tr></table>")
    assert '<table class="noviello-tabela">' in out


def test_classificar_tabelas_nao_duplica_classe():
    entrada = '<table class="ja-tem"><tr><td>x</td></tr></table>'
    assert _classificar_tabelas(entrada) == entrada


def test_estilizar_envolve_no_template():
    out = estilizar(HTML_CRU, "Inventario Extrajudicial", TEMPLATES)
    # wrapper e estilo da marca presentes
    assert 'class="noviello-artigo"' in out
    assert "--claret: #68192E" in out
    assert "Cinzel" in out
    # conteudo original preservado
    assert "Titulo da Secao" in out
    assert "<strong>negrito</strong>" in out
    # tabela recebeu a classe
    assert 'class="noviello-tabela"' in out
    # titulo no <head>
    assert "Inventario Extrajudicial" in out


def test_estilizar_escapa_titulo():
    out = estilizar("<p>x</p>", "Aspas & <perigo>", TEMPLATES)
    assert "&amp;" in out and "&lt;perigo&gt;" in out


def test_estilizar_categoria_chip_e_tags():
    out = estilizar(
        HTML_CRU,
        "T",
        TEMPLATES,
        categorias=["Sucessório"],
        tags=["doação", "usufruto", "ITCMD"],
    )
    # chip da primeira categoria no header
    assert '<span class="chip">Sucessório</span>' in out
    # tags renderizadas no rodape
    assert "tags-rodape" in out and "doação" in out and "ITCMD" in out


def test_estilizar_meta_tags_seo():
    out = estilizar(
        HTML_CRU,
        "Titulo SEO",
        TEMPLATES,
        canonical_url="https://noviello.adv.br/teste-seo/",
        imagem_destaque="https://example.com/img.png",
    )
    assert 'rel="canonical"' in out
    assert 'href="https://noviello.adv.br/teste-seo/"' in out
    assert 'property="og:image"' in out
    assert "https://example.com/img.png" in out
    assert "application/ld+json" in out
    assert '"@type": "Article"' in out


def test_estilizar_passos_circulos():
    """OL com <li><strong>X:</strong> ...</li> vira ol.passos"""
    html_passos = (
        "<h2>Como Fazer</h2>"
        "<ol>"
        "<li><strong>Primeiro passo:</strong> faca isso.</li>"
        "<li><strong>Segundo passo:</strong> faca aquilo.</li>"
        "<li><strong>Terceiro passo:</strong> finalize.</li>"
        "</ol>"
    )
    out = estilizar(html_passos, "T", TEMPLATES, incluir_toc=False)
    assert '<ol class="passos"' in out


def test_estilizar_cards_grid():
    """UL com 3-6 itens '<strong>Titulo:</strong> texto' vira card-grid"""
    html_cards = (
        "<ul>"
        "<li><strong>Card Um:</strong> primeiro card.</li>"
        "<li><strong>Card Dois:</strong> segundo card.</li>"
        "<li><strong>Card Tres:</strong> terceiro card.</li>"
        "</ul>"
    )
    out = estilizar(html_cards, "T", TEMPLATES, incluir_toc=False)
    assert '<div class="card-grid">' in out
    assert '<div class="card-titulo">Card Um</div>' in out


def test_estilizar_callout_saiba_que():
    html_callout = "<p><strong>Saiba que:</strong> conteudo educativo.</p>"
    out = estilizar(html_callout, "T", TEMPLATES, incluir_toc=False)
    assert 'class="callout callout-saiba-que"' in out
    assert "<div class=\"titulo\">Saiba que</div>" in out


def test_estilizar_bio_sem_oab_sem_avalimob():
    out = estilizar(HTML_CRU, "T", TEMPLATES)
    # cargo no HTML cru (maiusculas vem do CSS text-transform)
    assert "Fundador da Noviello Advocacia" in out
    assert "Avalimob" not in out
    assert "OAB/SP 370" not in out


def test_estilizar_pode_omitir_bio():
    out = estilizar(HTML_CRU, "T", TEMPLATES, incluir_bio=False)
    # CSS de .bio-autor fica no <style>, mas a tag <aside> nao deve aparecer
    assert '<aside class="bio-autor">' not in out


def test_estilizar_faq_gera_schema():
    html_faq = (
        "<h2>Perguntas Frequentes</h2>"
        "<h3>O que e isso?</h3><p>Resposta um.</p>"
        "<h3>E aquilo?</h3><p>Resposta dois.</p>"
        "<h3>Outra duvida?</h3><p>Resposta tres.</p>"
    )
    out = estilizar(html_faq, "T", TEMPLATES, incluir_toc=False)
    assert 'class="faq"' in out
    assert "FAQPage" in out
    assert '"name": "O que e isso?"' in out
