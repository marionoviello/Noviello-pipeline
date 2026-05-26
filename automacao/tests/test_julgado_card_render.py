"""Testes do julgado_card_render — preenchimento do HTML do card.

A chamada ao Playwright (subprocess) NAO e testada — testes ficam no
preenchimento de string (_preencher_card). renderizar_card e testado
via mock do subprocess no test_julgado_producer.
"""

from src.config import AUTOMACAO_DIR
from src.julgado_card_render import _preencher_card

TEMPLATE = (AUTOMACAO_DIR / "templates" / "julgado-card.html").read_text(encoding="utf-8")


def _dados_completos():
    return {
        "area": "Direito Imobiliario",
        "orgao": "STJ",
        "orgao_completo": "Terceira Turma do STJ",
        "turma": "3a Turma · Unanimidade",
        "processo_id": "REsp 2.215.421/SE",
        "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi",
        "relator_curto": "Min. Nancy Andrighi",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve ser interpretado de forma ampla",
        "carimbo": "Unanimidade",
        "label_doc": "Documento Analisado",
        "legenda_doc": "Recibo de compra",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "Usucapiao ordinaria"}],
        "tema_rodape": "Usucapiao Ordinaria",
        "tema_rodape_sub": "Recibo como Justo Titulo",
        "assinatura": "T. M. S.",
    }


def test_preencher_card_substitui_campos_basicos():
    out = _preencher_card(TEMPLATE, _dados_completos(), canal="li")
    assert "Recibo basta como justo titulo" in out
    assert "REsp 2.215.421/SE" in out
    assert "Min. Nancy Andrighi" in out
    assert "{tese}" not in out
    assert "{processo}" not in out
    assert "{relator}" not in out


def test_carimbo_default_unanimidade_quando_vazio():
    dados = _dados_completos()
    dados["carimbo"] = ""
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Unanimidade" in out


def test_carimbo_default_quando_None():
    dados = _dados_completos()
    dados["carimbo"] = None
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Unanimidade" in out


def test_carimbo_dinamico_maioria():
    dados = _dados_completos()
    # neutraliza outras ocorrencias de "Unanimidade" na fixture
    dados["turma"] = "3a Turma"
    dados["carimbo"] = "Maioria"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Maioria" in out
    # carimbo dinamico veio — default Unanimidade NAO foi usado
    assert "Unanimidade" not in out


def test_carimbo_dinamico_repetitivo_tema():
    dados = _dados_completos()
    dados["carimbo"] = "Repetitivo Tema 1234"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Repetitivo Tema 1234" in out


def test_subtitulo_marca_li_padrao():
    dados = _dados_completos()
    out = _preencher_card(TEMPLATE, dados, canal="li")
    # subtitulo LI tem "Imobiliario e Sucessorio" (sem "Direito Senior")
    assert "Imobili" in out
    assert "Direito Sênior" not in out


def test_subtitulo_marca_ig_padrao():
    dados = _dados_completos()
    out = _preencher_card(TEMPLATE, dados, canal="ig")
    assert "Direito Sênior" in out


def test_subtitulo_marca_override_explicito():
    """Se dados['subtitulo_marca_li'] vier explicito, usa esse."""
    dados = _dados_completos()
    dados["subtitulo_marca_li"] = "Advocacia · Customizado"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Advocacia · Customizado" in out


def test_escapa_html_em_campos():
    dados = _dados_completos()
    dados["tese"] = "Tese & <script>alert(1)</script>"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "&amp;" in out
    assert "&lt;script&gt;" in out
    assert "<script>alert(1)</script>" not in out


def test_fundamentos_renderiza_lista():
    dados = _dados_completos()
    dados["fundamentos"] = [
        {"fonte": "Art. 1.242 CC", "texto": "Usucapiao ordinaria"},
        {"fonte": "Sumula 237", "texto": "Pode ser arguido em defesa"},
    ]
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "Art. 1.242 CC" in out
    assert "Sumula 237" in out
    assert "Pode ser arguido" in out


def test_processo_id_mapeia_para_template_processo():
    """O template usa {processo}; o dict usa processo_id (nomenclatura do parser)."""
    dados = _dados_completos()
    dados["processo_id"] = "RE 1.234.567"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "RE 1.234.567" in out


def test_orgao_aparece_no_selo_e_no_orgao_completo():
    dados = _dados_completos()
    dados["orgao"] = "STF"
    dados["orgao_completo"] = "Plenario do STF"
    out = _preencher_card(TEMPLATE, dados, canal="li")
    assert "STF" in out
    assert "Plenario do STF" in out
