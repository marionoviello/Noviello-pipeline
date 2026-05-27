"""Testes das constantes do Radar."""

from src.julgado_radar import config


def test_areas_alvo_tem_tres_areas():
    assert set(config.AREAS_ALVO) == {"urbanistico", "imobiliario", "sucessorio"}


def test_area_fora_nao_e_alvo():
    assert config.AREA_FORA == "fora"
    assert config.AREA_FORA not in config.AREAS_ALVO


def test_fontes_tem_stj_e_tjsp():
    assert "stj" in config.FONTES
    assert "tjsp" in config.FONTES


def test_rate_limits_conservadores():
    """TJ-SP precisa ser mais lento que STJ (mais sensivel)."""
    assert config.RATE_LIMIT_TJSP_SEG >= config.RATE_LIMIT_STJ_SEG


def test_termos_busca_tjsp_cobrem_3_areas():
    assert set(config.TERMOS_BUSCA_TJSP.keys()) == set(config.AREAS_ALVO)
    for area, termos in config.TERMOS_BUSCA_TJSP.items():
        assert len(termos) >= 3, f"{area} precisa de >=3 termos"


def test_top_por_mes_area_limita_volume():
    """Limite por mes/area evita explosao de volume no TJ-SP."""
    assert 10 <= config.TJSP_TOP_POR_MES_AREA <= 100
