import pytest

from src.producer import _texto_limpo
from src.producer_state import (
    EstadoProd,
    ProducaoState,
    ProducaoStore,
    TransicaoInvalida,
    transition,
)


# ---- producer_state ----

def test_store_crud(tmp_path):
    store = ProducaoStore(tmp_path)
    peca = ProducaoState(post_id="11745", titulo="Inventario")
    assert store.exists("11745") is False
    store.save(peca)
    assert store.exists("11745") is True
    carregada = store.load("11745")
    assert carregada.titulo == "Inventario"
    assert carregada.status == EstadoProd.DETECTADO
    assert carregada.decisao == ""
    store.delete("11745")
    assert store.exists("11745") is False


def test_decisao_persiste(tmp_path):
    store = ProducaoStore(tmp_path)
    peca = ProducaoState(post_id="x", decisao="ajustar", ajuste_texto="trocar slide 1")
    store.save(peca)
    carregada = store.load("x")
    assert carregada.decisao == "ajustar"
    assert carregada.ajuste_texto == "trocar slide 1"


def test_transicao_valida():
    peca = ProducaoState(post_id="x")
    transition(peca, EstadoProd.AGUARDANDO_REVISAO_COPY)
    transition(peca, EstadoProd.COPY_APROVADA)
    transition(peca, EstadoProd.PECA_MONTADA)
    assert peca.status == EstadoProd.PECA_MONTADA
    assert len(peca.historico) == 3


def test_transicao_invalida():
    peca = ProducaoState(post_id="x")
    with pytest.raises(TransicaoInvalida):
        transition(peca, EstadoProd.PECA_MONTADA)


# ---- _texto_limpo ----

def test_texto_limpo_remove_tags():
    html = "<h2>Titulo</h2><p>Um <strong>paragrafo</strong> com &amp; entidade.</p>"
    out = _texto_limpo(html)
    assert "<" not in out and ">" not in out
    assert "Titulo" in out
    assert "paragrafo" in out
    assert "& entidade" in out
