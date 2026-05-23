"""Testes do SkillsLoader: leitura, cache, frontmatter, combinacao."""

from __future__ import annotations

import pytest

from src.skills_loader import SkillNaoEncontrada, SkillsLoader, _strip_frontmatter

SKILL_COM_FRONTMATTER = """---
name: minha-skill
description: testa skill loader
---

# Skill de Teste

Conteudo da skill que vai pro system prompt.
"""

SKILL_SEM_FRONTMATTER = """# Outra Skill

Texto puro sem metadata.
"""


def _criar_skill(skills_dir, nome, conteudo):
    pasta = skills_dir / nome
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "SKILL.md").write_text(conteudo, encoding="utf-8")


def test_strip_frontmatter_remove_yaml_inicial():
    texto = "---\nname: x\n---\n\n# Heading"
    assert _strip_frontmatter(texto) == "# Heading"


def test_strip_frontmatter_preserva_se_nao_tem():
    texto = "# Heading direto\n\nCorpo"
    assert _strip_frontmatter(texto) == "# Heading direto\n\nCorpo"


def test_loader_le_arquivo_existente(tmp_path):
    _criar_skill(tmp_path, "x", SKILL_COM_FRONTMATTER)
    loader = SkillsLoader(tmp_path)
    conteudo = loader.load("x")
    assert "# Skill de Teste" in conteudo
    assert "name: minha-skill" not in conteudo  # frontmatter foi removido


def test_loader_preserva_frontmatter_se_pedir(tmp_path):
    _criar_skill(tmp_path, "x", SKILL_COM_FRONTMATTER)
    loader = SkillsLoader(tmp_path)
    conteudo = loader.load("x", strip_frontmatter=False)
    assert "name: minha-skill" in conteudo


def test_loader_existe(tmp_path):
    _criar_skill(tmp_path, "x", SKILL_SEM_FRONTMATTER)
    loader = SkillsLoader(tmp_path)
    assert loader.existe("x") is True
    assert loader.existe("y") is False


def test_loader_skill_inexistente_levanta(tmp_path):
    loader = SkillsLoader(tmp_path)
    with pytest.raises(SkillNaoEncontrada):
        loader.load("nao-existe")


def test_loader_cacheia_leitura(tmp_path):
    _criar_skill(tmp_path, "x", "Original")
    loader = SkillsLoader(tmp_path)
    assert loader.load("x") == "Original"
    # modifica o arquivo no disco, mas cache continua
    (tmp_path / "x" / "SKILL.md").write_text("Modificado", encoding="utf-8")
    assert loader.load("x") == "Original"  # cache retorna o antigo


def test_combine_concatena_com_separador(tmp_path):
    _criar_skill(tmp_path, "a", "# AAA\n\ntexto A")
    _criar_skill(tmp_path, "b", "# BBB\n\ntexto B")
    loader = SkillsLoader(tmp_path)
    combinado = loader.combine(["a", "b"])
    assert "# AAA" in combinado
    assert "# BBB" in combinado
    assert "\n\n---\n\n" in combinado  # separador


def test_combine_ignora_skills_faltantes(tmp_path):
    _criar_skill(tmp_path, "existe", "# OK")
    loader = SkillsLoader(tmp_path)
    combinado = loader.combine(["existe", "nao-existe"], ignore_missing=True)
    assert "# OK" in combinado
    assert "nao-existe" not in combinado


def test_combine_levanta_se_skill_falta_sem_ignore(tmp_path):
    loader = SkillsLoader(tmp_path)
    with pytest.raises(SkillNaoEncontrada):
        loader.combine(["nao-existe"])


def test_combine_pula_string_vazia(tmp_path):
    _criar_skill(tmp_path, "x", "AAA")
    loader = SkillsLoader(tmp_path)
    # string vazia na lista nao quebra
    combinado = loader.combine(["x", "", None])  # type: ignore[list-item]
    assert "AAA" in combinado
