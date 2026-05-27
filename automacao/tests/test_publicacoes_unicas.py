"""Testes do registry de publicações únicas (anti-duplicata)."""

from __future__ import annotations

from src.publicacoes_unicas import (
    RegistroPublicacao,
    RegistroStore,
    chave_manual,
    chave_processo,
    chave_wp_post,
    normalizar_processo_id,
)


# ---- normalização ---------------------------------------------------------

def test_normaliza_resp_padrao_stj():
    assert normalizar_processo_id("REsp 2.215.421/SE") == "resp-2215421-se"


def test_normaliza_resp_com_acentos_e_classes():
    assert normalizar_processo_id("AgRg no REsp 1.234.567/RJ") == "agrg-no-resp-1234567-rj"


def test_normaliza_recurso_extraordinario():
    assert normalizar_processo_id("RE 1.000.000/SP") == "re-1000000-sp"


def test_normaliza_apelacao_tjsp():
    """Numeração CNJ do TJ-SP."""
    s = normalizar_processo_id("Apel. 1234567-89.2020.8.26.0100")
    assert s == "apel-1234567-89-2020-8-26-0100"


def test_normaliza_vazio_retorna_vazio():
    assert normalizar_processo_id("") == ""
    assert normalizar_processo_id("   ") == ""


def test_normaliza_é_idempotente():
    s = normalizar_processo_id("REsp 2.215.421/SE")
    assert normalizar_processo_id(s) == s


# ---- chaves canônicas -----------------------------------------------------

def test_chave_processo_prefixo():
    assert chave_processo("REsp 2.215.421/SE") == "processo:resp-2215421-se"


def test_chave_processo_vazia_se_id_vazio():
    assert chave_processo("") == ""


def test_chave_wp_post_aceita_int_ou_str():
    assert chave_wp_post(11748) == "wp:11748"
    assert chave_wp_post("11748") == "wp:11748"


def test_chave_manual_normaliza_slug():
    assert chave_manual("Holding Familiar Teste 01") == "manual:holding-familiar-teste-01"


# ---- store ----------------------------------------------------------------

def test_store_existe_false_inicialmente(tmp_path):
    store = RegistroStore(tmp_path)
    assert store.existe("processo:resp-2215421-se") is False


def test_store_registrar_e_obter(tmp_path):
    store = RegistroStore(tmp_path)
    reg = store.registrar(
        "processo:resp-2215421-se",
        tipo="processo",
        peca_id="julgado-resp-2-215-421-se",
        titulo="Recibo basta como justo título",
        canais_publicados=["instagram", "linkedin"],
        urls={"linkedin": "https://lnk.in/abc"},
    )
    assert reg.chave == "processo:resp-2215421-se"
    assert reg.tipo == "processo"
    assert reg.tentativas == 1
    obtido = store.obter("processo:resp-2215421-se")
    assert obtido is not None
    assert obtido.peca_id == "julgado-resp-2-215-421-se"
    assert "instagram" in obtido.canais_publicados


def test_store_existe_true_apos_registrar(tmp_path):
    store = RegistroStore(tmp_path)
    store.registrar("processo:resp-2215421-se", tipo="processo")
    assert store.existe("processo:resp-2215421-se") is True


def test_store_registrar_idempotente_preserva_primeira_publicacao(tmp_path):
    store = RegistroStore(tmp_path)
    r1 = store.registrar("processo:abc", tipo="processo", canais_publicados=["linkedin"])
    primeira = r1.primeira_publicacao_iso
    r2 = store.registrar("processo:abc", tipo="processo", canais_publicados=["instagram"])
    # primeira publicacao NAO muda (mesmo se ocorrer no mesmo segundo)
    assert r2.primeira_publicacao_iso == primeira
    # ultima tentativa pode ser >= primeira (precisão de segundo no agora_iso)
    assert r2.ultima_tentativa_iso >= primeira
    # tentativas incrementou
    assert r2.tentativas == 2
    # canais foram mergidos (linkedin do r1 + instagram do r2)
    assert "linkedin" in r2.canais_publicados
    assert "instagram" in r2.canais_publicados


def test_store_registrar_idempotente_urls_merge(tmp_path):
    store = RegistroStore(tmp_path)
    store.registrar("processo:abc", tipo="processo", urls={"linkedin": "url-1"})
    r2 = store.registrar("processo:abc", tipo="processo", urls={"instagram": "url-2"})
    assert r2.urls == {"linkedin": "url-1", "instagram": "url-2"}


def test_store_chave_vazia_levanta(tmp_path):
    store = RegistroStore(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        store.registrar("", tipo="processo")


def test_store_remover(tmp_path):
    store = RegistroStore(tmp_path)
    store.registrar("processo:abc", tipo="processo")
    assert store.remover("processo:abc") is True
    assert store.existe("processo:abc") is False
    # remoção de inexistente devolve False
    assert store.remover("processo:nao-existe") is False


def test_store_listar_ordenado_mais_recente_primeiro(tmp_path):
    """Ordering: agora_iso tem precisão de segundo; usamos sleep > 1s
    pra garantir distinção, dado que o sort em isoformat é estável."""
    import time
    store = RegistroStore(tmp_path)
    store.registrar("processo:antigo", tipo="processo")
    time.sleep(1.1)
    store.registrar("processo:novo", tipo="processo")
    lista = store.listar()
    assert len(lista) == 2
    assert lista[0].chave == "processo:novo"  # mais recente primeiro
    assert lista[1].chave == "processo:antigo"


def test_store_persiste_entre_instancias(tmp_path):
    """Confirma que JSON realmente vai pro disco e sobrevive ao recarregamento."""
    s1 = RegistroStore(tmp_path)
    s1.registrar("processo:abc", tipo="processo")
    s2 = RegistroStore(tmp_path)
    assert s2.existe("processo:abc") is True
