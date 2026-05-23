"""Publisher WordPress — REST API (stage 05c).

Dois modos:
- ativos.wordpress.post_id_existente presente -> publica o rascunho ja existente
  (gerado pelo plugin): muda status para publish, injeta o HTML estilizado e remove
  a categoria "Fila Social". Nao cria post novo (evita duplicar).
- ausente -> cria um post novo (comportamento padrao).
"""

from __future__ import annotations

from pathlib import Path

from src.manifest import Peca
from src.publish_result import PublishResult
from src.wp_client import WordPressClient

NOME = "wordpress"


def _app_passwords(cfg) -> dict[str, str]:
    return {
        "noviello": cfg.wordpress.get("app_password_noviello", ""),
        "imobiliario": cfg.wordpress.get("app_password_imobiliario", ""),
    }


def pronto(cfg) -> bool:
    return cfg.wordpress_pronto()


def motivo_indisponivel(cfg) -> str:
    return "credencial WordPress ausente (WP_USER / WP_APP_PASSWORD_*)"


def publish(peca: Peca, cfg, logger) -> PublishResult:
    wp_ativos = peca.ativos("wordpress") or {}
    if not wp_ativos:
        return PublishResult.pulado(NOME, "sem ativos WordPress no MANIFEST")

    site = wp_ativos.get("site_destino", "noviello")
    cliente = WordPressClient(cfg.wordpress["user"], _app_passwords(cfg))
    if not cliente.site_disponivel(site):
        return PublishResult.pulado(NOME, f"sem App Password para o site '{site}'")

    # imagem destaque
    featured_id = None
    destaque = wp_ativos.get("imagem_destaque")
    if destaque and Path(destaque).exists():
        midia = cliente.upload_media(destaque, site)
        featured_id = midia["id"]

    conteudo = ""
    if wp_ativos.get("conteudo_html") and Path(wp_ativos["conteudo_html"]).exists():
        conteudo = Path(wp_ativos["conteudo_html"]).read_text(encoding="utf-8")

    post_id_existente = wp_ativos.get("post_id_existente")
    status_alvo = wp_ativos.get("status_alvo", "publish")

    if post_id_existente:
        # modo: publicar rascunho existente do plugin
        atual = cliente.get_json(
            site, f"posts/{post_id_existente}", {"_fields": "categories"}
        )
        cats = atual.get("categories", []) if isinstance(atual, dict) else []
        fila_nome = cfg.wp_categoria_fila_social
        fila_id = next(
            (
                c["id"]
                for c in cliente.get_categories(site, fila_nome)
                if c.get("name", "").strip().lower() == fila_nome.strip().lower()
            ),
            None,
        )
        cats_finais = [c for c in cats if c != fila_id] if fila_id else cats

        campos = {
            "status": status_alvo,
            "content": conteudo,
            "title": wp_ativos.get("titulo", peca.titulo_curto),
            "categories": cats_finais,
        }
        if featured_id:
            campos["featured_media"] = featured_id
        post = cliente.update_post(site, post_id_existente, campos)
        return PublishResult.sucesso(
            NOME, post["link"], ids={"post_id": post["id"], "modo": "rascunho_existente"}
        )

    # modo padrao: criar post novo
    post = cliente.create_post(
        site,
        titulo=wp_ativos.get("titulo", peca.titulo_curto),
        slug=wp_ativos.get("slug", ""),
        conteudo_html=conteudo,
        status=status_alvo,
        featured_media=featured_id,
        categoria=wp_ativos.get("categoria"),
        tags=wp_ativos.get("tags"),
        meta_description=wp_ativos.get("meta_description", ""),
        data=peca.data_publicacao_alvo,
    )
    return PublishResult.sucesso(NOME, post["link"], ids={"post_id": post["id"], "modo": "novo"})
