"""Backup automatico de state/ + producao/ (Batch F3).

Empacota os diretorios criticos em tar.gz timestampado, mantem rotacao das N
ultimas copias e (opcional) sobe pra destino remoto se configurado.

Pre-requisitos de 24/7: sem backup automatico, qualquer falha de disco/VPS
significa perda total da fila de aprovacao + historico de cadencia + state
do circuit breaker.

Estrutura:
  ~/.noviello-backups/
    noviello-pipeline-2026-05-23T08-00-00.tar.gz
    noviello-pipeline-2026-05-22T08-00-00.tar.gz
    ...

Rodar:  .venv\\Scripts\\python.exe -m src.backup   (cwd = automacao/)
"""

from __future__ import annotations

import datetime as _dt
import os
import tarfile
from pathlib import Path

from src.config import load_config
from src.heartbeat import bater
from src.logger import get_logger, setup_logging

# diretorios a incluir no backup (relativos ao project_root)
INCLUI = [
    "automacao/state",         # cadencia, alertas, circuit, watcher, producer, painel
]

# diretorios a incluir do project_root (sao top-level)
INCLUI_TOP = [
    "producao",                # peças em andamento e _publicado/
]

# extensoes a EXCLUIR (cache, locks transitorios)
EXCLUI_EXT = {".lock", ".tmp", ".pyc"}

# diretorios a excluir
EXCLUI_DIR = {"__pycache__", ".pytest_cache"}


def _filtro_tar(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Filtra arquivos durante o tar (locks, cache, etc)."""
    nome = info.name.replace("\\", "/")
    for d in EXCLUI_DIR:
        if f"/{d}/" in f"/{nome}/":
            return None
    for ext in EXCLUI_EXT:
        if nome.endswith(ext):
            return None
    return info


def _destino_padrao() -> Path:
    """~/.noviello-backups (ou %USERPROFILE%\\.noviello-backups no Win)."""
    return Path.home() / ".noviello-backups"


def fazer_backup(cfg, destino: Path | None = None, logger=None) -> Path | None:
    """Empacota e devolve o Path do arquivo. None se nada foi empacotado."""
    if destino is None:
        env_dir = os.environ.get("NOVIELLO_BACKUP_DIR", "").strip()
        destino = Path(env_dir) if env_dir else _destino_padrao()
    destino.mkdir(parents=True, exist_ok=True)

    timestamp = _dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    nome_arq = f"noviello-pipeline-{timestamp}.tar.gz"
    arq = destino / nome_arq

    root = cfg.project_root
    incluidos = 0

    with tarfile.open(arq, "w:gz") as tar:
        for rel in INCLUI:
            p = root / rel
            if not p.exists():
                continue
            tar.add(p, arcname=rel, filter=_filtro_tar)
            incluidos += 1
        for rel in INCLUI_TOP:
            p = root / rel
            if not p.exists():
                continue
            tar.add(p, arcname=rel, filter=_filtro_tar)
            incluidos += 1

    if incluidos == 0:
        arq.unlink(missing_ok=True)
        if logger:
            logger.info("backup", status="nada_para_empacotar")
        return None

    tamanho = arq.stat().st_size
    if logger:
        logger.info("backup", status="ok",
                    arquivo=str(arq), tamanho=tamanho, incluidos=incluidos)
    return arq


def rotacionar(destino: Path | None = None, manter: int = 30, logger=None) -> int:
    """Apaga backups mais antigos, mantendo os `manter` mais recentes.

    Devolve quantos foram apagados.
    """
    if destino is None:
        env_dir = os.environ.get("NOVIELLO_BACKUP_DIR", "").strip()
        destino = Path(env_dir) if env_dir else _destino_padrao()
    if not destino.exists():
        return 0

    backups = sorted(
        destino.glob("noviello-pipeline-*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    a_apagar = backups[manter:]
    for p in a_apagar:
        try:
            p.unlink()
        except OSError:
            continue
    if logger and a_apagar:
        logger.info("backup", status="rotacao",
                    apagados=len(a_apagar), mantidos=min(len(backups), manter))
    return len(a_apagar)


def listar_backups(destino: Path | None = None) -> list[dict]:
    """Lista backups existentes (mais recente primeiro)."""
    if destino is None:
        env_dir = os.environ.get("NOVIELLO_BACKUP_DIR", "").strip()
        destino = Path(env_dir) if env_dir else _destino_padrao()
    if not destino.exists():
        return []
    out = []
    for p in sorted(destino.glob("noviello-pipeline-*.tar.gz"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({
            "nome": p.name,
            "caminho": str(p),
            "tamanho_bytes": st.st_size,
            "modificado_iso": _dt.datetime.fromtimestamp(st.st_mtime).isoformat(),
        })
    return out


def main() -> int:
    cfg = load_config()
    setup_logging(cfg.logs_dir)
    logger = get_logger("backup")
    bater(cfg.state_dir, "backup")

    arq = fazer_backup(cfg, logger=logger)
    if arq is None:
        logger.info("backup", status="vazio")
        return 0

    manter = int(os.environ.get("NOVIELLO_BACKUP_MANTER", "30") or "30")
    rotacionar(manter=manter, logger=logger)

    logger.info("backup", status="fim", arquivo=arq.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
