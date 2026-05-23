"""Testes do area_resolver: mapping de categorias WP para skills da area."""

from __future__ import annotations

from src.area_resolver import MAPPING_SLUG_PARA_SKILLS, resolver_skills_de_area


def test_lista_vazia_devolve_nenhuma_skill():
    assert resolver_skills_de_area([]) == []


def test_slug_nao_mapeado_e_ignorado():
    assert resolver_skills_de_area(["xpto-inexistente"]) == []


def test_slug_imobiliario_carrega_skill_master():
    assert resolver_skills_de_area(["imob"]) == ["noviello-imobiliario-master"]


def test_holding_carrega_skill_tributaria_e_sucessoria():
    skills = resolver_skills_de_area(["holding-patrimonial"])
    assert "noviello-imobiliario-holding-tributario" in skills
    assert "noviello-orcamentista-sucessorio" in skills


def test_categorias_multiplas_unem_skills_sem_duplicar():
    # Artigo Holding marcado com Holding + Sucessorio
    skills = resolver_skills_de_area(["holding-patrimonial", "planejamento-sucessorio"])
    # noviello-orcamentista-sucessorio aparece nos dois mappings, mas sem duplicata
    assert skills.count("noviello-orcamentista-sucessorio") == 1
    assert "noviello-imobiliario-holding-tributario" in skills


def test_slug_case_insensitive():
    skills_lower = resolver_skills_de_area(["imob"])
    skills_upper = resolver_skills_de_area(["IMOB"])
    assert skills_lower == skills_upper


def test_fila_social_e_sem_categoria_nao_acrescentam_nada():
    assert resolver_skills_de_area(["fila-social", "sem-categoria"]) == []


def test_senior_planejamento_carrega_duas_skills():
    skills = resolver_skills_de_area(["direito-do-senior-planejamento"])
    assert "noviello-direito-senior" in skills
    assert "noviello-orcamentista-sucessorio" in skills


def test_mapping_tem_entradas_para_categorias_principais():
    """Sanity: o mapping cobre as categorias mais usadas do blog (>10 posts)."""
    principais = ["imob", "idoso", "prev", "saude", "urban",
                  "holding-patrimonial", "planejamento-sucessorio"]
    for slug in principais:
        assert slug in MAPPING_SLUG_PARA_SKILLS, f"slug '{slug}' nao mapeado"
        assert MAPPING_SLUG_PARA_SKILLS[slug], f"slug '{slug}' mapeado para vazio"


def test_string_vazia_nao_quebra():
    assert resolver_skills_de_area(["", "imob"]) == ["noviello-imobiliario-master"]
