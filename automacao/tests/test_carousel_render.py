from src.carousel_render import _preencher
from src.config import AUTOMACAO_DIR

TEMPLATE = (AUTOMACAO_DIR / "templates" / "slide-carrossel.html").read_text(encoding="utf-8")


def test_preencher_substitui_campos():
    out = _preencher(TEMPLATE, {"titulo": "Meu Titulo", "corpo": "linha 1\nlinha 2"}, 2, 8)
    assert "Meu Titulo" in out
    assert "2 / 8" in out
    assert "linha 1<br>linha 2" in out
    assert "{titulo}" not in out
    assert "{corpo}" not in out
    assert "{numero}" not in out


def test_preencher_escapa_html():
    out = _preencher(TEMPLATE, {"titulo": "A & B <perigo>", "corpo": "ok"}, 1, 1)
    assert "&amp;" in out
    assert "&lt;perigo&gt;" in out


# ---- Batch (a): meta de julgado + carimbo (opcionais, retrocompatíveis) -----

def test_slide_sem_julgado_nao_renderiza_meta_nem_carimbo():
    """Slide sem campos novos não gera barra de meta nem carimbo."""
    out = _preencher(TEMPLATE, {"titulo": "T", "corpo": "C"}, 1, 5)
    assert 'class="meta-julgado"' not in out
    assert 'class="carimbo-decisao"' not in out
    assert "{meta_julgado_html}" not in out  # placeholder substituído
    assert "{carimbo_html}" not in out


def test_slide_com_area_renderiza_chip():
    slide = {"titulo": "T", "corpo": "C", "area": "Direito Imobiliário"}
    out = _preencher(TEMPLATE, slide, 1, 5)
    assert 'class="meta-julgado"' in out
    assert 'class="chip-area"' in out
    assert "Direito Imobiliário" in out


def test_slide_com_selo_tribunal_e_processo():
    slide = {
        "titulo": "T", "corpo": "C",
        "selo_tribunal": "STJ",
        "processo_id": "REsp 2.215.421/SE",
    }
    out = _preencher(TEMPLATE, slide, 1, 5)
    assert 'class="selo-trib">STJ' in out
    assert 'class="processo">REsp 2.215.421/SE' in out


def test_slide_com_carimbo_unanimidade():
    slide = {"titulo": "T", "corpo": "C", "carimbo": "Unanimidade"}
    out = _preencher(TEMPLATE, slide, 1, 5)
    assert 'class="carimbo-decisao"' in out
    assert "Unanimidade" in out
    # carimbo aparece DEPOIS do topo, ANTES do corpo-wrap (posicao absoluta)
    pos_topo_fim = out.find('</div>', out.find('class="topo"'))
    pos_carimbo = out.find('class="carimbo-decisao"')
    pos_corpo_wrap = out.find('class="corpo-wrap"')
    assert pos_topo_fim < pos_carimbo < pos_corpo_wrap


def test_julgado_completo_card_li_consistente():
    """Combo igual ao card LinkedIn: chip + selo + processo + carimbo."""
    slide = {
        "titulo": "Recibo basta como justo título",
        "corpo": "STJ revoluciona usucapião ordinária.",
        "area": "Direito Imobiliário",
        "selo_tribunal": "STJ",
        "processo_id": "REsp 2.215.421/SE",
        "carimbo": "Unanimidade",
    }
    out = _preencher(TEMPLATE, slide, 1, 9)
    # todos os 4 elementos novos aparecem
    assert 'Direito Imobiliário' in out
    assert 'STJ' in out
    assert 'REsp 2.215.421/SE' in out
    assert 'Unanimidade' in out
    # nao quebrou o resto
    assert "Recibo basta" in out
    assert "1 / 9" in out


def test_escapa_html_em_campos_de_julgado():
    """Campos de julgado também passam por escape."""
    slide = {
        "titulo": "T", "corpo": "C",
        "area": "Imobiliário & <script>",
        "carimbo": "x<script>",
    }
    out = _preencher(TEMPLATE, slide, 1, 1)
    assert "&amp;" in out
    assert "&lt;script&gt;" in out
    assert "<script>" not in out  # nenhum tag injetado
