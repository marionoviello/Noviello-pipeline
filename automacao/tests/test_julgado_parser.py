"""Testes do julgado_parser — localizacao de PDFs e parsing via pypdf + Anthropic.

A IA Anthropic e mockada — testes nao fazem chamada de rede.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.julgado_parser import (
    JulgadoParserError,
    _extrair_texto_pdf,
    localizar_pdf_da_semana,
    parse_julgado,
)

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "julgado_dummy.pdf"


# ===== localizar_pdf_da_semana =====

def test_localizar_pdf_pasta_inexistente_falha(tmp_path):
    with pytest.raises(JulgadoParserError, match="nao existe"):
        localizar_pdf_da_semana(tmp_path / "julgados", 22)


def test_localizar_pdf_pasta_vazia_falha(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    with pytest.raises(JulgadoParserError, match="nenhum PDF"):
        localizar_pdf_da_semana(tmp_path / "julgados", 22)


def test_localizar_pdf_multiplos_pdfs_falha(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    (pasta / "a.pdf").write_bytes(b"%PDF-1.4")
    (pasta / "b.pdf").write_bytes(b"%PDF-1.4")
    with pytest.raises(JulgadoParserError, match="mais de um PDF"):
        localizar_pdf_da_semana(tmp_path / "julgados", 22)


def test_localizar_pdf_unico_devolve(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    pdf = pasta / "acordao.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    resultado = localizar_pdf_da_semana(tmp_path / "julgados", 22)
    assert resultado == pdf


def test_localizar_pdf_zerofill_semana(tmp_path):
    """sem-01 (zerofill) deve funcionar com semana=1."""
    pasta = tmp_path / "julgados" / "sem-01"
    pasta.mkdir(parents=True)
    pdf = pasta / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert localizar_pdf_da_semana(tmp_path / "julgados", 1) == pdf


def test_localizar_pdf_ignora_arquivos_nao_pdf(tmp_path):
    pasta = tmp_path / "julgados" / "sem-22"
    pasta.mkdir(parents=True)
    (pasta / "README.txt").write_text("ignore", encoding="utf-8")
    pdf = pasta / "acordao.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert localizar_pdf_da_semana(tmp_path / "julgados", 22) == pdf


# ===== _extrair_texto_pdf =====

def test_extrair_texto_pdf_smoke():
    """PDF de fixture em branco devolve string."""
    assert FIXTURE_PDF.exists()
    texto = _extrair_texto_pdf(FIXTURE_PDF)
    assert isinstance(texto, str)


def test_extrair_texto_pdf_inexistente_falha(tmp_path):
    with pytest.raises(JulgadoParserError, match="nao existe"):
        _extrair_texto_pdf(tmp_path / "nao-existe.pdf")


def test_extrair_texto_pdf_corrompido_falha(tmp_path):
    pdf = tmp_path / "corrompido.pdf"
    pdf.write_text("isto nao eh um PDF", encoding="utf-8")
    with pytest.raises(JulgadoParserError):
        _extrair_texto_pdf(pdf)


# ===== parse_julgado (full pipeline) =====

def _anthropic_mock(payload):
    """Mock do AnthropicClient com extrair_dados_julgado."""
    cli = MagicMock()
    cli.extrair_dados_julgado.return_value = payload
    return cli


def _dados_completos():
    return {
        "area": "Direito Imobiliario",
        "orgao": "STJ",
        "orgao_completo": "Terceira Turma do STJ",
        "turma": "3a Turma",
        "processo_id": "REsp 2.215.421/SE",
        "data_julgamento": "10/03/2026",
        "relator": "Min. Nancy Andrighi",
        "relator_curto": "Min. Nancy Andrighi",
        "tese": "Recibo basta como justo titulo",
        "citacao_principal": "O justo titulo deve ser interpretado de forma ampla",
        "carimbo": "Unanimidade",
        "fundamentos": [{"fonte": "Art. 1.242 CC", "texto": "Usucapiao ordinaria"}],
    }


def test_parse_julgado_devolve_dict_completo(monkeypatch):
    """PDF valido + IA OK => dict com todos os campos."""
    monkeypatch.setattr(
        "src.julgado_parser._extrair_texto_pdf",
        lambda p: "TEXTO DO ACORDAO COMPLETO AQUI",
    )
    cli = _anthropic_mock(_dados_completos())
    dados = parse_julgado(FIXTURE_PDF, cli)
    assert dados["processo_id"] == "REsp 2.215.421/SE"
    assert dados["relator"] == "Min. Nancy Andrighi"
    assert dados["orgao"] == "STJ"
    assert dados["carimbo"] == "Unanimidade"
    assert len(dados["fundamentos"]) == 1


def test_parse_julgado_pdf_inexistente_falha(tmp_path):
    cli = _anthropic_mock({})
    with pytest.raises(JulgadoParserError):
        parse_julgado(tmp_path / "nao-existe.pdf", cli)


def test_parse_julgado_texto_vazio_falha(monkeypatch):
    """PDF que devolve texto vazio gera erro claro (sem chamar IA)."""
    monkeypatch.setattr("src.julgado_parser._extrair_texto_pdf", lambda p: "")
    cli = _anthropic_mock({})
    with pytest.raises(JulgadoParserError, match="texto"):
        parse_julgado(FIXTURE_PDF, cli)
    # IA nao deve ser chamada se texto vazio
    cli.extrair_dados_julgado.assert_not_called()


def test_parse_julgado_campo_obrigatorio_vazio_falha(monkeypatch):
    """Se IA devolve campo obrigatorio vazio, erro claro."""
    monkeypatch.setattr(
        "src.julgado_parser._extrair_texto_pdf", lambda p: "texto",
    )
    dados = _dados_completos()
    dados["relator"] = ""  # IA falhou em identificar
    cli = _anthropic_mock(dados)
    with pytest.raises(JulgadoParserError, match="relator"):
        parse_julgado(FIXTURE_PDF, cli)


def test_parse_julgado_fundamentos_vazios_falha(monkeypatch):
    monkeypatch.setattr(
        "src.julgado_parser._extrair_texto_pdf", lambda p: "texto",
    )
    dados = _dados_completos()
    dados["fundamentos"] = []
    cli = _anthropic_mock(dados)
    with pytest.raises(JulgadoParserError, match="fundamentos"):
        parse_julgado(FIXTURE_PDF, cli)


def test_parse_julgado_aceita_campos_opcionais_vazios(monkeypatch):
    """Campos opcionais (orgao_completo, turma, data_julgamento, relator_curto)
    podem vir vazios — nao bloqueiam."""
    monkeypatch.setattr("src.julgado_parser._extrair_texto_pdf", lambda p: "texto")
    dados = _dados_completos()
    dados["orgao_completo"] = ""
    dados["turma"] = ""
    dados["relator_curto"] = ""
    cli = _anthropic_mock(dados)
    resultado = parse_julgado(FIXTURE_PDF, cli)
    assert resultado["orgao_completo"] == ""
    assert resultado["relator"] == "Min. Nancy Andrighi"  # obrigatorio, preservado
