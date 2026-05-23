"""Health endpoint — coleta status de cada componente para o painel + monitoring externo.

`status_geral(cfg)` devolve dict serializavel com:
- componentes: heartbeat + idade + thresholds
- circuit: status de cada canal (pausado/ativo)
- pecas: contagens por estado
- cadencia: ultimo run + total promovidos
- alertas: ultimos N alertas disparados

Expectativa de cadencia (intervalos em segundos), pra inferir saude:
- watcher:  1 min → alerta se > 5 min
- poller:   1 min → alerta se > 5 min
- producer: 2 min → alerta se > 10 min
- cadencia: 4 h   → alerta se > 8 h
- painel:   sempre vivo (persistente) → alerta se > 10 min
"""

from __future__ import annotations

from pathlib import Path

from src import heartbeat
from src.cadencia_state import CadenciaState
from src.circuit import _load as _circuit_load, canal_pausado
from src.producer_state import EstadoProd, ProducaoStore
from src.state import Estado, StateStore

# (nome, idade_max_segundos_ok, idade_max_segundos_warn)
LIMITES = {
    "watcher":  (300,   600),   # 5 min ok, 10 min warn
    "poller":   (300,   600),
    "producer": (600,   1200),  # 10 min ok, 20 min warn
    "cadencia": (28800, 57600), # 8h ok, 16h warn (intervalo 4h)
    "painel":   (600,   1800),  # 10 min ok, 30 min warn
}


def _status_componente(state_dir: Path, nome: str) -> dict:
    iso = heartbeat.ler(state_dir, nome)
    idade = heartbeat.idade_segundos(iso)
    ok_thr, warn_thr = LIMITES.get(nome, (600, 1800))
    if idade == float("inf"):
        status = "nunca_rodou"
    elif idade < ok_thr:
        status = "ok"
    elif idade < warn_thr:
        status = "atrasado"
    else:
        status = "parado"
    return {
        "ultimo_iso": iso or "",
        "idade_segundos": None if idade == float("inf") else round(idade, 1),
        "limite_ok_s": ok_thr,
        "status": status,
    }


def _status_pecas(cfg) -> dict:
    prod = ProducaoStore(cfg.state_dir).list_all()
    pec = StateStore(cfg.state_dir).list_all()
    return {
        "producao_aguardando_revisao": sum(
            1 for p in prod if p.status == EstadoProd.AGUARDANDO_REVISAO_COPY
        ),
        "producao_em_erro": sum(1 for p in prod if p.status == EstadoProd.ERRO),
        "pecas_aguardando_aprovacao": sum(
            1 for p in pec if p.status == Estado.AGUARDANDO_APROVACAO
        ),
        "pecas_publicando": sum(1 for p in pec if p.status == Estado.PUBLICANDO),
        "pecas_em_erro": sum(1 for p in pec if p.status == Estado.ERRO),
    }


def _status_circuit(cfg) -> dict:
    canais = ("instagram", "linkedin", "wordpress")
    out = {}
    try:
        dados = _circuit_load(cfg.state_dir)
    except Exception:  # noqa: BLE001
        dados = {}
    for c in canais:
        info = dados.get(c, {}) if isinstance(dados, dict) else {}
        try:
            pausado = canal_pausado(cfg.state_dir, c)
        except Exception:  # noqa: BLE001
            pausado = False
        out[c] = {
            "pausado": pausado,
            "falhas_consecutivas": info.get("falhas_consecutivas", 0),
            "ultima_falha_iso": info.get("ultima_falha_iso", ""),
        }
    return out


def _status_cadencia_short(cfg) -> dict:
    state = CadenciaState.carregar(cfg.state_dir)
    return {
        "ativa_env": cfg.cadencia_ativa,
        "ativa_painel": state.ativa,
        "ultimo_run": state.ultimo_run_iso or "",
        "total_promovidos": len(state.eventos_promovidos or {}),
    }


def status_geral(cfg) -> dict:
    """Snapshot completo da saude do sistema."""
    componentes = {
        nome: _status_componente(cfg.state_dir, nome)
        for nome in ("watcher", "poller", "producer", "cadencia", "painel")
    }
    # 'ok' geral: todos componentes em status 'ok' OU 'nunca_rodou' (1a execucao)
    saudavel = all(
        c["status"] in ("ok", "nunca_rodou")
        for c in componentes.values()
    )
    return {
        "ok": saudavel,
        "componentes": componentes,
        "pecas": _status_pecas(cfg),
        "circuit": _status_circuit(cfg),
        "cadencia": _status_cadencia_short(cfg),
    }
