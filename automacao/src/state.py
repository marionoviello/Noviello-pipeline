"""Persistencia de estado por peca.

Cada peca tem um arquivo state/<peca_id>.json. O arquivo existe enquanto a peca esta
em andamento; e removido apos a publicacao bem-sucedida (o thread do Gmail e a pasta
_publicado/ passam a ser a fonte de verdade).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path


def agora_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


class LockBusy(Exception):
    """Levantada quando outro processo ja segura o lock desta peca.

    O caller deve PULAR (continue) o processamento desta peca nesta tick;
    a proxima tick tentara novamente.
    """


@contextmanager
def _file_lock(path: Path):
    """Lock exclusivo nao-bloqueante via OS.

    Windows: msvcrt.locking (per file handle). Unix: fcntl.flock.
    Em ambos, o OS libera o lock quando o file descriptor e fechado —
    mesmo apos crash do processo. Sem orphan locks.

    Levanta LockBusy se outro processo ja segura o lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o666)
    try:
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise LockBusy(str(path)) from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LockBusy(str(path)) from exc
        yield
    finally:
        # fechar o fd libera o lock em ambas as plataformas
        os.close(fd)


class Estado:
    DETECTADA = "detectada"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    APROVADA = "aprovada"
    PUBLICANDO = "publicando"
    PUBLICADA = "publicada"
    AGUARDANDO_AJUSTE = "aguardando_ajuste"
    AGUARDANDO_REAGENDAMENTO = "aguardando_reagendamento"
    TIMEOUT = "timeout"
    ERRO = "erro"


# transicoes permitidas: estado_atual -> {estados_destino}
_TRANSICOES: dict[str, set[str]] = {
    Estado.DETECTADA: {Estado.AGUARDANDO_APROVACAO, Estado.ERRO},
    Estado.AGUARDANDO_APROVACAO: {
        Estado.APROVADA,
        Estado.AGUARDANDO_AJUSTE,
        Estado.AGUARDANDO_REAGENDAMENTO,
        Estado.TIMEOUT,
        Estado.ERRO,
    },
    Estado.APROVADA: {Estado.PUBLICANDO, Estado.ERRO},
    Estado.PUBLICANDO: {Estado.PUBLICADA, Estado.ERRO},
    Estado.AGUARDANDO_REAGENDAMENTO: {Estado.AGUARDANDO_APROVACAO, Estado.ERRO},
    Estado.AGUARDANDO_AJUSTE: {Estado.AGUARDANDO_APROVACAO, Estado.ERRO},
    Estado.TIMEOUT: {Estado.AGUARDANDO_APROVACAO, Estado.ERRO},
    Estado.ERRO: {Estado.PUBLICANDO, Estado.AGUARDANDO_APROVACAO},
    Estado.PUBLICADA: set(),
}


class TransicaoInvalida(Exception):
    pass


@dataclass
class PecaState:
    peca_id: str
    status: str = Estado.DETECTADA
    manifest_path: str = ""
    message_id: str = ""
    thread_id: str = ""
    label_atual: str = ""
    messages_count: int = 0
    # ids das mensagens que o proprio pipeline enviou no thread; tudo que NAO esta
    # aqui e considerado uma resposta do Mario
    nossos_msg_ids: list = field(default_factory=list)
    enviado_em: str = ""
    followup_enviado: bool = False
    # decisao registrada pelo painel: "" | "aprovar" | "ajustar"
    decisao: str = ""
    ajuste_texto: str = ""
    canais_publicados: dict = field(default_factory=dict)
    proof: dict = field(default_factory=dict)
    atualizado_em: str = field(default_factory=agora_iso)
    historico: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "PecaState":
        campos = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dados.items() if k in campos})


def transition(peca: PecaState, novo_estado: str) -> None:
    """Muda o estado da peca validando a transicao. Levanta TransicaoInvalida."""
    permitidos = _TRANSICOES.get(peca.status, set())
    if novo_estado not in permitidos:
        raise TransicaoInvalida(
            f"transicao invalida: {peca.status} -> {novo_estado} "
            f"(permitidos: {sorted(permitidos)})"
        )
    peca.historico.append({"de": peca.status, "para": novo_estado, "em": agora_iso()})
    peca.status = novo_estado
    peca.atualizado_em = agora_iso()


class StateStore:
    """CRUD de arquivos de estado em state/."""

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, peca_id: str) -> Path:
        return self.state_dir / f"{peca_id}.json"

    def exists(self, peca_id: str) -> bool:
        return self._path(peca_id).exists()

    def load(self, peca_id: str) -> PecaState:
        dados = json.loads(self._path(peca_id).read_text(encoding="utf-8"))
        return PecaState.from_dict(dados)

    def save(self, peca: PecaState) -> None:
        peca.atualizado_em = agora_iso()
        tmp = self._path(peca.peca_id).with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(peca.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path(peca.peca_id))

    def delete(self, peca_id: str) -> None:
        self._path(peca_id).unlink(missing_ok=True)

    def list_all(self) -> list[PecaState]:
        pecas = []
        for arquivo in sorted(self.state_dir.glob("*.json")):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                pecas.append(PecaState.from_dict(dados))
            except (json.JSONDecodeError, TypeError):
                continue
        return pecas

    def lock(self, peca_id: str):
        """Lock exclusivo nao-bloqueante desta peca (context manager).

        Use no `with` para proteger leitura+modificacao+escrita do estado de
        execucao concorrente. Levanta LockBusy se outro processo ja segura.
        """
        return _file_lock(self.state_dir / f"{peca_id}.lock")
