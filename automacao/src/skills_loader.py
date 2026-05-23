"""Carrega o conteudo das skills `noviello-*` do stash local.

As skills vivem em `<stash>/skills/<nome-da-skill>/SKILL.md`. Cada arquivo
comeca com um frontmatter YAML (`---name: ... description: ... ---`) seguido
do conteudo markdown propriamente dito.

Para o producer, o que importa e o markdown apos o frontmatter — o frontmatter
e metadata do Claude Code (irrelevante para o LLM da Anthropic).
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


class SkillNaoEncontrada(Exception):
    """Levantada quando uma skill referenciada nao existe no stash."""


def _strip_frontmatter(texto: str) -> str:
    """Remove o bloco YAML inicial `---...---` se presente."""
    return _FRONTMATTER_RE.sub("", texto, count=1).strip()


class SkillsLoader:
    """Carrega skills `.md` do stash com cache em memoria.

    Uso:
        loader = SkillsLoader(Path('/caminho/para/stash/skills'))
        conteudo = loader.load('noviello-marketing-creator')
        combinado = loader.combine([
            'noviello-marketing-creator',
            'noviello-voz-padrao',
        ])
    """

    def __init__(self, skills_dir: Path):
        self._dir = Path(skills_dir)
        self._cache: dict[str, str] = {}

    def existe(self, nome: str) -> bool:
        return (self._dir / nome / "SKILL.md").exists()

    def load(self, nome: str, *, strip_frontmatter: bool = True) -> str:
        """Le o conteudo da skill (com cache). Levanta SkillNaoEncontrada."""
        chave = (nome, strip_frontmatter)
        if chave in self._cache:
            return self._cache[chave]

        path = self._dir / nome / "SKILL.md"
        if not path.exists():
            raise SkillNaoEncontrada(
                f"skill '{nome}' nao encontrada em {path}. "
                f"Verifique se o stash de skills esta no caminho esperado."
            )
        conteudo = path.read_text(encoding="utf-8")
        if strip_frontmatter:
            conteudo = _strip_frontmatter(conteudo)
        self._cache[chave] = conteudo
        return conteudo

    def combine(
        self,
        nomes: list[str],
        *,
        separator: str = "\n\n---\n\n",
        strip_frontmatter: bool = True,
        ignore_missing: bool = False,
    ) -> str:
        """Combina varias skills num unico texto, separadas por `separator`.

        `ignore_missing=True` pula skills que nao existem (util para fallback).
        """
        textos: list[str] = []
        for nome in nomes:
            if not nome:
                continue
            try:
                textos.append(self.load(nome, strip_frontmatter=strip_frontmatter))
            except SkillNaoEncontrada:
                if not ignore_missing:
                    raise
        return separator.join(textos)
