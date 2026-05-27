"""Testes das dataclasses Julgado/Descartado."""

import json

from src.julgado_radar.models import Descartado, Julgado


def test_julgado_to_row_serializa_fundamentos():
    j = Julgado(
        tribunal="STJ", processo_id="X", area="imobiliario", tese="T",
        fundamentos=[{"fonte": "F", "texto": "T"}],
        indexado_em="2026-05-26",
    )
    row = j.to_row()
    assert "fundamentos" not in row
    assert "fundamentos_json" in row
    assert json.loads(row["fundamentos_json"]) == [{"fonte": "F", "texto": "T"}]


def test_julgado_from_row_desserializa_fundamentos():
    row = {
        "tribunal": "STJ", "processo_id": "X", "area": "imobiliario",
        "tese": "T", "indexado_em": "2026-05-26",
        "fundamentos_json": '[{"fonte":"F","texto":"T"}]',
    }
    j = Julgado.from_row(row)
    assert j.fundamentos == [{"fonte": "F", "texto": "T"}]


def test_julgado_from_row_ignora_fundamentos_json_invalido():
    row = {
        "tribunal": "STJ", "processo_id": "X", "area": "imobiliario",
        "tese": "T", "indexado_em": "2026-05-26",
        "fundamentos_json": "{nao eh json",
    }
    j = Julgado.from_row(row)
    assert j.fundamentos == []


def test_julgado_from_row_ignora_chaves_desconhecidas():
    """Campo extra no SQL nao explode (forward-compat)."""
    row = {
        "tribunal": "STJ", "processo_id": "X", "area": "imobiliario",
        "tese": "T", "indexado_em": "2026-05-26",
        "campo_novo_que_nao_existe": "blah",
    }
    j = Julgado.from_row(row)
    assert j.tribunal == "STJ"


def test_descartado_to_row_serializa_payload():
    d = Descartado(
        tribunal="STJ", processo_id="X", motivo="area_fora_escopo",
        payload={"area": "penal"}, descartado_em="2026-05-26",
    )
    row = d.to_row()
    assert "payload" not in row
    assert json.loads(row["payload_json"]) == {"area": "penal"}
