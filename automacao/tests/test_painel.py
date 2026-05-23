from src.config import load_config
from src.painel import criar_app, listar_pendencias, registrar_decisao
from src.producer_state import EstadoProd, ProducaoState, ProducaoStore
from src.state import Estado, PecaState, StateStore


def _cfg(tmp_path):
    cfg = load_config()
    cfg.state_dir = tmp_path / "state"
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _copy_pendente(post_id="11745"):
    return ProducaoState(
        post_id=post_id,
        titulo="Inventario Extrajudicial",
        status=EstadoProd.AGUARDANDO_REVISAO_COPY,
        copy_carrossel={
            "slides": [{"titulo": "Gancho", "corpo": "corpo"}],
            "legenda": "Legenda teste",
            "hashtags": ["#inventario"],
        },
        texto_linkedin="Post LinkedIn",
    )


def test_listar_pendencias_copy(tmp_path):
    cfg = _cfg(tmp_path)
    ProducaoStore(cfg.state_dir).save(_copy_pendente())
    pend = listar_pendencias(cfg)
    assert len(pend["copy"]) == 1
    assert pend["copy"][0]["titulo"] == "Inventario Extrajudicial"
    assert pend["copy"][0]["slides"][0]["titulo"] == "Gancho"


def test_peca_com_decisao_some_da_lista(tmp_path):
    cfg = _cfg(tmp_path)
    est = _copy_pendente()
    est.decisao = "aprovar"
    ProducaoStore(cfg.state_dir).save(est)
    assert listar_pendencias(cfg)["copy"] == []


def test_registrar_decisao_copy(tmp_path):
    cfg = _cfg(tmp_path)
    store = ProducaoStore(cfg.state_dir)
    store.save(_copy_pendente())
    registrar_decisao(cfg, "copy", "11745", "ajustar", "trocar o slide 1")
    est = store.load("11745")
    assert est.decisao == "ajustar"
    assert est.ajuste_texto == "trocar o slide 1"


def test_registrar_decisao_final(tmp_path):
    cfg = _cfg(tmp_path)
    store = StateStore(cfg.state_dir)
    store.save(PecaState(peca_id="social-1", status=Estado.AGUARDANDO_APROVACAO))
    registrar_decisao(cfg, "final", "social-1", "aprovar")
    assert store.load("social-1").decisao == "aprovar"


def test_rota_index_responde(tmp_path):
    cfg = _cfg(tmp_path)
    ProducaoStore(cfg.state_dir).save(_copy_pendente())
    cliente = criar_app(cfg).test_client()
    resp = cliente.get("/")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "Painel de Aprova" in corpo
    assert "Inventario Extrajudicial" in corpo


def test_rota_decidir_grava(tmp_path):
    cfg = _cfg(tmp_path)
    store = ProducaoStore(cfg.state_dir)
    store.save(_copy_pendente())
    cliente = criar_app(cfg).test_client()
    resp = cliente.post(
        "/decidir",
        data={"tipo": "copy", "peca_id": "11745", "decisao": "aprovar", "ajuste_texto": ""},
    )
    assert resp.status_code in (302, 303)
    assert store.load("11745").decisao == "aprovar"
