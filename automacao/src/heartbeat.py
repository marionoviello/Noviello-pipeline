"""Heartbeat de componentes — cada script toca um arquivo ao rodar.

state/heartbeat/<nome>.txt contem o ISO timestamp da ultima execucao.
Health endpoint le esses arquivos para inferir se um componente esta vivo.

Uso (no inicio de cada script agendado):
    from src.heartbeat import bater
    bater(cfg.state_dir, "watcher")
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.state import agora_iso

NOMES_VALIDOS = {"watcher", "poller", "producer", "cadencia", "painel", "backup"}


def bater(state_dir: Path, nome: str) -> None:
    """Toca arquivo de heartbeat. Falha silenciosa (heartbeat nao deve quebrar nada)."""
    try:
        hb_dir = Path(state_dir) / "heartbeat"
        hb_dir.mkdir(parents=True, exist_ok=True)
        (hb_dir / f"{nome}.txt").write_text(agora_iso(), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def ler(state_dir: Path, nome: str) -> str | None:
    """Le o ISO do ultimo heartbeat. None se nunca rodou."""
    arq = Path(state_dir) / "heartbeat" / f"{nome}.txt"
    if not arq.exists():
        return None
    try:
        return arq.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def idade_segundos(iso: str | None) -> float:
    """Idade (em segundos) de um ISO timestamp. Inf se None ou invalido."""
    if not iso:
        return float("inf")
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        agora = datetime.now(timezone.utc)
        return (agora - dt).total_seconds()
    except (ValueError, TypeError):
        return float("inf")
