"""Testes do parser do Radar — particionar + classificar + extrair."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.julgado_radar.config import AREA_FORA, AREAS_ALVO
from src.julgado_radar.parser import (
    KEYWORDS_AREAS,
    ParserError,
    STJ_ITEM_SCHEMA,
    bloco_e_candidato,
    classificar_area_via_ia,
    extrair_item_via_ia,
    extrair_itens_de_informativo,
    particionar_itens,
)


def _texto_informativo_fake():
    """Simula um informativo STJ com 3 itens. Marcadores 'PROCESSO' e 'REsp'."""
    item_a = "PROCESSO\n" + ("Conteudo do item A com pelo menos duzentos caracteres. " * 6)
    item_b = "REsp 1234567\n" + ("Item B com texto longo o suficiente para passar filtro. " * 6)
    item_c = "AGRAVO REGIMENTAL\n" + ("Item C tambem com tamanho adequado pra ser aceito. " * 6)
    return f"Cabecalho irrelevante.\n\n{item_a}\n\n{item_b}\n\n{item_c}"


def test_particionar_itens_divide_em_blocos():
    texto = _texto_informativo_fake()
    blocos = particionar_itens(texto)
    assert len(blocos) == 3
    # cada bloco tem >= 200 chars
    assert all(len(b) >= 200 for b in blocos)


def test_particionar_itens_texto_vazio():
    assert particionar_itens("") == []
    assert particionar_itens("   \n\n  ") == []


def test_particionar_itens_descarta_blocos_curtos():
    texto = "PROCESSO\ncurto\nREsp 99\n" + ("Item normal " * 50)
    blocos = particionar_itens(texto)
    # so o segundo (longo) sobrevive
    assert len(blocos) == 1


def test_stj_item_schema_tem_required():
    obrig = set(STJ_ITEM_SCHEMA["required"])
    assert obrig == {"relevante", "area", "processo_id", "tese"}


def test_stj_item_schema_area_enum_inclui_fora():
    valores = STJ_ITEM_SCHEMA["properties"]["area"]["enum"]
    for area in AREAS_ALVO:
        assert area in valores
    assert AREA_FORA in valores


# ===== extrair_item_via_ia (delega ao client mockado) =====

def test_extrair_item_via_ia_delega_ao_anthropic():
    cli = MagicMock()
    cli.extrair_item_stj.return_value = {
        "relevante": True, "area": "imobiliario",
        "processo_id": "REsp X", "tese": "T",
    }
    out = extrair_item_via_ia("texto do bloco", cli)
    assert out["processo_id"] == "REsp X"
    cli.extrair_item_stj.assert_called_once_with("texto do bloco", STJ_ITEM_SCHEMA)


# ===== extrair_itens_de_informativo (pipeline completo) =====

def _ler_pdf_fake(pdf_path):
    return _texto_informativo_fake()


def test_extrair_itens_de_informativo_aceita_3_imobiliarios(tmp_path, monkeypatch):
    """3 itens, todos imobiliario, todos validos."""
    cli = MagicMock()
    cli.extrair_item_stj.side_effect = [
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp A", "tese": "Tese A"},
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp B", "tese": "Tese B"},
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp C", "tese": "Tese C"},
    ]
    pdf_fake = tmp_path / "fake.pdf"
    pdf_fake.write_bytes(b"%PDF-1.4")
    resultado = extrair_itens_de_informativo(pdf_fake, cli, ler_pdf=_ler_pdf_fake, pre_filtro=False)
    assert len(resultado["aceitos"]) == 3
    assert len(resultado["descartados"]) == 0


def test_extrair_itens_descarta_area_fora(tmp_path):
    cli = MagicMock()
    cli.extrair_item_stj.side_effect = [
        {"relevante": False, "area": "fora", "processo_id": "HC 1", "tese": "Penal"},
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp B", "tese": "Tese"},
        {"relevante": False, "area": "fora", "processo_id": "REsp C", "tese": "Tributario"},
    ]
    pdf_fake = tmp_path / "x.pdf"
    pdf_fake.write_bytes(b"x")
    r = extrair_itens_de_informativo(pdf_fake, cli, ler_pdf=_ler_pdf_fake, pre_filtro=False)
    assert len(r["aceitos"]) == 1
    assert r["aceitos"][0]["processo_id"] == "REsp B"
    assert len(r["descartados"]) == 2
    assert all(d["motivo"] == "area_fora_escopo" for d in r["descartados"])


def test_extrair_itens_descarta_sem_processo_id(tmp_path):
    cli = MagicMock()
    cli.extrair_item_stj.side_effect = [
        {"relevante": True, "area": "imobiliario", "processo_id": "", "tese": "Tese"},
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp A", "tese": ""},
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp B", "tese": "OK"},
    ]
    pdf_fake = tmp_path / "x.pdf"
    pdf_fake.write_bytes(b"x")
    r = extrair_itens_de_informativo(pdf_fake, cli, ler_pdf=_ler_pdf_fake, pre_filtro=False)
    assert len(r["aceitos"]) == 1
    assert len(r["descartados"]) == 2
    motivos = {d["motivo"] for d in r["descartados"]}
    assert motivos == {"sem_campos_obrigatorios"}


def test_extrair_itens_lida_com_ia_que_explode(tmp_path):
    """IA que levanta excecao em 1 item — descarta esse, segue com os outros."""
    cli = MagicMock()
    cli.extrair_item_stj.side_effect = [
        {"relevante": True, "area": "imobiliario", "processo_id": "REsp A", "tese": "T"},
        RuntimeError("Anthropic indisponivel"),
        {"relevante": True, "area": "sucessorio", "processo_id": "REsp C", "tese": "T"},
    ]
    pdf_fake = tmp_path / "x.pdf"
    pdf_fake.write_bytes(b"x")
    r = extrair_itens_de_informativo(pdf_fake, cli, ler_pdf=_ler_pdf_fake, pre_filtro=False)
    assert len(r["aceitos"]) == 2
    assert len(r["descartados"]) == 1
    assert r["descartados"][0]["motivo"] == "ia_falhou"


def test_extrair_itens_pdf_vazio(tmp_path):
    cli = MagicMock()
    pdf_fake = tmp_path / "vazio.pdf"
    pdf_fake.write_bytes(b"%PDF-1.4")
    r = extrair_itens_de_informativo(pdf_fake, cli, ler_pdf=lambda p: "")
    assert r["aceitos"] == []
    assert r["descartados"] == []
    cli.extrair_item_stj.assert_not_called()


def test_classificar_area_via_ia_delega():
    cli = MagicMock()
    cli.classificar_area.return_value = "imobiliario"
    out = classificar_area_via_ia("ementa sobre usucapiao", cli)
    assert out == "imobiliario"
    cli.classificar_area.assert_called_once()


# ===== HTML reader (novo fluxo Playwright) =====

def test_ler_html_remove_tags_e_preserva_quebras(tmp_path):
    """_ler_html converte HTML para texto preservando linhas por bloco."""
    from src.julgado_radar.parser import _ler_html

    html_path = tmp_path / "inf-0855.html"
    html_path.write_text(
        "<ul>"
        "<li>PROCESSO REsp 999/SP — texto longo</li>"
        "<li>PROCESSO HC 888 — outro texto</li>"
        "</ul>",
        encoding="utf-8",
    )
    texto = _ler_html(html_path)
    assert "<li>" not in texto
    assert "PROCESSO REsp 999/SP" in texto
    assert "PROCESSO HC 888" in texto
    # cada <li> vira uma linha
    linhas = [linha for linha in texto.split("\n") if linha.strip()]
    assert len(linhas) == 2


def test_extrair_itens_de_informativo_le_html_quando_extensao_html(tmp_path):
    """extrair_itens_de_informativo deve aceitar .html, nao so .pdf."""
    cli = MagicMock()
    cli.extrair_item_stj.return_value = {
        "relevante": True, "area": "imobiliario",
        "processo_id": "REsp 1", "tese": "Tese teste",
    }
    html_path = tmp_path / "inf-0855.html"
    html_path.write_text(
        "<ul><li>PROCESSO " + ("X " * 200) + "</li></ul>",
        encoding="utf-8",
    )
    r = extrair_itens_de_informativo(html_path, cli, pre_filtro=False)
    assert len(r["aceitos"]) == 1
    assert r["aceitos"][0]["processo_id"] == "REsp 1"


def test_ler_html_normaliza_quebras_excessivas(tmp_path):
    from src.julgado_radar.parser import _ler_html

    html_path = tmp_path / "x.html"
    html_path.write_text("<p>A</p>\n\n\n\n<p>B</p>", encoding="utf-8")
    texto = _ler_html(html_path)
    # nao deve ter mais de 2 newlines seguidos
    assert "\n\n\n" not in texto


# ===== Pre-filtro por keyword =====

def test_keywords_areas_inclui_termos_essenciais():
    """Keywords derivadas de TERMOS_BUSCA_TJSP + sinonimos."""
    for kw in ("usucapiao", "itbi", "heranca", "inventario", "reurb",
               "condominio", "fiduciaria", "imovel"):
        assert kw in KEYWORDS_AREAS, f"{kw} faltando nas keywords"


def test_bloco_e_candidato_detecta_imobiliario():
    bloco = ("PROCESSO REsp 1.999.485/DF. Em operacoes de financiamento "
             "imobiliario garantidas por alienacao fiduciaria, nao e possivel "
             "a flexibilizacao do percentual da taxa de ocupacao.")
    assert bloco_e_candidato(bloco) is True


def test_bloco_e_candidato_detecta_sucessorio():
    bloco = "PROCESSO REsp 123. Discute-se a partilha de bens no inventario."
    assert bloco_e_candidato(bloco) is True


def test_bloco_e_candidato_ignora_acentos():
    """Bloco com acento deve casar com keyword normalizada."""
    bloco = "Trata-se de USUCAPIÃO extraordinária de imóvel rural."
    assert bloco_e_candidato(bloco) is True


def test_bloco_e_candidato_rejeita_penal():
    bloco = ("PROCESSO HC 123.456/SP. Habeas corpus. Trafico de drogas. "
             "Dosimetria da pena. Regime inicial fechado.")
    assert bloco_e_candidato(bloco) is False


def test_bloco_e_candidato_rejeita_processual_generico():
    bloco = "PROCESSO em segredo de justica. Conflito de competencia."
    assert bloco_e_candidato(bloco) is False


def test_extrair_itens_pre_filtro_economiza_chamadas(tmp_path):
    """Com pre_filtro=True, blocos sem keyword nao chamam o Anthropic."""
    cli = MagicMock()
    cli.extrair_item_stj.return_value = {
        "relevante": True, "area": "imobiliario",
        "processo_id": "REsp 1", "tese": "Tese sobre usucapiao",
    }

    def ler_misto(p):
        # 2 blocos: 1 imobiliario (passa filtro), 1 penal (barrado)
        imob = "PROCESSO REsp 1. " + ("Usucapiao de imovel urbano. " * 20)
        penal = "PROCESSO HC 2. " + ("Trafico de drogas dosimetria pena. " * 20)
        return f"{imob}\n\n{penal}"

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"x")
    r = extrair_itens_de_informativo(pdf, cli, ler_pdf=ler_misto)

    # so o bloco imobiliario chamou o Anthropic
    assert cli.extrair_item_stj.call_count == 1
    assert len(r["aceitos"]) == 1
    # o penal foi descartado por pre_filtro
    motivos = {d["motivo"] for d in r["descartados"]}
    assert "pre_filtro_keyword" in motivos


def test_extrair_itens_pre_filtro_desligavel(tmp_path):
    """Com pre_filtro=False, todos os blocos chamam o Anthropic."""
    cli = MagicMock()
    cli.extrair_item_stj.return_value = {
        "relevante": False, "area": "fora",
        "processo_id": "HC 2", "tese": "Penal",
    }

    def ler_dois(p):
        b1 = "PROCESSO HC 1. " + ("Trafico dosimetria. " * 20)
        b2 = "PROCESSO HC 2. " + ("Roubo qualificado pena. " * 20)
        return f"{b1}\n\n{b2}"

    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"x")
    r = extrair_itens_de_informativo(pdf, cli, ler_pdf=ler_dois, pre_filtro=False)
    # ambos chamaram (sem filtro), ambos descartados por area fora
    assert cli.extrair_item_stj.call_count == 2
