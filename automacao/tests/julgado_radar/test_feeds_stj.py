"""Testes do feeds_stj — discover URL + download com cache + rate limit.

Sem rede: HTTP getter e mockado, sleep e capturado.
"""

import pytest

from src.julgado_radar.feeds_stj import (
    FeedSTJError,
    InformativoRef,
    baixar_informativo,
    descobrir_informativos,
    parse_listagem,
)


HTML_LISTAGEM_FAKE = """
<html>
<body>
  <h2>Informativos de Jurisprudencia</h2>
  <ul>
    <li><a href="/informativos/inf-789.pdf">Informativo 789</a></li>
    <li><a href="/informativos/inf-825.pdf">Informativo 825</a></li>
    <li><a href="/informativos/inf-855.pdf">Informativo n. 855</a></li>
    <li><a href="https://www.stj.jus.br/x/inf-700.pdf">Informativo nº 700</a></li>
    <li><a href="/algum-outro-doc.pdf">Documento Avulso</a></li>
  </ul>
</body></html>
"""


def test_parse_listagem_extrai_informativos():
    refs = parse_listagem(HTML_LISTAGEM_FAKE)
    numeros = sorted(r.numero for r in refs)
    assert numeros == [700, 789, 825, 855]


def test_parse_listagem_resolve_url_relativa():
    refs = parse_listagem(HTML_LISTAGEM_FAKE, base_url="https://www.stj.jus.br/pagina")
    by_num = {r.numero: r for r in refs}
    assert by_num[789].url_pdf.startswith("https://www.stj.jus.br/informativos/")
    assert by_num[700].url_pdf == "https://www.stj.jus.br/x/inf-700.pdf"


def test_parse_listagem_ignora_links_nao_pdf():
    html = '<a href="/algo.html">Informativo 999</a>'
    assert parse_listagem(html) == []


def test_parse_listagem_dedupica_numero_repetido():
    html = (
        '<a href="/a/inf-1.pdf">Informativo 1</a>'
        '<a href="/b/inf-1.pdf">Informativo 1</a>'
    )
    refs = parse_listagem(html)
    assert len(refs) == 1
    assert refs[0].numero == 1


def test_descobrir_informativos_filtra_por_ano():
    """Numero 825 esta na faixa de 2025; 700 e 2021."""
    def fake_get(url):
        return 200, HTML_LISTAGEM_FAKE.encode("utf-8")

    refs = descobrir_informativos([2025], http_get=fake_get)
    numeros = sorted(r.numero for r in refs)
    assert numeros == [825]


def test_descobrir_informativos_multi_anos():
    def fake_get(url):
        return 200, HTML_LISTAGEM_FAKE.encode("utf-8")

    refs = descobrir_informativos([2021, 2025], http_get=fake_get)
    numeros = sorted(r.numero for r in refs)
    assert 700 in numeros  # 2021
    assert 825 in numeros  # 2025


def test_descobrir_informativos_listagem_indisponivel():
    def fake_get(url):
        return 503, b""
    assert descobrir_informativos([2025], http_get=fake_get) == []


def test_informativo_ref_fonte_key():
    ref = InformativoRef(numero=789, ano=2024, url_pdf="x")
    assert ref.fonte_key == "stj-informativo-789"


def test_informativo_ref_filename_zero_padded():
    ref = InformativoRef(numero=1, ano=2021, url_pdf="x")
    assert ref.filename == "inf-0001.pdf"


def test_baixar_informativo_cria_arquivo(tmp_path):
    sleeps = []
    ref = InformativoRef(numero=789, ano=2024, url_pdf="https://x/inf.pdf")

    def fake_get(url):
        return 200, b"%PDF-1.4 conteudo fake"

    destino = baixar_informativo(
        ref, tmp_path / "cache",
        http_get=fake_get, sleep_fn=sleeps.append,
    )
    assert destino.exists()
    assert destino.read_bytes() == b"%PDF-1.4 conteudo fake"
    # rate limit foi respeitado (1 sleep ~1seg)
    assert len(sleeps) == 1
    assert sleeps[0] >= 1.0


def test_baixar_informativo_usa_cache_quando_ja_existe(tmp_path):
    """Se ja existe no cache, nao chama HTTP nem sleep."""
    sleeps = []
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    ref = InformativoRef(numero=789, ano=2024, url_pdf="https://x/inf.pdf")
    arquivo_existente = cache_dir / ref.filename
    arquivo_existente.write_bytes(b"cache antigo")

    chamadas = []

    def fake_get(url):
        chamadas.append(url)
        return 200, b"deveria nao ser chamado"

    destino = baixar_informativo(
        ref, cache_dir, http_get=fake_get, sleep_fn=sleeps.append,
    )
    assert destino == arquivo_existente
    assert destino.read_bytes() == b"cache antigo"  # nao sobrescreveu
    assert chamadas == []  # cache hit, sem HTTP
    assert sleeps == []  # sem rate limit


def test_baixar_informativo_falha_404(tmp_path):
    ref = InformativoRef(numero=789, ano=2024, url_pdf="https://x/inf.pdf")

    def fake_get(url):
        return 404, b""

    with pytest.raises(FeedSTJError, match="status=404"):
        baixar_informativo(ref, tmp_path / "cache", http_get=fake_get, sleep_fn=lambda s: None)


def test_baixar_informativo_falha_corpo_vazio(tmp_path):
    ref = InformativoRef(numero=789, ano=2024, url_pdf="https://x/inf.pdf")

    def fake_get(url):
        return 200, b""

    with pytest.raises(FeedSTJError):
        baixar_informativo(ref, tmp_path / "cache", http_get=fake_get, sleep_fn=lambda s: None)


def test_baixar_informativo_respeita_rate_limit_customizado(tmp_path):
    ref = InformativoRef(numero=789, ano=2024, url_pdf="x")
    sleeps = []

    def fake_get(url):
        return 200, b"%PDF dados"

    baixar_informativo(
        ref, tmp_path,
        http_get=fake_get, sleep_fn=sleeps.append, rate_limit_seg=2.5,
    )
    assert sleeps == [2.5]
