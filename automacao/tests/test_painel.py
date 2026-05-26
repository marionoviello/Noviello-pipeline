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


# ===== Julgado da Semana (Wave 5) =====

from src.julgado_state import EstadoJulgado, JulgadoState, JulgadoStore


def test_listar_pendencias_inclui_julgado(tmp_path):
    cfg = _cfg(tmp_path)
    JulgadoStore(cfg.state_dir).save(JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={
            "tese": "Tese aqui", "processo_id": "REsp X",
            "relator": "Min. Y", "area": "Imobiliario",
            "orgao": "STJ", "carimbo": "Unanimidade",
            "citacao_principal": "Citacao",
            "fundamentos": [{"fonte": "F1", "texto": "T1"}],
        },
        copy_carrossel={
            "slides": [{"titulo": "S1", "corpo": "C1"}],
            "legenda": "L", "hashtags": ["#x"],
        },
        texto_linkedin="LI text",
    ))

    pend = listar_pendencias(cfg)
    assert "julgado" in pend
    assert len(pend["julgado"]) == 1
    item = pend["julgado"][0]
    assert item["id"] == "evt-1"
    assert item["titulo"] == "Tese aqui"
    assert item["processo"] == "REsp X"
    assert item["relator"] == "Min. Y"
    assert item["area"] == "Imobiliario"
    assert item["orgao"] == "STJ"
    assert item["carimbo"] == "Unanimidade"
    assert item["linkedin"] == "LI text"
    assert item["legenda"] == "L"
    assert len(item["slides"]) == 1
    assert item["semana_iso"] == 22


def test_listar_pendencias_julgado_com_decisao_some(tmp_path):
    cfg = _cfg(tmp_path)
    JulgadoStore(cfg.state_dir).save(JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
        dados_julgado={"tese": "T"},
        decisao="aprovar",
    ))
    pend = listar_pendencias(cfg)
    assert pend["julgado"] == []


def test_listar_pendencias_julgado_em_erro_aparece(tmp_path):
    cfg = _cfg(tmp_path)
    JulgadoStore(cfg.state_dir).save(JulgadoState(
        event_id="evt-erro", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.ERRO,
        erro_mensagem="pasta sem-22 nao existe",
    ))
    pend = listar_pendencias(cfg)
    assert any(i["id"] == "evt-erro" for i in pend["julgado"])
    item = next(i for i in pend["julgado"] if i["id"] == "evt-erro")
    assert item["erro_mensagem"] == "pasta sem-22 nao existe"
    assert item["status"] == EstadoJulgado.ERRO


def test_registrar_decisao_julgado(tmp_path):
    cfg = _cfg(tmp_path)
    store = JulgadoStore(cfg.state_dir)
    store.save(JulgadoState(
        event_id="evt-1", semana_iso=22, ano_iso=2026,
        status=EstadoJulgado.AGUARDANDO_REVISAO,
    ))
    registrar_decisao(cfg, "julgado", "evt-1", "aprovar")
    assert store.load("evt-1").decisao == "aprovar"

    registrar_decisao(cfg, "julgado", "evt-1", "ajustar", "trocar relator")
    est = store.load("evt-1")
    assert est.decisao == "ajustar"
    assert est.ajuste_texto == "trocar relator"
