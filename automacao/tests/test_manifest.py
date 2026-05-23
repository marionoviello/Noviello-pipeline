import pytest

from src.manifest import ValidacaoError, carregar_manifest, validate_manifest
from tests.helpers import criar_peca_dir


def test_manifest_valido(tmp_path):
    mpath = criar_peca_dir(tmp_path, canais=("instagram", "wordpress"))
    peca = validate_manifest(mpath)
    assert peca.peca_id == "2026-S20-teste"
    assert peca.pilar == "Direito Imobiliario"
    assert set(peca.canais_no_manifest()) == {"instagram", "wordpress"}


def test_status_errado_reprova(tmp_path):
    mpath = criar_peca_dir(tmp_path, status="rascunho")
    with pytest.raises(ValidacaoError, match="status"):
        validate_manifest(mpath)


def test_oab_reprovado_reprova(tmp_path):
    mpath = criar_peca_dir(tmp_path, oab="reprovado")
    with pytest.raises(ValidacaoError, match="oab_205"):
        validate_manifest(mpath)


def test_marca_nao_conforme_reprova(tmp_path):
    mpath = criar_peca_dir(tmp_path, marca="desvio_registrado")
    with pytest.raises(ValidacaoError, match="marca"):
        validate_manifest(mpath)


def test_asset_ausente_reprova(tmp_path):
    mpath = criar_peca_dir(tmp_path, quebrar_path=True)
    with pytest.raises(ValidacaoError, match="assets ausentes"):
        validate_manifest(mpath)


def test_carregar_manifest_sem_peca_id_levanta(tmp_path):
    mpath = tmp_path / "MANIFEST.json"
    mpath.write_text('{"tipo": "carrossel"}', encoding="utf-8")
    with pytest.raises(ValidacaoError, match="peca_id"):
        carregar_manifest(mpath)
