"""Shadow test: regera a Holding com sistema enriquecido e gera comparativo v1 vs v2.

NAO publica nada. NAO altera o estado. Apenas:
1. Carrega o ProducaoState 11748 (v1, ja gerada e aprovada pelo Mario)
2. Calcula o system_extra (skills base + skills da area Holding)
3. Busca o corpus do blog (20 artigos)
4. Chama anthropic_cli.gerar_carrossel + gerar_linkedin com enriquecimento
5. Salva tudo em `samples/comparacao-holding-v1-v2.md`
6. Imprime metricas (tokens, custo, latencia)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.anthropic_client import AnthropicClient
from src.area_resolver import resolver_skills_de_area
from src.blog_corpus import pegar_corpus_blog
from src.config import load_config
from src.producer import SKILLS_BASE
from src.producer_state import ProducaoStore
from src.skills_loader import SkillsLoader


def _formatar_slides_md(slides: list[dict]) -> str:
    linhas = []
    for i, s in enumerate(slides, 1):
        linhas.append(f"**Slide {i}: {s.get('titulo','')}**")
        linhas.append("")
        linhas.append(s.get("corpo", "").replace("\n", "  \n"))
        linhas.append("")
        linhas.append("---")
        linhas.append("")
    return "\n".join(linhas)


def main() -> int:
    cfg = load_config()
    print(f"skills_dir: {cfg.skills_dir}")
    if not (cfg.skills_dir and cfg.skills_dir.exists()):
        print("ERRO: skills_dir nao encontrado")
        return 1

    skills_loader = SkillsLoader(cfg.skills_dir)
    store = ProducaoStore(cfg.state_dir)
    if not store.exists("11748"):
        print("ERRO: ProducaoStore 11748 nao existe — peca Holding nao disponivel")
        return 1
    estado = store.load("11748")
    print(f"v1 (ja existe): {len(estado.copy_carrossel.get('slides', []))} slides, "
          f"legenda {len(estado.copy_carrossel.get('legenda',''))} chars")

    # Categorias do artigo Holding: pelo que sei do WP, post 11748 tem categoria
    # 849 (Fila Social) e 1 (Sem categoria). Tema real do artigo: Holding/Sucessorio.
    # Aqui forco os slugs corretos (no fluxo real eles viriam do _resolver_skills_de_artigo).
    slugs_holding = ["holding-patrimonial", "planejamento-sucessorio", "imob"]
    area_skills = resolver_skills_de_area(slugs_holding)
    todas = list(SKILLS_BASE)
    for s in area_skills:
        if s not in todas:
            todas.append(s)
    print(f"skills carregadas ({len(todas)}): {todas}")

    # Mede o tamanho de cada bloco
    system_extra = skills_loader.combine(todas, ignore_missing=True)
    print(f"system_extra: {len(system_extra)} chars (~{len(system_extra)//4} tokens estimados)")

    # Corpus do blog (cache 24h interno)
    wp_base = "https://noviello.adv.br"
    wp_auth = (cfg.wordpress["user"], cfg.wordpress["app_password_noviello"])
    contexto_blog = pegar_corpus_blog(cfg.state_dir, wp_base, wp_auth, top_n=20)
    print(f"contexto_blog: {len(contexto_blog)} chars (~{len(contexto_blog)//4} tokens estimados)")

    # Chama a IA com enriquecimento
    anthropic_cli = AnthropicClient(cfg.anthropic, cfg.templates_dir)

    print("\n=== gerando v2 do carrossel (sonnet com enriquecimento)... ===")
    t0 = time.monotonic()
    v2_carrossel = anthropic_cli.gerar_carrossel(
        estado.artigo_texto, estado.titulo,
        system_extra=system_extra,
        contexto_blog=contexto_blog,
    )
    t_carr = time.monotonic() - t0
    print(f"  duracao: {t_carr:.1f}s, {len(v2_carrossel['slides'])} slides")

    print("\n=== gerando v2 do LinkedIn... ===")
    t0 = time.monotonic()
    v2_linkedin = anthropic_cli.gerar_linkedin(
        estado.artigo_texto, estado.titulo,
        f"https://noviello.adv.br/?p={estado.post_id}",
        system_extra=system_extra,
        contexto_blog=contexto_blog,
    )
    t_li = time.monotonic() - t0
    print(f"  duracao: {t_li:.1f}s, {len(v2_linkedin)} chars")

    # Persiste a v2 raw para inspecao
    out_json = Path(__file__).parent / "holding-v2-raw.json"
    out_json.write_text(
        json.dumps(
            {
                "v2_carrossel": v2_carrossel,
                "v2_linkedin": v2_linkedin,
                "duracao_carrossel_s": t_carr,
                "duracao_linkedin_s": t_li,
                "skills_carregadas": todas,
                "system_extra_chars": len(system_extra),
                "contexto_blog_chars": len(contexto_blog),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nraw salvo em: {out_json}")

    # Comparativo markdown side-by-side
    md = [
        "# Comparacao Holding v1 (legado) vs v2 (enriquecido)",
        "",
        "**Artigo:** Holding Familiar: Desmistificando o Planejamento Sucessorio para Todos, Nao Apenas Bilionarios (post 11748)",
        "",
        "## Metadata",
        "",
        f"- **v1**: gerada em 19/05 ~21:44, modelo `{cfg.anthropic.get('model')}`, "
        "system = brief-marca.txt apenas (~43 linhas).",
        f"- **v2**: gerada agora, mesmo modelo, "
        f"system enriquecido com {len(todas)} skills + corpus de 20 artigos do blog.",
        f"- **Skills carregadas**: {', '.join(todas)}",
        f"- **System extra**: {len(system_extra)} chars (~{len(system_extra)//4} tokens)",
        f"- **Corpus do blog**: {len(contexto_blog)} chars (~{len(contexto_blog)//4} tokens)",
        f"- **Latencia v2 (carrossel)**: {t_carr:.1f}s",
        f"- **Latencia v2 (LinkedIn)**: {t_li:.1f}s",
        "",
        "## Carrossel — v1 (atual)",
        "",
        _formatar_slides_md(estado.copy_carrossel["slides"]),
        "",
        "## Carrossel — v2 (enriquecida)",
        "",
        _formatar_slides_md(v2_carrossel["slides"]),
        "",
        "## Legenda v1",
        "",
        "```",
        estado.copy_carrossel.get("legenda", ""),
        "```",
        "",
        "## Legenda v2",
        "",
        "```",
        v2_carrossel.get("legenda", ""),
        "```",
        "",
        "## Hashtags",
        "",
        f"- **v1**: {' '.join(estado.copy_carrossel.get('hashtags', []))}",
        f"- **v2**: {' '.join(v2_carrossel.get('hashtags', []))}",
        "",
        "## LinkedIn v1",
        "",
        "```",
        estado.texto_linkedin or "(vazio)",
        "```",
        "",
        "## LinkedIn v2",
        "",
        "```",
        v2_linkedin,
        "```",
    ]
    out_md = Path(__file__).parent / "comparacao-holding-v1-v2.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"comparacao salva em: {out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
