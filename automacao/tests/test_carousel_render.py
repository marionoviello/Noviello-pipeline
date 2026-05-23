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
