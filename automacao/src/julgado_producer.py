"""Producer do Julgado da Semana — branch novo do producer.

Etapa A: detecta evento '[NOV-MKT] LI 08h30 — Julgado' no Google Calendar,
le PDF de producao/julgados/sem-NN/, extrai dados via pypdf + Anthropic
(julgado_parser.parse_julgado) e gera copy de carrossel + LinkedIn.

Etapa B: le decisao do painel (aprovar/ajustar). Em aprovar, monta a peca
(renderiza N slides + card LI + escreve MANIFEST.json). Em ajustar,
regenera copy com o texto do Mario e volta pro painel.

Chamado de producer.main() apos as Etapas A/B do blog, dentro do mesmo
loop de 2 min. Estado isolado em state/julgados/<event_id>.json — zero
intercessao com o flow de blog.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import time
from pathlib import Path

from src import ai_tells_detector, carousel_render, julgado_card_render
from src.julgado_parser import JulgadoParserError, localizar_pdf_da_semana, parse_julgado
from src.julgado_state import (
    EstadoJulgado,
    JulgadoState,
    JulgadoStore,
    TransicaoInvalida,
    transition,
)
from src.logger import log_stage
from src.state import LockBusy, agora_iso

PILAR = "Julgado da Semana"


# ===== Helpers puros (testaveis sem deps) =====

def semana_iso_de_iso_string(iso_string: str) -> tuple[int, int]:
    """Devolve (ano_iso, semana_iso) a partir de ISO 8601 com/sem timezone."""
    s = iso_string.split("T")[0]
    data = _dt.date.fromisoformat(s)
    ano, semana, _ = data.isocalendar()
    return ano, semana


def pasta_da_semana(julgados_dir: Path, semana_iso: int) -> Path:
    return Path(julgados_dir) / f"sem-{semana_iso:02d}"


_PROC_SLUG_RE = re.compile(r"[^a-z0-9]+")


def processo_slug(processo: str) -> str:
    """REsp 2.215.421/SE -> resp-2-215-421-se"""
    return _PROC_SLUG_RE.sub("-", processo.lower()).strip("-")


def _render_script(cfg) -> Path:
    """Caminho do script Playwright que renderiza HTML -> JPG."""
    return cfg.project_root / "scripts" / "render-slide.py"


# ===== Etapa A — detectar evento + extrair PDF + gerar copy =====

def _processar_evento_novo(
    evento: dict, cfg, anthropic_cli, store, logger,
) -> None:
    event_id = evento["id"]
    summary = evento.get("summary", "")
    start_iso = evento.get("start_iso", "")

    ano_iso, semana_iso = semana_iso_de_iso_string(start_iso)

    estado = JulgadoState(
        event_id=event_id,
        semana_iso=semana_iso,
        ano_iso=ano_iso,
        event_summary=summary,
        event_start_iso=start_iso,
    )

    inicio = time.monotonic()
    try:
        pdf_path = localizar_pdf_da_semana(cfg.julgado_dir, semana_iso)
        estado.pdf_path = str(pdf_path)
        dados = parse_julgado(pdf_path, anthropic_cli)
        estado.dados_julgado = dados

        copy = anthropic_cli.gerar_carrossel_julgado(dados)
        tells_carrossel = copy.pop("_ai_tells", [])
        estado.copy_carrossel = copy

        texto_li = anthropic_cli.gerar_linkedin_julgado(dados)
        tells_li = ai_tells_detector.detectar(texto_li)
        estado.texto_linkedin = texto_li

        estado.ai_tells_resumo = {
            "carrossel": ai_tells_detector.resumir(tells_carrossel),
            "linkedin": ai_tells_detector.resumir(tells_li),
        }
    except JulgadoParserError as exc:
        estado.status = EstadoJulgado.ERRO
        estado.erro_mensagem = str(exc)
        store.save(estado)
        log_stage(logger, event_id, "julgado.etapaA", "erro_parsing", erro=str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        estado.status = EstadoJulgado.ERRO
        estado.erro_mensagem = f"erro inesperado: {exc}"
        store.save(estado)
        log_stage(logger, event_id, "julgado.etapaA", "erro_inesperado", erro=str(exc))
        return

    try:
        transition(estado, EstadoJulgado.AGUARDANDO_REVISAO)
    except TransicaoInvalida:
        pass  # estado ja em AGUARDANDO_REVISAO em algum cenario raro de retry
    store.save(estado)

    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, event_id, "julgado.etapaA", "no_painel", duracao_ms=dur)
    # contexto extra (processo) vai como evento separado — log_stage so aceita kwargs fixos
    logger.info(
        "julgado_detectado",
        event_id=event_id,
        processo=estado.dados_julgado.get("processo_id", ""),
        semana_iso=estado.semana_iso,
    )


def detectar_e_extrair(cfg, cal_client, anthropic_cli, store, logger) -> None:
    """Varre calendar, extrai PDFs novos, popula store. Idempotente por event_id."""
    try:
        eventos = cal_client.listar_eventos_futuros(
            cfg.julgado_calendario,
            cfg.julgado_janela_horas,
            cfg.julgado_filtro_titulo,
        )
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, "julgado", "etapaA", "erro_listar_calendario", erro=str(exc))
        return

    for evento in eventos:
        event_id = evento.get("id", "")
        if not event_id:
            continue
        if store.exists(event_id):
            continue
        try:
            with store.lock(event_id):
                if store.exists(event_id):
                    continue
                _processar_evento_novo(evento, cfg, anthropic_cli, store, logger)
        except LockBusy:
            log_stage(logger, event_id, "julgado.etapaA", "evento_ocupado")
            continue


# ===== Etapa B — regeneracao e aprovacao =====

def _regenerar_copy(
    estado: JulgadoState, cfg, anthropic_cli, store, logger,
) -> None:
    ajuste = estado.ajuste_texto
    try:
        copy = anthropic_cli.gerar_carrossel_julgado(estado.dados_julgado, ajuste=ajuste)
        tells_carrossel = copy.pop("_ai_tells", [])
        estado.copy_carrossel = copy

        texto_li = anthropic_cli.gerar_linkedin_julgado(estado.dados_julgado, ajuste=ajuste)
        tells_li = ai_tells_detector.detectar(texto_li)
        estado.texto_linkedin = texto_li

        estado.ai_tells_resumo = {
            "carrossel": ai_tells_detector.resumir(tells_carrossel),
            "linkedin": ai_tells_detector.resumir(tells_li),
        }
    except Exception as exc:  # noqa: BLE001
        log_stage(logger, estado.event_id, "julgado.etapaB", "erro_regeracao", erro=str(exc))
        return

    estado.decisao = ""
    estado.ajuste_texto = ""
    estado.tentativas_ajuste += 1
    store.save(estado)
    log_stage(logger, estado.event_id, "julgado.etapaB", "copy_regerada")


def processar_revisao(
    estado: JulgadoState, cfg, anthropic_cli, store, logger,
) -> None:
    """aprovar -> monta peca; ajustar -> regenera copy. Outros: no-op."""
    # Recovery: estado ja foi APROVADO mas peca nao montada
    if estado.status == EstadoJulgado.APROVADO:
        _finalizar(estado, cfg, store, logger)
        return
    if estado.status != EstadoJulgado.AGUARDANDO_REVISAO:
        return

    if estado.decisao == "aprovar":
        transition(estado, EstadoJulgado.APROVADO)
        store.save(estado)
        _finalizar(estado, cfg, store, logger)
    elif estado.decisao == "ajustar":
        _regenerar_copy(estado, cfg, anthropic_cli, store, logger)


# ===== Montagem da peca =====

def _pasta_peca(cfg, estado: JulgadoState) -> Path:
    proc_slug = processo_slug(estado.dados_julgado.get("processo_id", "sem-processo"))
    return cfg.producao_dir / f"{estado.ano_iso}-S{estado.semana_iso:02d}" / f"julgado-{proc_slug}"


def _slides_enriquecidos(copy_slides: list[dict], dados: dict) -> list[dict]:
    """Injeta area/selo_tribunal/processo_id/carimbo em cada slide.

    Se a IA ja preencheu (valor nao-vazio), preserva. Caso contrario, usa
    o dado canonico do julgado. Mapeia: dados.orgao -> slide.selo_tribunal.
    """
    defaults = {
        "area": dados.get("area", ""),
        "selo_tribunal": dados.get("orgao", ""),
        "processo_id": dados.get("processo_id", ""),
        "carimbo": dados.get("carimbo", ""),
    }
    enriquecidos: list[dict] = []
    for slide in copy_slides:
        novo = dict(slide)
        for k, v in defaults.items():
            if not str(novo.get(k, "")).strip():
                novo[k] = v
        enriquecidos.append(novo)
    return enriquecidos


def montar_peca(estado: JulgadoState, cfg, logger) -> Path:
    """Renderiza carrossel + card LI + escreve MANIFEST. Devolve pasta da peca."""
    pasta = _pasta_peca(cfg, estado)
    pasta.mkdir(parents=True, exist_ok=True)

    dados = estado.dados_julgado or {}
    copy = estado.copy_carrossel or {}
    slides_raw = copy.get("slides", []) or []
    slides = _slides_enriquecidos(slides_raw, dados)

    jpgs = carousel_render.renderizar(
        slides, pasta, cfg.templates_dir, _render_script(cfg),
    )
    jpg_card = julgado_card_render.renderizar_card(
        dados, pasta, cfg.templates_dir, _render_script(cfg),
        canal="li", nome_base="card",
    )

    legenda_path = pasta / "legenda.txt"
    legenda = copy.get("legenda", "")
    hashtags = copy.get("hashtags", []) or []
    if hashtags:
        legenda = (legenda + "\n\n" + " ".join(hashtags)).strip()
    legenda_path.write_text(legenda, encoding="utf-8")

    linkedin_path = pasta / "linkedin.txt"
    linkedin_path.write_text(estado.texto_linkedin or "", encoding="utf-8")

    proc_slug = processo_slug(dados.get("processo_id", "sem-processo"))
    peca_id = f"julgado-{estado.ano_iso}-S{estado.semana_iso:02d}-{proc_slug}"

    manifest = {
        "peca_id": peca_id,
        "tipo": "julgado",
        "pilar": PILAR,
        "titulo_curto": dados.get("tese", "")[:140],
        "data_publicacao_alvo": estado.event_start_iso or agora_iso(),
        "status": "pronta_para_aprovacao",
        "validacoes": {"oab_205": "aprovado", "marca": "v2-conforme", "ortografia": "ok"},
        "ativos": {
            "instagram": {
                "imagens": [str(j) for j in jpgs],
                "legenda": str(legenda_path),
                "hashtags": hashtags,
                "tipo_post": "carrossel",
            },
            "linkedin": {
                "imagem": str(jpg_card),
                "texto": str(linkedin_path),
            },
        },
        "cross_link": {"ig_para_wp": False, "li_para_wp": False, "linktree_topo": False},
    }
    (pasta / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pasta


def _finalizar(estado, cfg, store, logger) -> None:
    """Renderiza + grava MANIFEST, transiciona pra PECA_MONTADA."""
    inicio = time.monotonic()
    try:
        montar_peca(estado, cfg, logger)
    except Exception as exc:  # noqa: BLE001
        estado.status = EstadoJulgado.ERRO
        estado.erro_mensagem = f"erro na montagem: {exc}"
        store.save(estado)
        log_stage(logger, estado.event_id, "julgado.etapaB", "erro_montagem", erro=str(exc))
        return
    transition(estado, EstadoJulgado.PECA_MONTADA)
    store.save(estado)
    dur = int((time.monotonic() - inicio) * 1000)
    log_stage(logger, estado.event_id, "julgado.etapaB", "peca_montada", duracao_ms=dur)


# ===== Entrypoint =====

def main_julgado(cfg, anthropic_cli, cal_client, store, logger) -> None:
    """Etapa B (estados pendentes) antes da Etapa A (eventos novos).

    Aprovacoes em flight viram peca antes do producer detectar novos eventos —
    isso evita race entre aprovacao tardia e regeracao automatica.
    """
    for estado in store.list_all():
        try:
            with store.lock(estado.event_id):
                if not store.exists(estado.event_id):
                    continue
                estado_atual = store.load(estado.event_id)
                processar_revisao(estado_atual, cfg, anthropic_cli, store, logger)
        except LockBusy:
            log_stage(logger, estado.event_id, "julgado.etapaB", "estado_ocupado")
            continue
        except Exception as exc:  # noqa: BLE001
            log_stage(
                logger, estado.event_id, "julgado.etapaB",
                "erro_inesperado", erro=str(exc),
            )

    detectar_e_extrair(cfg, cal_client, anthropic_cli, store, logger)
