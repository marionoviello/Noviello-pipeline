"""Circuit breaker por canal — persiste em state/channel_health.json.

3 falhas consecutivas no mesmo canal => canal pausado por 1h.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

ARQUIVO = "channel_health.json"
LIMITE_FALHAS = 3
PAUSA_HORAS = 1


def _path(state_dir) -> Path:
    return Path(state_dir) / ARQUIVO


def _load(state_dir) -> dict:
    p = _path(state_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(state_dir, dados: dict) -> None:
    _path(state_dir).write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def canal_pausado(state_dir, canal: str, agora: _dt.datetime | None = None) -> bool:
    agora = agora or _dt.datetime.now().astimezone()
    info = _load(state_dir).get(canal, {})
    ate = info.get("pausado_ate")
    if not ate:
        return False
    try:
        return _dt.datetime.fromisoformat(ate) > agora
    except ValueError:
        return False


def registrar_sucesso(state_dir, canal: str) -> None:
    dados = _load(state_dir)
    dados[canal] = {"falhas_consecutivas": 0, "pausado_ate": None}
    _save(state_dir, dados)


def registrar_falha(state_dir, canal: str, agora: _dt.datetime | None = None) -> dict:
    agora = agora or _dt.datetime.now().astimezone()
    dados = _load(state_dir)
    info = dados.get(canal, {"falhas_consecutivas": 0, "pausado_ate": None})
    info["falhas_consecutivas"] = info.get("falhas_consecutivas", 0) + 1
    if info["falhas_consecutivas"] >= LIMITE_FALHAS:
        info["pausado_ate"] = (agora + _dt.timedelta(hours=PAUSA_HORAS)).isoformat()
    dados[canal] = info
    _save(state_dir, dados)
    return info
