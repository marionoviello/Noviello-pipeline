"""Testes do feeds_tjsp — POST CJSG + parser de HTML + busca por area + sessao."""

from contextlib import contextmanager
from datetime import date

import pytest

from src.julgado_radar.feeds_tjsp import (
    AcordaoTJSP,
    URL_CJSG,
    URL_CJSG_CONSULTA,
    buscar_acordaos,
    extrair_csrf,
    fonte_key,
    montar_payload_cjsg,
    parse_cjsg_html,
)


# ===== FakeSession — simula httpx.Client com cookies internos =====

class FakeSession:
    """Substituto de httpx.Client. Devolve respostas pre-configuradas e
    loga calls pra asserts.

    Configurar:
      - `get_response`: (status, body_bytes) devolvido por sess.get(url)
      - `post_response_fn`: callable (url, data) -> (status, body)
    """

    def __init__(
        self,
        *,
        get_response: tuple[int, bytes] = (200, b""),
        post_response_fn=None,
    ):
        self.get_response = get_response
        self.post_response_fn = post_response_fn or (lambda u, d: (200, b""))
        self.gets: list[str] = []
        self.posts: list[tuple[str, dict]] = []

    def get(self, url):
        self.gets.append(url)
        return self.get_response

    def post(self, url, data):
        self.posts.append((url, dict(data)))
        return self.post_response_fn(url, data)


def _factory(sess: FakeSession):
    @contextmanager
    def factory():
        yield sess
    return factory


# ===== montar_payload =====

def test_montar_payload_inclui_termo_e_datas():
    payload = montar_payload_cjsg(
        "usucapiao", date(2024, 1, 1), date(2024, 1, 31),
    )
    assert payload["dadosConsulta.pesquisaLivre"] == "usucapiao"
    assert payload["dadosConsulta.dataInicial"] == "01/01/2024"
    assert payload["dadosConsulta.dataFinal"] == "31/01/2024"
    assert payload["tipoDecisao"] == "A"


def test_montar_payload_pagina_default_1():
    p = montar_payload_cjsg("ITBI", date(2024, 1, 1), date(2024, 1, 31))
    assert p["pagina"] == "1"


def test_montar_payload_pagina_customizada():
    p = montar_payload_cjsg("ITBI", date(2024, 1, 1), date(2024, 1, 31), pagina=3)
    assert p["pagina"] == "3"


# ===== parse_cjsg_html =====

# Fixture com 2 acordaos no formato HTML observado do cjsg.
HTML_CJSG_FAKE = """
<html><body>
<table>
  <tr>
    <td>Numero do Processo: <strong>1234567-89.2024.8.26.0100</strong></td>
  </tr>
  <tr>
    <td>Classe/Assunto: <span>Apelacao Civel / Usucapiao</span></td>
    <td>Relator(a): <span>Des. Joao da Silva</span></td>
    <td>Orgao Julgador: <span>6a Camara de Direito Privado</span></td>
    <td>Data do Julgamento: <span>15/04/2024</span></td>
    <td>Data de publicacao: <span>20/04/2024</span></td>
    <td>Ementa: <span>USUCAPIAO ORDINARIA. RECIBO DE COMPRA. JUSTO TITULO CONFIGURADO.</span></td>
  </tr>
  <tr>
    <td>Numero: <strong>9876543-21.2023.8.26.0011</strong></td>
  </tr>
  <tr>
    <td>Classe/Assunto: <span>Apelacao / ITBI</span></td>
    <td>Relator: <span>Des. Maria Santos</span></td>
    <td>Orgao Julgador: <span>14a Camara de Direito Publico</span></td>
    <td>Data do Julgamento: <span>10/03/2024</span></td>
    <td>Data de publicacao: <span>15/03/2024</span></td>
    <td>Ementa: <span>ITBI. BASE DE CALCULO. VALOR VENAL DE REFERENCIA INADEQUADO.</span></td>
  </tr>
</table>
</body></html>
"""


def test_parse_cjsg_html_extrai_2_acordaos():
    acordaos = parse_cjsg_html(HTML_CJSG_FAKE)
    assert len(acordaos) == 2
    processos = [a.processo_id for a in acordaos]
    assert "1234567-89.2024.8.26.0100" in processos
    assert "9876543-21.2023.8.26.0011" in processos


def test_parse_cjsg_html_extrai_campos_basicos():
    acordaos = parse_cjsg_html(HTML_CJSG_FAKE)
    por_proc = {a.processo_id: a for a in acordaos}
    a1 = por_proc["1234567-89.2024.8.26.0100"]
    assert "Joao da Silva" in a1.relator
    assert "6a Camara de Direito Privado" in a1.orgao
    assert a1.data_julgamento == "15/04/2024"
    assert a1.data_publicacao == "20/04/2024"
    assert "USUCAPIAO" in a1.ementa.upper()


def test_parse_cjsg_html_vazio():
    assert parse_cjsg_html("") == []
    assert parse_cjsg_html("<html><body>Nada encontrado</body></html>") == []


def test_parse_cjsg_html_sem_match_processo():
    """HTML que nao contem processos no formato CNJ devolve vazio."""
    html = "<html><body>texto qualquer sem processo</body></html>"
    assert parse_cjsg_html(html) == []


def test_parse_cjsg_html_limpa_tags_dos_campos():
    html = """<html><body>
    <p>1111111-11.2024.8.26.0100</p>
    <p>Classe/Assunto: <span><b>Apelacao Civel</b></span></p>
    <p>Relator: <span>Des. Teste<br></span></p>
    </body></html>"""
    acordaos = parse_cjsg_html(html)
    assert len(acordaos) == 1
    a = acordaos[0]
    assert "<b>" not in a.classe
    assert "<br>" not in a.relator


# ===== buscar_acordaos =====

def test_buscar_acordaos_sem_area_valida():
    resultado = buscar_acordaos(
        "area_inexistente", date(2024, 1, 1), date(2024, 1, 31),
        http_post=lambda url, p: (200, b""),
        sleep_fn=lambda s: None,
    )
    assert resultado == []


def test_buscar_acordaos_pipeline_completo():
    chamadas = []

    def fake_post(url, params):
        chamadas.append((url, params))
        return 200, HTML_CJSG_FAKE.encode("utf-8")

    sleeps = []
    resultado = buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        http_post=fake_post, sleep_fn=sleeps.append,
    )
    assert len(resultado) == 2
    # primeiro POST chama URL cjsg
    assert chamadas[0][0] == URL_CJSG
    # rate limit aplicou entre chamadas (mas nao antes da primeira)
    assert all(s >= 3.0 for s in sleeps)
    # se ja tinha 2 acordaos no primeiro POST, top_n=30 nao precisa mais — mas
    # os termos restantes ainda sao chamados ate atingir top_n ou esgotar
    # NOTE: aqui dedup mantem 2 acordaos no total porque HTML_CJSG_FAKE e o mesmo


def test_buscar_acordaos_respeita_top_n():
    """top_n=1 para na primeira chamada que retorna >=1."""
    def fake_post(url, params):
        return 200, HTML_CJSG_FAKE.encode("utf-8")

    resultado = buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        http_post=fake_post, sleep_fn=lambda s: None, top_n=1,
    )
    assert len(resultado) == 1


def test_buscar_acordaos_status_nao_200_continua():
    """503 num termo nao interrompe a busca."""
    chamadas = []

    def fake_post(url, params):
        chamadas.append(params["dadosConsulta.pesquisaLivre"])
        if len(chamadas) == 1:
            return 503, b""
        return 200, HTML_CJSG_FAKE.encode("utf-8")

    resultado = buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        http_post=fake_post, sleep_fn=lambda s: None,
    )
    # apesar do 503 no primeiro termo, demais termos foram tentados
    assert len(chamadas) > 1
    assert len(resultado) >= 1


def test_buscar_acordaos_dedup_entre_termos():
    """Mesmo processo aparecendo em 2 termos da mesma area = 1 linha so."""
    def fake_post(url, params):
        return 200, HTML_CJSG_FAKE.encode("utf-8")

    resultado = buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        http_post=fake_post, sleep_fn=lambda s: None,
    )
    processos = [a.processo_id for a in resultado]
    assert len(processos) == len(set(processos))


def test_fonte_key_formato_canonico():
    assert fonte_key("imobiliario", 2024, 8) == "tjsp-cjsg-2024-08-imobiliario"
    assert fonte_key("urbanistico", 2025, 12) == "tjsp-cjsg-2025-12-urbanistico"


# ===== CSRF extraction =====

def test_extrair_csrf_input_padrao():
    html = '<form><input type="hidden" name="_csrf" value="abc123def" /></form>'
    assert extrair_csrf(html) == "abc123def"


def test_extrair_csrf_input_atributos_invertidos():
    """value antes de name — regex aceita ambas as ordens."""
    html = '<input value="xyz789" name="_csrf" type="hidden">'
    assert extrair_csrf(html) == "xyz789"


def test_extrair_csrf_meta_tag():
    html = '<head><meta name="_csrf" content="meta-token-456"></head>'
    assert extrair_csrf(html) == "meta-token-456"


def test_extrair_csrf_html_sem_token():
    assert extrair_csrf("<html><body>nada</body></html>") == ""


def test_extrair_csrf_html_vazio():
    assert extrair_csrf("") == ""
    assert extrair_csrf(None) == ""  # tolera None


def test_montar_payload_inclui_csrf_quando_dado():
    p = montar_payload_cjsg(
        "ITBI", date(2024, 1, 1), date(2024, 1, 31), csrf="tok-987",
    )
    assert p["_csrf"] == "tok-987"


def test_montar_payload_omite_csrf_quando_vazio():
    p = montar_payload_cjsg("ITBI", date(2024, 1, 1), date(2024, 1, 31))
    assert "_csrf" not in p


# ===== buscar_acordaos via session_factory =====

_HTML_GET_PREVIO_COM_CSRF = (
    '<html><body><form>'
    '<input type="hidden" name="_csrf" value="TOKEN-AAA"/>'
    '<input type="text" name="termo"/>'
    '</form></body></html>'
)


def test_buscar_acordaos_faz_get_previo_antes_do_post():
    sess = FakeSession(
        get_response=(200, _HTML_GET_PREVIO_COM_CSRF.encode("utf-8")),
        post_response_fn=lambda u, d: (200, HTML_CJSG_FAKE.encode("utf-8")),
    )
    buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        session_factory=_factory(sess), sleep_fn=lambda s: None,
    )
    # GET previo foi em consultaCompleta.do (1 vez), depois POSTs
    assert URL_CJSG_CONSULTA in sess.gets
    assert sess.posts, "deveria ter feito POSTs"
    # CSRF do GET previo aparece em cada POST
    for _, payload in sess.posts:
        assert payload.get("_csrf") == "TOKEN-AAA"


def test_buscar_acordaos_sem_csrf_continua_sem_token():
    """Se o GET previo nao tem CSRF, segue postando sem _csrf no payload."""
    sess = FakeSession(
        get_response=(200, b"<html><body>vazio</body></html>"),
        post_response_fn=lambda u, d: (200, HTML_CJSG_FAKE.encode("utf-8")),
    )
    buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        session_factory=_factory(sess), sleep_fn=lambda s: None,
    )
    for _, payload in sess.posts:
        assert "_csrf" not in payload


def test_buscar_acordaos_get_previo_500_segue_tentando_posts():
    """GET previo nao-200 nao deve impedir os POSTs — alguns layouts CSRF
    nao bloqueiam o POST e o GET so server pros cookies."""
    sess = FakeSession(
        get_response=(500, b""),
        post_response_fn=lambda u, d: (200, HTML_CJSG_FAKE.encode("utf-8")),
    )
    resultado = buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        session_factory=_factory(sess), sleep_fn=lambda s: None,
    )
    assert sess.posts  # ainda tentou
    assert resultado  # ainda achou


def test_buscar_acordaos_sessao_reusada_entre_termos():
    """Uma unica sessao serve N POSTs (1 por termo). Garantido pelo
    factory devolver o MESMO objeto em todas as chamadas internas."""
    sess = FakeSession(
        get_response=(200, _HTML_GET_PREVIO_COM_CSRF.encode("utf-8")),
        post_response_fn=lambda u, d: (200, HTML_CJSG_FAKE.encode("utf-8")),
    )
    buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        session_factory=_factory(sess), sleep_fn=lambda s: None,
        top_n=100,  # forca ir ate o fim dos termos
    )
    # imobiliario tem 6 termos em config.TERMOS_BUSCA_TJSP — 1 GET + 6 POSTs no max
    assert len(sess.gets) == 1
    assert 1 <= len(sess.posts) <= 6


def test_buscar_acordaos_post_excecao_termo_descartado():
    """Se sess.post levanta, o termo e pulado mas os outros seguem."""
    posts_feitos: list[int] = []

    def post_fn(url, data):
        posts_feitos.append(1)
        if len(posts_feitos) == 1:
            raise RuntimeError("conexao caiu")
        return 200, HTML_CJSG_FAKE.encode("utf-8")

    sess = FakeSession(
        get_response=(200, _HTML_GET_PREVIO_COM_CSRF.encode("utf-8")),
        post_response_fn=post_fn,
    )
    resultado = buscar_acordaos(
        "imobiliario", date(2024, 1, 1), date(2024, 1, 31),
        session_factory=_factory(sess), sleep_fn=lambda s: None,
    )
    # tentou >1 (excecao no primeiro, segue tentando os demais)
    assert len(posts_feitos) >= 2
    assert resultado
