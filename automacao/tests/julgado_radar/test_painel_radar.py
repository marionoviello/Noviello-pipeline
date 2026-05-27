"""Testes das rotas /radar e /radar/usar no painel Flask."""

from src.config import load_config
from src.julgado_radar import db, indexer
from src.julgado_radar.models import Julgado
from src.painel import criar_app


def _cfg(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.ENV_PATH", tmp_path / "nao-existe.env")
    monkeypatch.setenv("NOVIELLO_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("NOVIELLO_PRODUCAO_DIR", str(tmp_path / "producao"))
    cfg = load_config()
    return cfg


def _seed(cfg):
    conn = db.abrir(cfg.state_dir)
    indexer.indexar_batch(conn, [
        Julgado(tribunal="STJ", processo_id="REsp 1", area="imobiliario",
                tese="Usucapiao ordinaria com recibo de compra",
                ementa="ementa sobre usucapiao", relator="Min. A",
                classe="Recurso Especial", data_julgamento="2024-03-10"),
        Julgado(tribunal="TJ-SP", processo_id="1111-2024", area="sucessorio",
                tese="Holding familiar e licita",
                relator="Des. B", classe="Apelacao", data_julgamento="2024-08-15"),
    ])
    conn.close()


def test_radar_rota_responde(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _seed(cfg)
    app = criar_app(cfg)
    client = app.test_client()
    resp = client.get("/radar")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Radar de Julgados" in body
    assert "Usucapiao" in body


def test_radar_busca_filtra_resultados(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _seed(cfg)
    app = criar_app(cfg)
    client = app.test_client()
    resp = client.get("/radar?q=usucapiao")
    body = resp.get_data(as_text=True)
    assert "Usucapiao" in body
    assert "Holding familiar" not in body


def test_radar_filtro_area(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _seed(cfg)
    app = criar_app(cfg)
    client = app.test_client()
    resp = client.get("/radar?area=sucessorio")
    body = resp.get_data(as_text=True)
    assert "Holding" in body
    assert "Usucapiao" not in body


def test_radar_sem_resultados_mostra_mensagem(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    app = criar_app(cfg)
    client = app.test_client()
    resp = client.get("/radar")
    body = resp.get_data(as_text=True)
    assert "Nenhum julgado encontrado" in body


def test_radar_usar_cria_pasta_e_redireciona(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _seed(cfg)
    app = criar_app(cfg)
    client = app.test_client()
    resp = client.post("/radar/usar", data={"julgado_id": "1"})
    assert resp.status_code in (302, 303)
    # pasta sem-NN/ criada em cfg.julgado_dir
    pastas = list((cfg.julgado_dir).glob("sem-*"))
    assert len(pastas) == 1
    # PDF + JSON dentro
    arquivos = list(pastas[0].iterdir())
    assert any(a.suffix == ".pdf" for a in arquivos)
    assert any(a.suffix == ".json" for a in arquivos)


def test_radar_usar_julgado_inexistente_falha_500(tmp_path, monkeypatch):
    """julgado_id desconhecido: RadarViewError -> 500."""
    cfg = _cfg(tmp_path, monkeypatch)
    app = criar_app(cfg)
    client = app.test_client()
    resp = client.post("/radar/usar", data={"julgado_id": "9999"})
    # Flask sem error handler customizado retorna 500
    assert resp.status_code == 500
