"""Log estruturado em JSONL.

Cada execucao escreve em logs/<ano>-<mes>-publicacoes.jsonl e tambem ecoa em stdout
(util ao rodar os scripts a mao). Campos minimos por evento de stage:
timestamp, peca_id, stage, status, duracao_ms, erro.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import structlog


def logfile_do_mes(logs_dir: Path) -> Path:
    agora = _dt.datetime.now()
    return logs_dir / f"{agora.year}-{agora.month:02d}-publicacoes.jsonl"


class _Tee:
    """Escreve a mesma linha em varios streams (arquivo de log + stdout).

    Ignora streams None — sob pythonw.exe (sem console) sys.stdout e None.
    """

    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]

    def write(self, texto: str) -> None:
        for s in self._streams:
            s.write(texto)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()


def setup_logging(logs_dir: Path) -> Path:
    """Configura o structlog para escrever JSONL. Devolve o path do arquivo do mes."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    arquivo = logfile_do_mes(logs_dir)
    fh = open(arquivo, "a", encoding="utf-8")

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=_Tee(fh, sys.stdout)),
        cache_logger_on_first_use=False,
    )
    return arquivo


def get_logger(nome: str = "pipeline"):
    return structlog.get_logger(nome)


def log_stage(
    logger,
    peca_id: str,
    stage: str,
    status: str,
    duracao_ms: int | None = None,
    erro: str | None = None,
) -> None:
    """Emite um evento de stage no formato padronizado."""
    logger.info(
        "stage",
        peca_id=peca_id,
        stage=stage,
        status=status,
        duracao_ms=duracao_ms,
        erro=erro,
    )
