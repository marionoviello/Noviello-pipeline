"""Testes do gerador de imagens (helpers de prompt — sem chamada API real)."""

from src.image_gen import (
    _ambiente_por_tema,
    _sujeito_por_categoria,
    ESTILO_HERO_ARTIGO,
)


def test_sujeito_por_categoria_sucessorio():
    s = _sujeito_por_categoria(["Sucessório"], "Inventário")
    assert "sucessao familiar" in s.lower() or "alianca" in s.lower()


def test_sujeito_por_categoria_imobiliario():
    s = _sujeito_por_categoria(["Direito Imobiliário"], "Locação")
    assert "imovel" in s.lower() or "fachada" in s.lower()


def test_sujeito_por_categoria_acentuado_e_lowercase():
    """Deve casar mesmo com case/acento variando."""
    s1 = _sujeito_por_categoria(["SUCESSÓRIO"], "")
    s2 = _sujeito_por_categoria(["sucessorio"], "")
    s3 = _sujeito_por_categoria(["Planejamento Sucessório"], "")
    assert s1 == s2 == s3


def test_sujeito_fallback_no_titulo():
    """Sem categoria valida, deriva do titulo."""
    s = _sujeito_por_categoria(["Geral"], "Doação com Reserva de Usufruto: Sucessório")
    # casa "sucessório" no titulo
    assert "sucessao" in s.lower() or "familia" in s.lower()


def test_sujeito_fallback_generico():
    """Sem categoria nem titulo relevante, retorna generico."""
    s = _sujeito_por_categoria([], "Tema genérico qualquer")
    assert "escritorio" in s.lower() or "advocacia" in s.lower()


def test_ambiente_familia():
    a = _ambiente_por_tema("Como preservar o patrimônio dos filhos", "Doação")
    assert "transicao geracional" in a.lower() or "domestico" in a.lower()


def test_ambiente_imovel():
    a = _ambiente_por_tema("Compra de imóvel sem escritura", "Regularização")
    assert "arquitetonicos" in a.lower()


def test_estilo_hero_proibe_texto():
    assert "SEM TEXTO" in ESTILO_HERO_ARTIGO
    assert "16:9" in ESTILO_HERO_ARTIGO
