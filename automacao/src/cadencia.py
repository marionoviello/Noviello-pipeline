"""Cadencia semanal automatica — promotor de backlog (Batch 5).

Le eventos `[NOV-BLOG] Publicacao WordPress` (configuravel) do calendario
'Noviello — Marketing' nas proximas N horas. Para cada evento ainda nao
processado, pega o rascunho mais antigo da categoria 'Backlog Editorial' e
move para 'Fila Social' (adiciona Fila Social, remove Backlog). O producer
normal pega daquele ponto em diante.

Idempotencia: estado em state/cadencia.json registra cada event_id ja
processado. Re-execucoes nao duplicam.

Kill switches:
  - .env CADENCIA_ATIVA=false   -> override total (qualquer estado)
  - state/cadencia.json::ativa  -> toggle do painel (usado dia-a-dia)

Rodar:  .venv\\Scripts\\python.exe -m src.cadencia   (cwd = automacao/)
"""

from __future__ import annotations

import time

from src.cadencia_state import CadenciaState
from src.calendar_client import CalendarClient
from src.config import load_config
from src.logger import get_logger, log_stage, setup_logging
from src.wp_client import WordPressClient
from src.wp_source import CategoriaNaoEncontrada, WordPressSource

SITE = "noviello"


def _wp_passwords(cfg) -> dict[str, str]:
    return {
        "noviello": cfg.wordpress.get("app_password_noviello", ""),
        "imobiliario": cfg.wordpress.get("app_password_imobiliario", ""),
    }


def promover_artigo(
    wp_client: WordPressClient,
    artigo,
    backlog_cat_id: int,
    fila_social_cat_id: int,
) -> dict:
    """Move o artigo da categoria backlog para fila social (atomico no WP)."""
    cats_atuais = list(artigo.categorias)
    cats_novas = [c for c in cats_atuais if c != backlog_cat_id]
    if fila_social_cat_id not in cats_novas:
        cats_novas.append(fila_social_cat_id)
    return wp_client.update_post(SITE, artigo.post_id, {"categories": cats_novas})


def main() -> int:
    cfg = load_config()
    setup_logging(cfg.logs_dir)
    logger = get_logger("cadencia")

    # kill switch .env (mais alto na hierarquia)
    if not cfg.cadencia_ativa:
        logger.info("cadencia", status="desativada_via_env")
        return 0

    state = CadenciaState.carregar(cfg.state_dir)

    # kill switch painel
    if not state.ativa:
        logger.info("cadencia", status="desativada_via_painel")
        state.marcar_run()
        state.salvar(cfg.state_dir)
        return 0

    if not cfg.google_pronto():
        logger.info("cadencia", status="aguardando_credencial_google")
        return 0
    if not cfg.wordpress_pronto():
        logger.info("cadencia", status="aguardando_credencial_wordpress")
        return 0

    inicio = time.monotonic()
    cal = CalendarClient(cfg.google)
    eventos = cal.listar_eventos_futuros(
        cfg.cadencia_calendario,
        cfg.cadencia_janela_horas,
        cfg.cadencia_filtro_titulo,
    )

    if not eventos:
        logger.info(
            "cadencia",
            status="sem_eventos_na_janela",
            janela_horas=cfg.cadencia_janela_horas,
        )
        state.marcar_run()
        state.salvar(cfg.state_dir)
        return 0

    wp = WordPressClient(cfg.wordpress["user"], _wp_passwords(cfg))
    src = WordPressSource(wp, cfg.wp_categoria_fila_social)

    try:
        backlog_cat_id = src.resolver_categoria(cfg.wp_categoria_backlog)
        fila_social_cat_id = src.categoria_id()
    except CategoriaNaoEncontrada as exc:
        log_stage(logger, "-", "cadencia", "categoria_inexistente", erro=str(exc))
        return 1

    promovidos = 0
    for evento in eventos:
        if state.evento_ja_promovido(evento["id"]):
            continue

        # busca backlog FIFO
        backlog = src.listar_backlog(cfg.wp_categoria_backlog)
        if not backlog:
            logger.info(
                "cadencia",
                status="backlog_vazio",
                evento_pendente=evento.get("summary", ""),
                evento_em=evento.get("start_iso", ""),
            )
            break  # sem nada pra promover, para

        artigo = backlog[0]

        try:
            promover_artigo(wp, artigo, backlog_cat_id, fila_social_cat_id)
        except Exception as exc:  # noqa: BLE001
            log_stage(
                logger, str(artigo.post_id), "cadencia", "erro_promocao",
                evento_id=evento["id"], erro=str(exc),
            )
            continue

        state.registrar_promocao(
            event_id=evento["id"],
            data_evento_iso=evento.get("start_iso", ""),
            titulo_evento=evento.get("summary", ""),
            post_id=artigo.post_id,
            post_titulo=artigo.titulo,
        )
        state.salvar(cfg.state_dir)
        promovidos += 1
        log_stage(
            logger, str(artigo.post_id), "cadencia", "promovido",
            evento=evento.get("summary", ""),
            evento_em=evento.get("start_iso", ""),
            post_titulo=artigo.titulo,
        )

    state.marcar_run()
    state.salvar(cfg.state_dir)
    dur = int((time.monotonic() - inicio) * 1000)
    logger.info(
        "cadencia",
        status="fim",
        eventos_na_janela=len(eventos),
        promovidos=promovidos,
        duracao_ms=dur,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
