import pytest

from src.state import (
    Estado,
    PecaState,
    StateStore,
    TransicaoInvalida,
    transition,
)


def test_ciclo_crud(tmp_path):
    store = StateStore(tmp_path)
    peca = PecaState(peca_id="2026-S20-teste", manifest_path="/x/MANIFEST.json")

    assert store.exists("2026-S20-teste") is False
    store.save(peca)
    assert store.exists("2026-S20-teste") is True

    carregada = store.load("2026-S20-teste")
    assert carregada.peca_id == "2026-S20-teste"
    assert carregada.status == Estado.DETECTADA

    store.delete("2026-S20-teste")
    assert store.exists("2026-S20-teste") is False


def test_list_all(tmp_path):
    store = StateStore(tmp_path)
    store.save(PecaState(peca_id="a"))
    store.save(PecaState(peca_id="b"))
    ids = {p.peca_id for p in store.list_all()}
    assert ids == {"a", "b"}


def test_transicao_valida_registra_historico():
    peca = PecaState(peca_id="x")
    transition(peca, Estado.AGUARDANDO_APROVACAO)
    assert peca.status == Estado.AGUARDANDO_APROVACAO
    assert len(peca.historico) == 1
    assert peca.historico[0]["de"] == Estado.DETECTADA
    assert peca.historico[0]["para"] == Estado.AGUARDANDO_APROVACAO


def test_transicao_invalida_levanta():
    peca = PecaState(peca_id="x")
    with pytest.raises(TransicaoInvalida):
        transition(peca, Estado.PUBLICADA)


def test_fluxo_completo_de_aprovacao():
    peca = PecaState(peca_id="x")
    transition(peca, Estado.AGUARDANDO_APROVACAO)
    transition(peca, Estado.APROVADA)
    transition(peca, Estado.PUBLICANDO)
    transition(peca, Estado.PUBLICADA)
    assert peca.status == Estado.PUBLICADA
    assert len(peca.historico) == 4


def test_from_dict_ignora_campos_extras():
    peca = PecaState.from_dict(
        {"peca_id": "x", "status": Estado.APROVADA, "campo_lixo": 123}
    )
    assert peca.peca_id == "x"
    assert peca.status == Estado.APROVADA
