"""Testes dos metodos novos do AnthropicClient para o pipeline Julgado.

A chamada ao SDK Anthropic e mockada — testes nao fazem rede.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.anthropic_client import (
    AnthropicClient,
    CAROUSEL_SCHEMA_JULGADO,
    JULGADO_SCHEMA,
)


def _fake_response(payload):
    msg = MagicMock()
    bloco = MagicMock()
    bloco.type = "text"
    bloco.text = json.dumps(payload) if isinstance(payload, dict) else payload
    msg.content = [bloco]
    return msg


def _fake_stream_cm(payload):
    stream = MagicMock()
    stream.get_final_message.return_value = _fake_response(payload)
    cm = MagicMock()
    cm.__enter__ = lambda self: stream
    cm.__exit__ = lambda self, *a: False
    return cm


def _make_client(tmp_path):
    (tmp_path / "brief-marca.txt").write_text("brief de teste", encoding="utf-8")
    return AnthropicClient({"api_key": "sk-fake"}, tmp_path)


# ===== Schemas =====

def test_julgado_schema_tem_campos_obrigatorios():
    obrig = set(JULGADO_SCHEMA["required"])
    assert obrig >= {
        "area", "orgao", "processo_id", "relator",
        "tese", "citacao_principal", "carimbo", "fundamentos",
    }


def test_carousel_schema_julgado_inclui_campos_meta_no_slide():
    """Slides aceitam 4 campos opcionais do Batch (a)."""
    slide_props = CAROUSEL_SCHEMA_JULGADO["properties"]["slides"]["items"]["properties"]
    assert "area" in slide_props
    assert "selo_tribunal" in slide_props
    assert "processo_id" in slide_props
    assert "carimbo" in slide_props
    # obrigatorios continuam sendo so titulo+corpo
    obrig = set(CAROUSEL_SCHEMA_JULGADO["properties"]["slides"]["items"]["required"])
    assert obrig == {"titulo", "corpo"}


# ===== extrair_dados_julgado =====

def test_extrair_dados_julgado_devolve_dict(tmp_path):
    cliente = _make_client(tmp_path)
    payload = {
        "area": "Direito Imobiliario", "orgao": "STJ",
        "orgao_completo": "Terceira Turma do STJ", "turma": "3a Turma",
        "processo_id": "REsp 2.215.421/SE", "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi", "relator_curto": "Min. Nancy",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve...",
        "carimbo": "Unanimidade",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "..."}],
    }
    with patch.object(
        cliente._client.messages, "stream", return_value=_fake_stream_cm(payload),
    ):
        resultado = cliente.extrair_dados_julgado("TEXTO DO ACORDAO AQUI")
    assert resultado["processo_id"] == "REsp 2.215.421/SE"
    assert resultado["carimbo"] == "Unanimidade"


def test_extrair_dados_julgado_passa_texto_no_user_content(tmp_path):
    cliente = _make_client(tmp_path)
    payload = {
        "area": "x", "orgao": "STJ", "processo_id": "p", "relator": "r",
        "tese": "t", "citacao_principal": "c", "carimbo": "Unanimidade",
        "fundamentos": [],
    }
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm(payload)

    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.extrair_dados_julgado("MEU TEXTO BRUTO")

    # o texto do PDF aparece em algum lugar dos blocos user
    user_content = capturado["messages"][0]["content"]
    texto_completo = json.dumps(user_content, ensure_ascii=False)
    assert "MEU TEXTO BRUTO" in texto_completo


# ===== gerar_carrossel_julgado =====

def test_gerar_carrossel_julgado_devolve_slides_com_metadados(tmp_path):
    cliente = _make_client(tmp_path)
    dados = {
        "area": "Direito Imobiliario", "orgao": "STJ",
        "processo_id": "REsp 2.215.421/SE", "carimbo": "Unanimidade",
        "tese": "T", "citacao_principal": "C", "relator": "R",
        "fundamentos": [],
    }
    payload = {
        "slides": [
            {
                "titulo": "Capa", "corpo": "STJ revoluciona usucapiao",
                "area": "Direito Imobiliario", "selo_tribunal": "STJ",
                "processo_id": "REsp 2.215.421/SE", "carimbo": "Unanimidade",
            },
            {"titulo": "Slide 2", "corpo": "..."},
        ],
        "legenda": "legenda",
        "hashtags": ["#usucapiao"],
    }
    with patch.object(
        cliente._client.messages, "stream", return_value=_fake_stream_cm(payload),
    ):
        resultado = cliente.gerar_carrossel_julgado(dados)
    assert resultado["slides"][0]["area"] == "Direito Imobiliario"
    assert resultado["slides"][0]["carimbo"] == "Unanimidade"
    assert "_ai_tells" in resultado


def test_gerar_carrossel_julgado_com_ajuste(tmp_path):
    cliente = _make_client(tmp_path)
    payload = {"slides": [{"titulo": "x", "corpo": "y"}], "legenda": "", "hashtags": []}
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm(payload)

    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.gerar_carrossel_julgado(
            {"tese": "x", "fundamentos": []}, ajuste="trocar slide 1",
        )
    texto_completo = json.dumps(capturado["messages"], ensure_ascii=False)
    assert "trocar slide 1" in texto_completo


# ===== gerar_linkedin_julgado =====

def test_gerar_linkedin_julgado_devolve_texto(tmp_path):
    cliente = _make_client(tmp_path)
    dados = {
        "tese": "x", "processo_id": "y", "relator": "z",
        "citacao_principal": "w", "fundamentos": [],
    }
    with patch.object(
        cliente._client.messages, "stream",
        return_value=_fake_stream_cm("Post LinkedIn de teste."),
    ):
        resultado = cliente.gerar_linkedin_julgado(dados)
    assert resultado == "Post LinkedIn de teste."


def test_gerar_linkedin_julgado_com_url_blog(tmp_path):
    cliente = _make_client(tmp_path)
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm("post.")

    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.gerar_linkedin_julgado(
            {"tese": "t", "fundamentos": []},
            url_blog="https://noviello.adv.br/julgado-x",
        )
    texto = json.dumps(capturado["messages"], ensure_ascii=False)
    assert "https://noviello.adv.br/julgado-x" in texto


def test_gerar_linkedin_julgado_sem_url_blog_nao_inclui_link(tmp_path):
    cliente = _make_client(tmp_path)
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm("post.")

    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.gerar_linkedin_julgado({"tese": "t", "fundamentos": []})
    texto = json.dumps(capturado["messages"], ensure_ascii=False)
    assert "Termine com o link" not in texto


# ===== Radar de Julgados — extrair_item_stj + classificar_area =====

def test_extrair_item_stj_devolve_dict_com_schema(tmp_path):
    cliente = _make_client(tmp_path)
    payload = {
        "relevante": True, "area": "imobiliario",
        "processo_id": "REsp 2.215.421/SE",
        "relator": "Min. Nancy Andrighi", "orgao": "3a Turma",
        "data_julgamento": "10/03/2026", "classe": "Recurso Especial",
        "tese": "Recibo basta como justo titulo",
        "ementa": "EMENTA: usucapiao ordinaria...",
        "citacao_voto": "O justo titulo deve...",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "..."}],
    }
    schema = {"type": "object", "properties": {}, "required": []}
    with patch.object(
        cliente._client.messages, "stream", return_value=_fake_stream_cm(payload),
    ):
        out = cliente.extrair_item_stj("TEXTO DO BLOCO AQUI", schema)
    assert out["processo_id"] == "REsp 2.215.421/SE"
    assert out["area"] == "imobiliario"


def test_extrair_item_stj_passa_schema_no_output_config(tmp_path):
    cliente = _make_client(tmp_path)
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm({"relevante": False, "area": "fora", "processo_id": "x", "tese": "t"})

    schema = {"type": "object", "properties": {"area": {"type": "string"}}, "required": ["area"]}
    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.extrair_item_stj("bloco", schema)

    output_cfg = capturado["output_config"]
    assert output_cfg["format"]["schema"] == schema
    assert output_cfg["format"]["type"] == "json_schema"


def test_classificar_area_devolve_string(tmp_path):
    cliente = _make_client(tmp_path)
    payload = {"area": "imobiliario"}
    with patch.object(
        cliente._client.messages, "stream", return_value=_fake_stream_cm(payload),
    ):
        area = cliente.classificar_area(
            "ementa sobre usucapiao",
            ["urbanistico", "imobiliario", "sucessorio", "fora"],
        )
    assert area == "imobiliario"


def test_classificar_area_passa_areas_validas_no_schema(tmp_path):
    cliente = _make_client(tmp_path)
    capturado = {}

    def fake_stream(**kwargs):
        capturado.update(kwargs)
        return _fake_stream_cm({"area": "fora"})

    areas = ["urbanistico", "imobiliario", "sucessorio", "fora"]
    with patch.object(cliente._client.messages, "stream", side_effect=fake_stream):
        cliente.classificar_area("ementa", areas)

    schema = capturado["output_config"]["format"]["schema"]
    assert schema["properties"]["area"]["enum"] == areas
