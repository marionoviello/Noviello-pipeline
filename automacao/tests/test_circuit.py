import datetime as _dt

from src.circuit import canal_pausado, registrar_falha, registrar_sucesso


def test_canal_novo_nao_esta_pausado(tmp_path):
    assert canal_pausado(tmp_path, "instagram") is False


def test_tres_falhas_pausam_o_canal(tmp_path):
    registrar_falha(tmp_path, "instagram")
    registrar_falha(tmp_path, "instagram")
    assert canal_pausado(tmp_path, "instagram") is False  # 2 falhas, ainda nao
    registrar_falha(tmp_path, "instagram")
    assert canal_pausado(tmp_path, "instagram") is True  # 3 falhas


def test_sucesso_zera_o_contador(tmp_path):
    registrar_falha(tmp_path, "instagram")
    registrar_falha(tmp_path, "instagram")
    registrar_sucesso(tmp_path, "instagram")
    registrar_falha(tmp_path, "instagram")
    assert canal_pausado(tmp_path, "instagram") is False


def test_pausa_expira(tmp_path):
    for _ in range(3):
        registrar_falha(tmp_path, "instagram")
    futuro = _dt.datetime.now().astimezone() + _dt.timedelta(hours=2)
    assert canal_pausado(tmp_path, "instagram", agora=futuro) is False
