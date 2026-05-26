import pytest

from src.julgado_state import (
    EstadoJulgado,
    JulgadoState,
    JulgadoStore,
    TransicaoInvalida,
    transition,
    _safe_key,
)


def test_safe_key_sanitiza_chars_invalidos():
    assert _safe_key("evt_abc@123") == "evt_abc_123"
    assert _safe_key("a/b\\c:d") == "a_b_c_d"
    assert _safe_key("ok-123_xyz") == "ok-123_xyz"


def test_store_crud(tmp_path):
    store = JulgadoStore(tmp_path)
    estado = JulgadoState(event_id="evt-xyz", semana_iso=22, ano_iso=2026)
    assert store.exists("evt-xyz") is False
    store.save(estado)
    assert store.exists("evt-xyz") is True
    carregado = store.load("evt-xyz")
    assert carregado.semana_iso == 22
    assert carregado.status == EstadoJulgado.DETECTADO
    store.delete("evt-xyz")
    assert store.exists("evt-xyz") is False


def test_event_id_com_chars_especiais_sanitiza_no_path(tmp_path):
    store = JulgadoStore(tmp_path)
    estado = JulgadoState(event_id="evt@abc/123", semana_iso=1, ano_iso=2026)
    store.save(estado)
    arquivos = list((tmp_path / "julgados").glob("*.json"))
    assert len(arquivos) == 1
    assert "@" not in arquivos[0].name
    assert "/" not in arquivos[0].name
    carregado = store.load("evt@abc/123")
    assert carregado.event_id == "evt@abc/123"


def test_transicao_valida_registra_historico():
    est = JulgadoState(event_id="x", semana_iso=1, ano_iso=2026)
    transition(est, EstadoJulgado.AGUARDANDO_REVISAO)
    transition(est, EstadoJulgado.APROVADO)
    transition(est, EstadoJulgado.PECA_MONTADA)
    assert est.status == EstadoJulgado.PECA_MONTADA
    assert len(est.historico) == 3


def test_transicao_invalida_levanta():
    est = JulgadoState(event_id="x", semana_iso=1, ano_iso=2026)
    with pytest.raises(TransicaoInvalida):
        transition(est, EstadoJulgado.PECA_MONTADA)


def test_erro_permite_recovery():
    est = JulgadoState(
        event_id="x", semana_iso=1, ano_iso=2026, status=EstadoJulgado.ERRO,
    )
    transition(est, EstadoJulgado.AGUARDANDO_REVISAO)
    assert est.status == EstadoJulgado.AGUARDANDO_REVISAO


def test_decisao_persiste(tmp_path):
    store = JulgadoStore(tmp_path)
    est = JulgadoState(
        event_id="x", semana_iso=1, ano_iso=2026,
        decisao="ajustar", ajuste_texto="trocar relator",
    )
    store.save(est)
    carregado = store.load("x")
    assert carregado.decisao == "ajustar"
    assert carregado.ajuste_texto == "trocar relator"


def test_list_all_ignora_arquivos_invalidos(tmp_path):
    store = JulgadoStore(tmp_path)
    store.save(JulgadoState(event_id="a", semana_iso=1, ano_iso=2026))
    (tmp_path / "julgados" / "lixo.json").write_text("{nao eh json", encoding="utf-8")
    pecas = store.list_all()
    assert len(pecas) == 1
    assert pecas[0].event_id == "a"


def test_from_dict_ignora_campos_extras():
    dados = {"event_id": "x", "semana_iso": 1, "ano_iso": 2026, "campo_obsoleto": "x"}
    est = JulgadoState.from_dict(dados)
    assert est.event_id == "x"
