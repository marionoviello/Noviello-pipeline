"""Resolve quais skills `noviello-*` carregar baseado nas categorias WP.

A IA recebe um conjunto fixo de skills (marketing-creator, voz-padrao, oab-205)
+ um conjunto da AREA do artigo, escolhido dinamicamente pelas categorias do
post no WordPress.

O mapping abaixo foi montado a partir das categorias reais do `noviello.adv.br`
(WP REST `categories?orderby=count`). Slugs sao mais estaveis que IDs.

**Como expandir:** se aparecer categoria nova ou faltar skill pra alguma area,
adicione abaixo. O default e `[]` (nenhuma skill extra — IA usa so a base).
"""

from __future__ import annotations

# Mapping slug-da-categoria-WP -> lista de skills `noviello-*` a carregar.
# Multiplas categorias num artigo produzem UNIAO das skills (sem duplicatas).
MAPPING_SLUG_PARA_SKILLS: dict[str, list[str]] = {
    # Imobiliario / Urbanistico
    "imob": ["noviello-imobiliario-master"],
    "urban": ["noviello-imobiliario-urbanistico-paulista"],
    "direito-condominial": ["noviello-imobiliario-condominial"],
    # Sucessorio / Holding / Tributario
    "planejamento-sucessorio": ["noviello-orcamentista-sucessorio"],
    "sucessoes-e-planejamento-sucessorio": ["noviello-orcamentista-sucessorio"],
    "holding-patrimonial": [
        "noviello-imobiliario-holding-tributario",
        "noviello-orcamentista-sucessorio",
    ],
    "direito-tributario": ["noviello-imobiliario-holding-tributario"],
    # Senior / Geriatrico
    "idoso": ["noviello-direito-senior"],
    "direito-do-senior-planejamento": [
        "noviello-direito-senior",
        "noviello-orcamentista-sucessorio",
    ],
    # Areas especificas com skill propria
    "prev": ["noviello-previdenciario"],
    "saude": ["noviello-saude-suplementar"],
    "direito-agro": ["noviello-agro"],
    "direito-civil": ["noviello-civilista-mestre"],
    # Categorias sem skill especifica (so usa as base)
    "fam": [],
    "cons": [],
    "crim": [],
    "direito-do-passageiro-aereo": [],
    "sem-categoria": [],
    "fila-social": [],
}


def resolver_skills_de_area(slugs_categorias: list[str]) -> list[str]:
    """Devolve a uniao (sem duplicatas) das skills mapeadas para os slugs.

    Slug nao mapeado e ignorado silenciosamente — usa apenas as skills base.
    """
    skills: list[str] = []
    for slug in slugs_categorias:
        if not slug:
            continue
        for s in MAPPING_SLUG_PARA_SKILLS.get(slug.lower(), []):
            if s not in skills:
                skills.append(s)
    return skills
