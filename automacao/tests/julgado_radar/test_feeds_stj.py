"""Testes do feeds_stj — discover + download via Playwright mock.

Sem rede: `playwright_factory` injetavel devolve uma FakePage que implementa
o subset usado (goto/wait_for_*/evaluate/eval_on_selector/select_option).
"""

from contextlib import contextmanager

import pytest

from src.julgado_radar.feeds_stj import (
    ANOS_PDF_ANUAL,
    ANOS_SUPORTADOS,
    FeedSTJError,
    InformativoRef,
    PdfAnualRef,
    URL_PDF_ANUAL_TEMPLATE,
    URL_PORTAL_INFORMATIVOS,
    baixar_informativo,
    baixar_pdf_anual,
    descobrir_informativos,
    obter_pdfs_anuais,
)


# ===== FakePage — simula Playwright Page para os testes =====

class FakePage:
    """Substituto minimo de playwright.sync_api.Page para os testes.

    Aceita um dict `selects` mapeando select_id -> lista de
    {value, text} e um dict `blocos` mapeando option_value -> HTML.
    Apos `select_option`, `eval_on_selector("#idInformativoBlocoLista", ...)`
    devolve o HTML do bloco correspondente.
    """

    def __init__(
        self,
        *,
        selects: dict | None = None,
        blocos: dict | None = None,
        goto_raises: Exception | None = None,
    ):
        self.selects = selects or {}
        self.blocos = blocos or {}
        self.goto_raises = goto_raises
        self.calls: list[tuple] = []  # log de chamadas pra asserts
        self._selecionado: str = ""

    def goto(self, url, **kwargs):
        self.calls.append(("goto", url, kwargs))
        if self.goto_raises:
            raise self.goto_raises

    def wait_for_load_state(self, state, **kwargs):
        self.calls.append(("wait_for_load_state", state))

    def wait_for_timeout(self, ms):
        self.calls.append(("wait_for_timeout", ms))

    def evaluate(self, script, *args):
        # 2 usos distintos:
        # 1) _listar_opcoes_do_select chama com selector "#idInfoEdicoes...{ano}"
        # 2) baixar_informativo chama com [selectId, optValue] pra setar value
        if args and isinstance(args[0], str) and args[0].startswith("#"):
            select_id = args[0][1:]
            return self.selects.get(select_id, [])
        if args and isinstance(args[0], list) and len(args[0]) == 2:
            select_id, opt_value = args[0]
            self.calls.append(("select_via_js", select_id, opt_value))
            self._selecionado = opt_value
            return None
        return []

    def eval_on_selector(self, selector, script):
        # _extrair_bloco passa por varios selectors; devolve o HTML do bloco
        # do option selecionado, independente do selector (simplificacao).
        if self._selecionado:
            return self.blocos.get(self._selecionado, "")
        return ""

    def select_option(self, selector, *, value):
        # Mantido pra compatibilidade com testes legados, mas o codigo
        # de producao agora usa evaluate (vide FakePage.evaluate).
        self.calls.append(("select_option", selector, value))
        self._selecionado = value


def _factory(page: FakePage):
    """Constroi um playwright_factory que cede `page` como context manager."""
    @contextmanager
    def factory():
        yield page
    return factory


# ===== InformativoRef =====

def test_informativo_ref_fonte_key_formato():
    ref = InformativoRef(numero=837, ano=2024)
    assert ref.fonte_key == "stj-informativo-837"


def test_informativo_ref_filename_zero_padded_html():
    ref = InformativoRef(numero=1, ano=2021)
    assert ref.filename == "inf-0001.html"


def test_informativo_ref_aceita_campos_playwright():
    ref = InformativoRef(
        numero=837,
        ano=2024,
        select_id="idInformativoEdicoesCombo2024",
        option_value="0837",
        titulo="Informativo 837 (15/04/2024)",
    )
    assert ref.select_id == "idInformativoEdicoesCombo2024"
    assert ref.option_value == "0837"


# ===== descobrir_informativos =====

def test_descobrir_informativos_le_combo_do_ano():
    page = FakePage(selects={
        "idInformativoEdicoesCombo2024": [
            {"value": "0837", "text": "Informativo 837 (15/04/2024)"},
            {"value": "0836", "text": "Informativo 836 (01/04/2024)"},
        ],
    })
    refs = descobrir_informativos([2024], playwright_factory=_factory(page))
    assert len(refs) == 2
    numeros = sorted(r.numero for r in refs)
    assert numeros == [836, 837]
    assert refs[0].ano == 2024
    assert refs[0].select_id == "idInformativoEdicoesCombo2024"


def test_descobrir_informativos_ordena_mais_recente_primeiro():
    page = FakePage(selects={
        "idInformativoEdicoesCombo2023": [
            {"value": "0800", "text": "Inf 800"},
        ],
        "idInformativoEdicoesCombo2025": [
            {"value": "0850", "text": "Inf 850"},
        ],
    })
    refs = descobrir_informativos([2023, 2025], playwright_factory=_factory(page))
    assert refs[0].ano == 2025
    assert refs[0].numero == 850
    assert refs[1].ano == 2023


def test_descobrir_informativos_filtra_anos_nao_suportados():
    """Anos fora de ANOS_SUPORTADOS (ex: 2019, 2030) devem ser ignorados."""
    page = FakePage(selects={})
    refs = descobrir_informativos([2019, 2030], playwright_factory=_factory(page))
    assert refs == []


def test_descobrir_informativos_ignora_valores_nao_numericos():
    """Combo de Especiais pode ter values nao-numericos — sao filtrados."""
    page = FakePage(selects={
        "idInformativoEdicoesCombo2024": [
            {"value": "0837", "text": "Inf 837"},
            {"value": "ESPECIAL-X", "text": "Especial X"},
            {"value": "", "text": "vazio"},
        ],
    })
    refs = descobrir_informativos([2024], playwright_factory=_factory(page))
    numeros = [r.numero for r in refs]
    assert numeros == [837]


def test_descobrir_informativos_combo_vazio_devolve_lista_vazia():
    page = FakePage(selects={"idInformativoEdicoesCombo2024": []})
    refs = descobrir_informativos([2024], playwright_factory=_factory(page))
    assert refs == []


def test_descobrir_informativos_abre_portal_uma_vez():
    """Reusa a mesma pagina pra todos os anos — 1 goto, N evaluates."""
    page = FakePage(selects={
        "idInformativoEdicoesCombo2024": [{"value": "0837", "text": "x"}],
        "idInformativoEdicoesCombo2025": [{"value": "0850", "text": "y"}],
    })
    descobrir_informativos([2024, 2025], playwright_factory=_factory(page))
    gotos = [c for c in page.calls if c[0] == "goto"]
    assert len(gotos) == 1
    assert gotos[0][1] == URL_PORTAL_INFORMATIVOS


# ===== baixar_informativo =====

def test_baixar_informativo_grava_html_no_cache(tmp_path):
    ref = InformativoRef(
        numero=837, ano=2024,
        select_id="idInformativoEdicoesCombo2024", option_value="0837",
    )
    page = FakePage(blocos={"0837": "<ul><li>Item A</li><li>Item B</li></ul>"})
    sleeps: list[float] = []

    destino = baixar_informativo(
        ref, tmp_path / "cache",
        playwright_factory=_factory(page),
        sleep_fn=sleeps.append,
    )
    assert destino.exists()
    assert destino.read_text(encoding="utf-8") == "<ul><li>Item A</li><li>Item B</li></ul>"
    # rate limit aplicou
    assert len(sleeps) == 1
    assert sleeps[0] >= 1.0
    # select via JS foi chamado com o value correto
    select_calls = [c for c in page.calls if c[0] == "select_via_js"]
    assert select_calls and select_calls[0][2] == "0837"


def test_baixar_informativo_cache_hit_nao_chama_playwright(tmp_path):
    """Se ja existe HTML no cache, nao abre Chromium nem dorme."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    ref = InformativoRef(
        numero=837, ano=2024,
        select_id="idInformativoEdicoesCombo2024", option_value="0837",
    )
    pre_existente = cache_dir / ref.filename
    pre_existente.write_text("<cache antigo />", encoding="utf-8")

    # Factory deve nao ser chamada — se for, FakePage levanta nada mas
    # podemos detectar via len(calls)
    page = FakePage(blocos={"0837": "<novo />"})
    sleeps: list[float] = []

    destino = baixar_informativo(
        ref, cache_dir,
        playwright_factory=_factory(page),
        sleep_fn=sleeps.append,
    )
    assert destino == pre_existente
    assert destino.read_text(encoding="utf-8") == "<cache antigo />"
    assert page.calls == []  # nada de Playwright
    assert sleeps == []


def test_baixar_informativo_sem_select_id_falha(tmp_path):
    """Ref sem select_id (legacy ou criado a mao) — erro claro."""
    ref = InformativoRef(numero=837, ano=2024)  # sem select_id
    page = FakePage()
    with pytest.raises(FeedSTJError, match="sem select_id"):
        baixar_informativo(
            ref, tmp_path / "cache",
            playwright_factory=_factory(page),
            sleep_fn=lambda s: None,
        )


def test_baixar_informativo_bloco_vazio_falha(tmp_path):
    """Se nenhum dos selectors retorna HTML — FeedSTJError."""
    ref = InformativoRef(
        numero=837, ano=2024,
        select_id="idInformativoEdicoesCombo2024", option_value="0837",
    )
    page = FakePage(blocos={})  # nenhum HTML
    with pytest.raises(FeedSTJError, match="bloco vazio"):
        baixar_informativo(
            ref, tmp_path / "cache",
            playwright_factory=_factory(page),
            sleep_fn=lambda s: None,
        )


def test_baixar_informativo_rate_limit_customizado(tmp_path):
    ref = InformativoRef(
        numero=837, ano=2024,
        select_id="idInformativoEdicoesCombo2024", option_value="0837",
    )
    page = FakePage(blocos={"0837": "<x/>"})
    sleeps: list[float] = []
    baixar_informativo(
        ref, tmp_path / "cache",
        playwright_factory=_factory(page),
        sleep_fn=sleeps.append,
        rate_limit_seg=2.5,
    )
    assert sleeps == [2.5]


def test_baixar_informativo_select_via_js_explode_propaga_feed_error(tmp_path):
    ref = InformativoRef(
        numero=999, ano=2024,
        select_id="idInformativoEdicoesCombo2024", option_value="0999",
    )

    class PageQuebrada(FakePage):
        def evaluate(self, script, *args):
            # se for o evaluate de set value, levanta
            if args and isinstance(args[0], list):
                raise RuntimeError("select nao encontrado")
            return []  # listar opcoes (nao usado neste teste)

    page = PageQuebrada(blocos={})
    with pytest.raises(FeedSTJError, match="select via evaluate falhou"):
        baixar_informativo(
            ref, tmp_path / "cache",
            playwright_factory=_factory(page),
            sleep_fn=lambda s: None,
        )


# ===== Anos suportados — guard de regressao =====

def test_anos_suportados_inclui_2021_a_2026():
    assert 2021 in ANOS_SUPORTADOS
    assert 2026 in ANOS_SUPORTADOS
    # quando STJ publicar 2027, atualizar essa constante


def test_anos_pdf_anual_cobre_historico():
    """PDF anual existe desde 2017 (mais amplo que o combo Playwright 2021+).
    Sao conceitos independentes: ANOS_SUPORTADOS = combo dinamico do portal;
    ANOS_PDF_ANUAL = PDFs agregados disponiveis via httpx."""
    assert 2017 in ANOS_PDF_ANUAL
    assert 2023 in ANOS_PDF_ANUAL
    # 2024+ nao disponivel ainda (STJ demora ~1 ano)
    assert 2024 not in ANOS_PDF_ANUAL


# ===== PdfAnualRef =====

def test_pdf_anual_ref_fonte_key():
    ref = PdfAnualRef(ano=2023, url="x")
    assert ref.fonte_key == "stj-pdf-anual-2023"


def test_pdf_anual_ref_filename():
    ref = PdfAnualRef(ano=2023, url="x")
    assert ref.filename == "informativo_anual_2023.pdf"


# ===== obter_pdfs_anuais =====

def test_obter_pdfs_anuais_so_devolve_anos_com_200():
    """Anos cujo HEAD da 404 sao filtrados."""
    def fake_head(url):
        if "2023" in url or "2022" in url:
            return 200, {}
        return 404, {}

    refs = obter_pdfs_anuais([2021, 2022, 2023, 2024], http_head=fake_head)
    anos = sorted(r.ano for r in refs)
    assert anos == [2022, 2023]


def test_obter_pdfs_anuais_url_canonica():
    def fake_head(url):
        return 200, {}

    refs = obter_pdfs_anuais([2023], http_head=fake_head)
    assert len(refs) == 1
    esperado = URL_PDF_ANUAL_TEMPLATE.format(ano=2023)
    assert refs[0].url == esperado


def test_obter_pdfs_anuais_excecao_no_head_filtra_ano():
    def fake_head(url):
        raise RuntimeError("DNS error")

    refs = obter_pdfs_anuais([2023], http_head=fake_head)
    assert refs == []


def test_obter_pdfs_anuais_deduplica_anos_repetidos():
    chamadas = []

    def fake_head(url):
        chamadas.append(url)
        return 200, {}

    obter_pdfs_anuais([2023, 2023, 2023], http_head=fake_head)
    assert len(chamadas) == 1  # uma chamada por ano unico


# ===== baixar_pdf_anual =====

PDF_FAKE = b"%PDF-1.4\n" + b"x" * 200_000  # >100KB, comeca com %PDF


def test_baixar_pdf_anual_grava_no_cache(tmp_path):
    ref = PdfAnualRef(ano=2023, url="https://x/2023.pdf")
    sleeps = []

    def fake_get(url):
        return 200, PDF_FAKE

    destino = baixar_pdf_anual(
        ref, tmp_path / "cache",
        http_get=fake_get, sleep_fn=sleeps.append,
    )
    assert destino.exists()
    assert destino.name == "informativo_anual_2023.pdf"
    assert destino.read_bytes().startswith(b"%PDF")
    assert sleeps == [1.0]  # rate_limit default


def test_baixar_pdf_anual_cache_hit(tmp_path):
    """Se ja existe no cache, nao chama HTTP nem dorme."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    ref = PdfAnualRef(ano=2023, url="x")
    pre = cache_dir / ref.filename
    pre.write_bytes(b"cache antigo PDF" * 1000)

    chamadas = []

    def fake_get(url):
        chamadas.append(url)
        return 200, b""

    destino = baixar_pdf_anual(
        ref, cache_dir, http_get=fake_get, sleep_fn=lambda s: None,
    )
    assert destino == pre
    assert chamadas == []


def test_baixar_pdf_anual_falha_404(tmp_path):
    ref = PdfAnualRef(ano=2024, url="x")

    def fake_get(url):
        return 404, b""

    with pytest.raises(FeedSTJError, match="indisponivel"):
        baixar_pdf_anual(
            ref, tmp_path / "cache",
            http_get=fake_get, sleep_fn=lambda s: None,
        )


def test_baixar_pdf_anual_falha_tamanho_minimo(tmp_path):
    """Body <100KB e rejeitado (PDFs anuais STJ sao 17-38MB)."""
    ref = PdfAnualRef(ano=2023, url="x")

    def fake_get(url):
        return 200, b"%PDF-tiny"

    with pytest.raises(FeedSTJError, match="indisponivel"):
        baixar_pdf_anual(
            ref, tmp_path / "cache",
            http_get=fake_get, sleep_fn=lambda s: None,
        )


def test_baixar_pdf_anual_corrompido_nao_pdf(tmp_path):
    """Body grande mas nao comeca com %PDF e rejeitado."""
    ref = PdfAnualRef(ano=2023, url="x")
    body = b"<html>404 not pretty</html>" + b"x" * 200_000

    def fake_get(url):
        return 200, body

    with pytest.raises(FeedSTJError, match="corrompido"):
        baixar_pdf_anual(
            ref, tmp_path / "cache",
            http_get=fake_get, sleep_fn=lambda s: None,
        )


def test_baixar_pdf_anual_excecao_de_rede_vira_feed_error(tmp_path):
    ref = PdfAnualRef(ano=2023, url="x")

    def fake_get(url):
        raise ConnectionError("timeout")

    with pytest.raises(FeedSTJError, match="falha de rede"):
        baixar_pdf_anual(
            ref, tmp_path / "cache",
            http_get=fake_get, sleep_fn=lambda s: None,
        )


def test_baixar_pdf_anual_rate_limit_customizado(tmp_path):
    ref = PdfAnualRef(ano=2023, url="x")
    sleeps = []

    def fake_get(url):
        return 200, PDF_FAKE

    baixar_pdf_anual(
        ref, tmp_path / "cache",
        http_get=fake_get, sleep_fn=sleeps.append, rate_limit_seg=2.5,
    )
    assert sleeps == [2.5]
