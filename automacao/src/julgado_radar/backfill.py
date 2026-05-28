"""Backfill historico STJ + TJ-SP — orquestrador rodavel via CLI.

Uso:
  python -m src.julgado_radar.backfill --janela 5 --fontes stj,tjsp
  python -m src.julgado_radar.backfill --janela 1 --fontes stj
  python -m src.julgado_radar.backfill --janela 2 --fontes tjsp --areas imobiliario,sucessorio

Idempotente: usa fetch_log pra pular fontes ja processadas com status=ok.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import logging
import sys
import time
import traceback
from calendar import monthrange
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from src.config import Config, load_config
from src.julgado_radar import db, feeds_stj, feeds_tjsp, indexer, parser
from src.julgado_radar.config import (
    AREA_FORA,
    AREAS_ALVO,
    FONTES,
    JANELA_ANOS_DEFAULT,
    TRIBUNAL_STJ,
    TRIBUNAL_TJSP,
)
from src.julgado_radar.models import Descartado, Julgado
from src.state import agora_iso

logger = logging.getLogger("radar.backfill")


@dataclass
class Stats:
    """Contadores agregados de uma execucao de backfill."""

    stj_inseridos: int = 0
    stj_atualizados: int = 0
    stj_descartados: int = 0
    stj_erros: int = 0
    tjsp_inseridos: int = 0
    tjsp_atualizados: int = 0
    tjsp_descartados: int = 0
    tjsp_erros: int = 0
    por_area: dict[tuple[str, str], int] = field(default_factory=dict)
    inicio: float = 0.0
    fim: float = 0.0

    @property
    def duracao_seg(self) -> float:
        return max(0.0, self.fim - self.inicio)

    def como_dict(self) -> dict:
        return {
            "stj": {
                "inseridos": self.stj_inseridos,
                "atualizados": self.stj_atualizados,
                "descartados": self.stj_descartados,
                "erros": self.stj_erros,
            },
            "tjsp": {
                "inseridos": self.tjsp_inseridos,
                "atualizados": self.tjsp_atualizados,
                "descartados": self.tjsp_descartados,
                "erros": self.tjsp_erros,
            },
            "por_tribunal_area": {
                f"{trib}:{area}": n for (trib, area), n in self.por_area.items()
            },
            "duracao_seg": round(self.duracao_seg, 1),
        }


# ===== STJ =====

def _processar_stj(
    conn,
    anos: list[int],
    cache_dir: Path,
    anthropic_cli,
    stats: Stats,
    *,
    playwright_factory=None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Itera informativos da janela, baixa via Playwright, parseia e indexa."""
    try:
        refs = feeds_stj.descobrir_informativos(
            anos, playwright_factory=playwright_factory,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("falha descoberta STJ: %s", exc)
        stats.stj_erros += 1
        return

    for ref in refs:
        if indexer.fetch_ja_feito(conn, ref.fonte_key):
            continue
        try:
            html_path = feeds_stj.baixar_informativo(
                ref, cache_dir,
                playwright_factory=playwright_factory, sleep_fn=sleep_fn,
            )
        except feeds_stj.FeedSTJError as exc:
            indexer.registrar_fetch(conn, ref.fonte_key, "erro", erro=str(exc))
            stats.stj_erros += 1
            continue

        try:
            resultado = parser.extrair_itens_de_informativo(html_path, anthropic_cli)
        except Exception as exc:  # noqa: BLE001
            indexer.registrar_fetch(conn, ref.fonte_key, "erro", erro=str(exc))
            stats.stj_erros += 1
            continue

        julgados = []
        for item in resultado["aceitos"]:
            julgados.append(Julgado(
                tribunal=TRIBUNAL_STJ,
                processo_id=item["processo_id"],
                relator=item.get("relator", ""),
                orgao=item.get("orgao", ""),
                data_julgamento=item.get("data_julgamento", ""),
                area=item["area"],
                classe=item.get("classe", ""),
                tese=item["tese"],
                ementa=item.get("ementa", ""),
                citacao_voto=item.get("citacao_voto", ""),
                fundamentos=item.get("fundamentos", []),
                url_fonte=ref.url_pdf,
                pdf_local=str(html_path),
                info_origem=ref.fonte_key,
                indexado_em=agora_iso(),
            ))

        s = indexer.indexar_batch(conn, julgados)
        stats.stj_inseridos += s["inseridos"]
        stats.stj_atualizados += s["atualizados"]

        for d in resultado["descartados"]:
            indexer.registrar_descartado(conn, Descartado(
                tribunal=TRIBUNAL_STJ,
                processo_id=(d.get("item") or {}).get("processo_id", ""),
                motivo=d.get("motivo", "desconhecido"),
                payload=d,
            ))
            stats.stj_descartados += 1

        indexer.registrar_fetch(conn, ref.fonte_key, "ok", itens_inseridos=s["inseridos"])
        logger.info(
            "STJ inf-%s: %d aceitos, %d descartados", ref.numero,
            len(julgados), len(resultado["descartados"]),
        )


# ===== TJ-SP =====

def _meses_da_janela(anos: list[int]) -> list[tuple[int, int]]:
    return [(ano, mes) for ano in sorted(anos) for mes in range(1, 13)]


def _periodo_do_mes(ano: int, mes: int) -> tuple[_dt.date, _dt.date]:
    primeiro = _dt.date(ano, mes, 1)
    _, ultimo_dia = monthrange(ano, mes)
    ultimo = _dt.date(ano, mes, ultimo_dia)
    return primeiro, ultimo


def _processar_tjsp(
    conn,
    anos: list[int],
    areas: list[str],
    anthropic_cli,
    stats: Stats,
    *,
    session_factory: Optional["feeds_tjsp.SessionFactory"] = None,
    http_post: Optional["feeds_tjsp.HttpPostFn"] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Itera (area, ano, mes) buscando acordaos via cjsg.

    Aceita session_factory (preferido, mantem sessao httpx.Client com
    cookies) ou http_post legacy (compat com testes antigos).
    """
    for ano, mes in _meses_da_janela(anos):
        for area in areas:
            fonte_key = feeds_tjsp.fonte_key(area, ano, mes)
            if indexer.fetch_ja_feito(conn, fonte_key):
                continue
            inicio, fim = _periodo_do_mes(ano, mes)
            try:
                acordaos = feeds_tjsp.buscar_acordaos(
                    area, inicio, fim,
                    session_factory=session_factory,
                    http_post=http_post,
                    sleep_fn=sleep_fn,
                )
            except Exception as exc:  # noqa: BLE001
                indexer.registrar_fetch(conn, fonte_key, "erro", erro=str(exc))
                stats.tjsp_erros += 1
                continue

            julgados: list[Julgado] = []
            descartados_local: list[dict] = []

            for a in acordaos:
                # area ja vem inferida pelo termo de busca (que foi escolhido por area).
                # mas pra honestidade, podemos confirmar via IA — opcional. Por padrao
                # confiamos no termo (economiza tokens).
                area_final = area
                if not a.ementa or len(a.ementa) < 50:
                    descartados_local.append({
                        "motivo": "ementa_curta",
                        "processo_id": a.processo_id,
                    })
                    continue

                tese = (a.ementa or "")[:280]
                julgados.append(Julgado(
                    tribunal=TRIBUNAL_TJSP,
                    processo_id=a.processo_id,
                    relator=a.relator,
                    orgao=a.orgao,
                    data_julgamento=a.data_julgamento,
                    data_publicacao=a.data_publicacao,
                    area=area_final,
                    classe=a.classe,
                    tese=tese,
                    ementa=a.ementa,
                    url_fonte=a.url_inteiro_teor,
                    info_origem=fonte_key,
                    indexado_em=agora_iso(),
                ))

            s = indexer.indexar_batch(conn, julgados)
            stats.tjsp_inseridos += s["inseridos"]
            stats.tjsp_atualizados += s["atualizados"]
            for d in descartados_local:
                indexer.registrar_descartado(conn, Descartado(
                    tribunal=TRIBUNAL_TJSP,
                    processo_id=d.get("processo_id", ""),
                    motivo=d.get("motivo", "desconhecido"),
                    payload=d,
                ))
                stats.tjsp_descartados += 1

            indexer.registrar_fetch(
                conn, fonte_key, "ok", itens_inseridos=s["inseridos"],
            )
            logger.info(
                "TJ-SP %s %d-%02d: %d aceitos", area, ano, mes, len(julgados),
            )


# ===== Orquestrador principal =====

def executar_backfill(
    cfg: Config,
    *,
    janela: int = JANELA_ANOS_DEFAULT,
    fontes: Iterable[str] = ("stj", "tjsp"),
    areas: Optional[Iterable[str]] = None,
    anthropic_cli=None,
    playwright_factory=None,
    session_factory: Optional["feeds_tjsp.SessionFactory"] = None,
    http_post: Optional["feeds_tjsp.HttpPostFn"] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Stats:
    """Backfill ponta-a-ponta. Devolve Stats com contagens + duracao."""
    stats = Stats(inicio=time.monotonic())
    hoje = _dt.date.today()
    anos = list(range(hoje.year - janela + 1, hoje.year + 1))
    areas_lista = list(areas) if areas else list(AREAS_ALVO)

    cache_dir = cfg.state_dir / "julgado_radar_cache" / "stj"
    cache_dir.mkdir(parents=True, exist_ok=True)

    conn = db.abrir(cfg.state_dir)
    try:
        if "stj" in fontes:
            if anthropic_cli is None:
                logger.warning("STJ pulado: sem anthropic_cli")
            else:
                _processar_stj(
                    conn, anos, cache_dir, anthropic_cli, stats,
                    playwright_factory=playwright_factory, sleep_fn=sleep_fn,
                )

        if "tjsp" in fontes:
            _processar_tjsp(
                conn, anos, areas_lista, anthropic_cli, stats,
                session_factory=session_factory,
                http_post=http_post,
                sleep_fn=sleep_fn,
            )

        stats.por_area = indexer.contar_por_tribunal_area(conn)
    finally:
        conn.close()

    stats.fim = time.monotonic()
    return stats


# ===== CLI =====

def _construir_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Backfill do Radar de Julgados")
    p.add_argument(
        "--janela", type=int, default=JANELA_ANOS_DEFAULT,
        help=f"Janela de anos (default: {JANELA_ANOS_DEFAULT})",
    )
    p.add_argument(
        "--fontes", default="stj,tjsp",
        help="Fontes separadas por virgula (default: stj,tjsp)",
    )
    p.add_argument(
        "--areas", default=",".join(AREAS_ALVO),
        help=f"Areas separadas por virgula (default: {','.join(AREAS_ALVO)})",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Apenas imprime parametros, nao executa nada",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _construir_argparser().parse_args(argv)
    fontes = tuple(f.strip() for f in args.fontes.split(",") if f.strip())
    areas = tuple(a.strip() for a in args.areas.split(",") if a.strip())

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
    logger.info(
        "Backfill iniciando: janela=%d fontes=%s areas=%s",
        args.janela, fontes, areas,
    )

    if args.dry_run:
        print(f"DRY-RUN: janela={args.janela}, fontes={fontes}, areas={areas}")
        return 0

    cfg = load_config()

    # AnthropicClient real (gated por credencial — se sem chave, STJ e pulado)
    anthropic_cli = None
    if cfg.anthropic_pronto():
        try:
            from src.anthropic_client import AnthropicClient
            anthropic_cli = AnthropicClient(cfg.anthropic, cfg.templates_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Anthropic indisponivel: %s", exc)

    try:
        stats = executar_backfill(
            cfg, janela=args.janela, fontes=fontes, areas=areas,
            anthropic_cli=anthropic_cli,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Backfill falhou: %s\n%s", exc, traceback.format_exc())
        return 1

    print("\n===== Backfill concluido =====")
    print(f"Tempo total: {stats.duracao_seg:.1f}s")
    print(f"STJ:   inseridos={stats.stj_inseridos} atualizados={stats.stj_atualizados} "
          f"descartados={stats.stj_descartados} erros={stats.stj_erros}")
    print(f"TJ-SP: inseridos={stats.tjsp_inseridos} atualizados={stats.tjsp_atualizados} "
          f"descartados={stats.tjsp_descartados} erros={stats.tjsp_erros}")
    print("Por tribunal/area:")
    for (trib, area), n in sorted(stats.por_area.items()):
        print(f"  {trib:>6s} / {area:<14s}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
