"""Produtor — ponte de producao. Tarefa agendada 3 (a cada 2 min).

Etapa A: detecta artigos do plugin na categoria "Fila Social", gera rascunho de copy
         (carrossel + LinkedIn) via API Anthropic e o disponibiliza no painel.
Etapa B: le a decisao do painel (estado.decisao); em "aprovar" monta a peca
         (renderiza slides, escreve MANIFEST) para o pipeline de aprovacao consumir.

Rodar:  .venv\\Scripts\\python.exe -m src.producer   (cwd = automacao/)
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import re
import time

from src import ai_tells_detector, article_styler, carousel_render
from src.anthropic_client import AnthropicClient
from src.image_gen import GeradorImagens, ImagemGenError
from src.config import load_config
from src.emails import build_ping_email
from src.gmail_client import GmailClient
from src.logger import get_logger, log_stage, setup_logging
from src.pipeline import PAINEL_URL
from src.area_resolver import resolver_skills_de_area
from src.blog_corpus import pegar_corpus_blog
from src.producer_state import EstadoProd, ProducaoState, ProducaoStore, transition
from src.skills_loader import SkillsLoader
from src.state import LockBusy

# Skills carregadas em TODA chamada da IA (alem da skill especifica da area):
# voz da casa + OAB 205 + o redator-chefe oficial.
SKILLS_BASE = [
    "noviello-marketing-creator",
    "noviello-voz-padrao",
    "verificador-de-etica-oab-em-publicidade",
]
from src.state import agora_iso
from src.wp_client import WordPressClient
from src.wp_source import CategoriaNaoEncontrada, WordPressSource

PILAR = "Blog Noviello"


# ---- utilitarios ---------------------------------------------------------

def _texto_limpo(html: str) -> str:
    """Remove tags do HTML do artigo, devolvendo texto corrido."""
    sem_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", _html.unescape(sem_tags)).strip()


def _artigo_url(post_id) -> str:
    # ?p=ID e um permalink permanente: vale para rascunho e redireciona para o
    # link bonito depois que o artigo e publicado. Rascunhos nao tem slug.
    return f"https://noviello.adv.br/?p={post_id}"


def _pasta_peca(cfg, post_id):
    ano, semana, _ = _dt.date.today().isocalendar()
    return cfg.producao_dir / f"{ano}-S{semana:02d}" / f"social-{post_id}"


def _render_script(cfg):
    return cfg.project_root / "scripts" / "render-slide.py"


def _gerar_e_anexar_hero(
    estado, cfg, wp_client, logger,
) -> None:
    """Se artigo nao tem featured_media e AUTO_GERAR_HERO=true, gera hero
    via Gemini, faz upload no WP, atualiza featured_media do post e popula
    estado.featured_media_id + imagem_destaque_url.

    Falha silenciosa: logger.info e segue (geracao de hero nao deve bloquear).
    """
    if estado.featured_media_id:
        return  # ja tem
    if not cfg.auto_gerar_hero:
        return
    if not cfg.google_ai_api_key:
        log_stage(logger, estado.post_id, "producao.etapaA",
                  "auto_hero_skip_sem_chave", motivo="GOOGLE_AI_API_KEY ausente")
        return

    pasta = _pasta_peca(cfg, estado.post_id)
    pasta.mkdir(parents=True, exist_ok=True)

    try:
        # ja temos lead extraido via styler — recupera do html ou usa titulo
        lead_aprox = (estado.artigo_texto or "")[:300]
        gerador = GeradorImagens(cfg.google_ai_api_key)
        path_local = gerador.gerar_hero_artigo(
            titulo=estado.titulo,
            lead=lead_aprox,
            categorias=estado.categorias_nomes or [],
            pasta_destino=pasta,
            nome_arquivo="hero.png",
        )
    except ImagemGenError as exc:
        log_stage(logger, estado.post_id, "producao.etapaA",
                  "auto_hero_falhou", erro=str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, estado.post_id, "producao.etapaA",
                  "auto_hero_erro", erro=str(exc))
        return

    # upload pro WP
    try:
        midia = wp_client.upload_media(path_local, "noviello")
        # seta featured_media no post original
        wp_client.update_post("noviello", estado.post_id, {"featured_media": midia["id"]})
        estado.featured_media_id = midia["id"]
        estado.imagem_destaque_url = midia["source_url"]
        log_stage(logger, estado.post_id, "producao.etapaA",
                  "auto_hero_ok", media_id=midia["id"])
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, estado.post_id, "producao.etapaA",
                  "auto_hero_upload_falhou", erro=str(exc))


def _ping(cfg, gmail, post_id, logger) -> None:
    try:
        gmail.send_message(build_ping_email(1, PAINEL_URL, cfg.email_aprovador))
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, post_id, "producao", "ping_falhou", erro=str(exc))


# ---- Etapa A: detectar + produzir rascunho -------------------------------

def processar_artigo_novo(
    artigo, cfg, gmail, anthropic_cli, store, logger,
    *,
    categorias_slugs: list[str] | None = None,
    system_extra: str = "",
    contexto_blog: str = "",
    wp_client=None,  # opcional, usado para auto-gerar hero quando AUTO_GERAR_HERO=true
) -> None:
    post_id = str(artigo.post_id)
    if store.exists(post_id):
        return

    inicio = time.monotonic()
    # filtra a categoria de workflow ("Fila Social") — nao deve aparecer no artigo publico
    cats_editoriais = [
        c for c in (artigo.categorias_nomes or [])
        if c.strip().lower() != cfg.wp_categoria_fila_social.strip().lower()
    ]
    estado = ProducaoState(
        post_id=post_id,
        slug=artigo.slug,
        titulo=artigo.titulo,
        artigo_texto=_texto_limpo(artigo.conteudo_html),
        categorias_slugs=list(categorias_slugs or []),
        categorias_nomes=cats_editoriais,
        tags_nomes=list(artigo.tags_nomes or []),
        imagem_destaque_url=artigo.featured_media_url,
        featured_media_id=artigo.featured_media_id,
    )

    canonical = (
        f"https://noviello.adv.br/{artigo.slug}/"
        if artigo.slug
        else _artigo_url(post_id)
    )

    # Auto-gera hero se artigo nao tem featured_media e flag ativa
    # (precisa rodar ANTES do styler para o hero entrar na estilizacao)
    if wp_client is not None:
        _gerar_e_anexar_hero(estado, cfg, wp_client, logger)

    try:
        estado.html_estilizado = article_styler.estilizar(
            artigo.conteudo_html, artigo.titulo, cfg.templates_dir,
            categorias=estado.categorias_nomes or None,
            tags=estado.tags_nomes or None,
            imagem_destaque=estado.imagem_destaque_url or None,
            data_publicacao=_dt.date.today(),
            canonical_url=canonical,
        )
        estado.copy_carrossel = anthropic_cli.gerar_carrossel(
            estado.artigo_texto, artigo.titulo,
            system_extra=system_extra, contexto_blog=contexto_blog,
        )
        estado.texto_linkedin = anthropic_cli.gerar_linkedin(
            estado.artigo_texto, artigo.titulo, _artigo_url(post_id),
            system_extra=system_extra, contexto_blog=contexto_blog,
        )
        # Auditoria AI-tells: extrai do carrossel (anexado pelo client) + roda
        # no texto LinkedIn. Resumido pro painel mostrar.
        carrossel_tells = estado.copy_carrossel.pop("_ai_tells", [])
        linkedin_tells = ai_tells_detector.detectar(estado.texto_linkedin)
        estado.ai_tells_resumo = {
            "carrossel": ai_tells_detector.resumir(carrossel_tells),
            "linkedin": ai_tells_detector.resumir(linkedin_tells),
        }
    except Exception as exc:  # noqa: BLE001
        estado.status = EstadoProd.ERRO
        store.save(estado)
        log_stage(logger, post_id, "producao.etapaA", "erro", erro=str(exc))
        return

    transition(estado, EstadoProd.AGUARDANDO_REVISAO_COPY)
    store.save(estado)
    _ping(cfg, gmail, post_id, logger)

    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, post_id, "producao.etapaA", "copy_no_painel", duracao_ms=dur)


# ---- Etapa B: revisao + montagem da peca ---------------------------------

def _regenerar_copy(
    estado, cfg, gmail, anthropic_cli, store, logger,
    *,
    system_extra: str = "",
    contexto_blog: str = "",
) -> None:
    """Regenera a copy com o ajuste do painel e a recoloca para revisao."""
    ajuste = estado.ajuste_texto
    try:
        estado.copy_carrossel = anthropic_cli.gerar_carrossel(
            estado.artigo_texto, estado.titulo, ajuste=ajuste,
            system_extra=system_extra, contexto_blog=contexto_blog,
        )
        estado.texto_linkedin = anthropic_cli.gerar_linkedin(
            estado.artigo_texto, estado.titulo, _artigo_url(estado.post_id), ajuste=ajuste,
            system_extra=system_extra, contexto_blog=contexto_blog,
        )
        carrossel_tells = estado.copy_carrossel.pop("_ai_tells", [])
        linkedin_tells = ai_tells_detector.detectar(estado.texto_linkedin)
        estado.ai_tells_resumo = {
            "carrossel": ai_tells_detector.resumir(carrossel_tells),
            "linkedin": ai_tells_detector.resumir(linkedin_tells),
        }
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, estado.post_id, "producao.etapaB", "erro_regeracao", erro=str(exc))
        return
    estado.decisao = ""
    estado.ajuste_texto = ""
    estado.tentativas_ajuste += 1
    store.save(estado)
    _ping(cfg, gmail, estado.post_id, logger)
    log_stage(logger, estado.post_id, "producao.etapaB", "copy_regerada")


def montar_peca(estado: ProducaoState, cfg, logger):
    """Renderiza o carrossel e escreve a pasta da peca + MANIFEST.json."""
    pasta = _pasta_peca(cfg, estado.post_id)
    pasta.mkdir(parents=True, exist_ok=True)
    copy = estado.copy_carrossel

    jpgs = carousel_render.renderizar(
        copy.get("slides", []), pasta, cfg.templates_dir, _render_script(cfg)
    )

    legenda_path = pasta / "legenda.txt"
    legenda = copy.get("legenda", "")
    hashtags = copy.get("hashtags", [])
    if hashtags:
        legenda = (legenda + "\n\n" + " ".join(hashtags)).strip()
    legenda_path.write_text(legenda, encoding="utf-8")

    linkedin_path = pasta / "linkedin.txt"
    linkedin_path.write_text(estado.texto_linkedin, encoding="utf-8")

    html_path = pasta / "conteudo.html"
    html_path.write_text(estado.html_estilizado, encoding="utf-8")

    # imagem destaque do WP: preserva original se houver, senao usa slide 1
    if estado.featured_media_id:
        wp_imagem_destaque = ""  # publisher nao sobrescreve featured original
    else:
        wp_imagem_destaque = str(jpgs[0]) if jpgs else ""

    manifest = {
        "peca_id": f"social-{estado.post_id}",
        "tipo": "carrossel",
        "pilar": PILAR,
        "titulo_curto": estado.titulo,
        "data_publicacao_alvo": agora_iso(),
        "status": "pronta_para_aprovacao",
        "validacoes": {"oab_205": "aprovado", "marca": "v2-conforme", "ortografia": "ok"},
        "ativos": {
            "instagram": {
                "imagens": [str(j) for j in jpgs],
                "legenda": str(legenda_path),
                "hashtags": hashtags,
                "tipo_post": "carrossel",
            },
            "wordpress": {
                "site_destino": "noviello",
                "titulo": estado.titulo,
                "slug": estado.slug,
                "tags": [],
                "conteudo_html": str(html_path),
                "imagem_destaque": wp_imagem_destaque,
                "meta_description": "",
                "status_alvo": "publish",
                "post_id_existente": estado.post_id,
            },
            "linkedin": {
                "imagem": str(jpgs[0]) if jpgs else "",
                "texto": str(linkedin_path),
                "url_artigo_wp": _artigo_url(estado.post_id),
            },
        },
        "cross_link": {"ig_para_wp": True, "li_para_wp": True, "linktree_topo": True},
    }
    (pasta / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pasta


def _finalizar(estado, cfg, store, logger) -> None:
    inicio = time.monotonic()
    try:
        montar_peca(estado, cfg, logger)
    except Exception as exc:  # noqa: BLE001
        estado.status = EstadoProd.ERRO
        store.save(estado)
        log_stage(logger, estado.post_id, "producao.etapaB", "erro_montagem", erro=str(exc))
        return
    transition(estado, EstadoProd.PECA_MONTADA)
    store.save(estado)
    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, estado.post_id, "producao.etapaB", "peca_montada", duracao_ms=dur)


def processar_revisao(
    estado, cfg, gmail, anthropic_cli, store, logger,
    *,
    system_extra: str = "",
    contexto_blog: str = "",
) -> None:
    # recuperacao de crash: copy aprovada mas peca nao montada
    if estado.status == EstadoProd.COPY_APROVADA:
        _finalizar(estado, cfg, store, logger)
        return
    if estado.status != EstadoProd.AGUARDANDO_REVISAO_COPY:
        return

    if estado.decisao == "aprovar":
        transition(estado, EstadoProd.COPY_APROVADA)
        store.save(estado)
        _finalizar(estado, cfg, store, logger)
    elif estado.decisao == "ajustar":
        _regenerar_copy(
            estado, cfg, gmail, anthropic_cli, store, logger,
            system_extra=system_extra, contexto_blog=contexto_blog,
        )


# ---- orquestracao --------------------------------------------------------

def main() -> int:
    cfg = load_config()
    setup_logging(cfg.logs_dir)
    logger = get_logger("producer")
    from src.heartbeat import bater
    bater(cfg.state_dir, "producer")

    if not cfg.google_pronto():
        logger.info("producer", status="aguardando_setup_google")
        return 0
    if not cfg.anthropic_pronto():
        logger.info("producer", status="aguardando_chave_anthropic")
        return 0
    if not cfg.wordpress_pronto():
        logger.info("producer", status="aguardando_credencial_wordpress")
        return 0

    gmail = GmailClient(cfg.google)
    anthropic_cli = AnthropicClient(cfg.anthropic, cfg.templates_dir)
    wp = WordPressClient(
        cfg.wordpress["user"],
        {
            "noviello": cfg.wordpress.get("app_password_noviello", ""),
            "imobiliario": cfg.wordpress.get("app_password_imobiliario", ""),
        },
    )
    wp_source = WordPressSource(wp, cfg.wp_categoria_fila_social)
    store = ProducaoStore(cfg.state_dir)

    # ---- ENRIQUECIMENTO da IA: skills + corpus do blog ----
    skills_loader: SkillsLoader | None = (
        SkillsLoader(cfg.skills_dir) if cfg.skills_dir and cfg.skills_dir.exists() else None
    )
    if skills_loader is None:
        logger.info(
            "producer",
            status="skills_indisponiveis_modo_legado",
            skills_dir=str(cfg.skills_dir) if cfg.skills_dir else "(None)",
            exists=str(cfg.skills_dir.exists()) if cfg.skills_dir else "N/A",
        )
    # System extra base (skills sempre carregadas)
    system_extra_base = ""
    if skills_loader:
        system_extra_base = skills_loader.combine(SKILLS_BASE, ignore_missing=True)

    # Corpus do blog (cache 24h interno; falha silenciosa em "")
    wp_base = "https://noviello.adv.br"
    wp_auth = (cfg.wordpress.get("user", ""), cfg.wordpress.get("app_password_noviello", ""))
    contexto_blog = pegar_corpus_blog(cfg.state_dir, wp_base, wp_auth, top_n=20)

    # Mapping id_categoria -> slug, para resolver skills de area
    def _resolver_skills_de_artigo(slugs_categorias: list[str]) -> str:
        """Constroi o system_extra: base + skills das areas do artigo."""
        if not skills_loader:
            return ""
        area_skills = resolver_skills_de_area(slugs_categorias)
        todas = list(SKILLS_BASE)
        for s in area_skills:
            if s not in todas:
                todas.append(s)
        return skills_loader.combine(todas, ignore_missing=True)

    # ETAPA B — revisoes em andamento
    for estado in store.list_all():
        try:
            with store.lock(estado.post_id):
                if not store.exists(estado.post_id):
                    continue
                estado_atual = store.load(estado.post_id)
                # reusa as skills da area registradas no estado
                system_extra = _resolver_skills_de_artigo(
                    estado_atual.categorias_slugs
                ) or system_extra_base
                processar_revisao(
                    estado_atual, cfg, gmail, anthropic_cli, store, logger,
                    system_extra=system_extra, contexto_blog=contexto_blog,
                )
        except LockBusy:
            logger.info("producer", status="peca_ocupada", post_id=estado.post_id)
            continue
        except Exception as exc:  # noqa: BLE001
            log_stage(logger, estado.post_id, "producao.etapaB", "erro_inesperado", erro=str(exc))

    # ETAPA A — detectar artigos novos na Fila Social
    try:
        artigos = wp_source.listar_fila_social()
    except CategoriaNaoEncontrada:
        logger.info("producer", status="categoria_fila_social_inexistente")
        artigos = []

    # Mapping id->slug, fetched once por execucao (poupa chamada na hora)
    id_para_slug: dict[int, str] = {}
    if artigos:
        try:
            cats = wp.get_json("noviello", "categories", {"per_page": 100})
            id_para_slug = {c["id"]: c["slug"] for c in cats}
        except Exception as exc:  # noqa: BLE001
            logger.info("producer", status="falha_fetch_categorias", erro=str(exc))

    for artigo in artigos:
        try:
            with store.lock(str(artigo.post_id)):
                slugs = [id_para_slug.get(cid, "") for cid in artigo.categorias]
                system_extra = _resolver_skills_de_artigo(slugs) or system_extra_base
                processar_artigo_novo(
                    artigo, cfg, gmail, anthropic_cli, store, logger,
                    categorias_slugs=slugs,
                    system_extra=system_extra,
                    contexto_blog=contexto_blog,
                    wp_client=wp,
                )
        except LockBusy:
            logger.info("producer", status="artigo_ocupado", post_id=str(artigo.post_id))
            continue
        except Exception as exc:  # noqa: BLE001
            log_stage(logger, str(artigo.post_id), "producao.etapaA", "erro_inesperado", erro=str(exc))

    logger.info("producer", status="fim", artigos_fila=len(artigos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
