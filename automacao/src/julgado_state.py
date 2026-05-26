"""Persistencia de estado do Julgado da Semana — um arquivo por evento do calendario.

Arquivos em state/julgados/<event_id_safe>.json. Chave de idempotencia e o event.id
do Google Calendar (sanitizado para nomes de arquivo validos).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.state import _file_lock, agora_iso


class EstadoJulgado:
    DETECTADO = "detectado"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    APROVADO = "aprovado"
    PECA_MONTADA = "peca_montada"
    ERRO = "erro"


_TRANSICOES: dict[str, set[str]] = {
    EstadoJulgado.DETECTADO: {EstadoJulgado.AGUARDANDO_REVISAO, EstadoJulgado.ERRO},
    EstadoJulgado.AGUARDANDO_REVISAO: {EstadoJulgado.APROVADO, EstadoJulgado.ERRO},
    EstadoJulgado.APROVADO: {EstadoJulgado.PECA_MONTADA, EstadoJulgado.ERRO},
    EstadoJulgado.ERRO: {EstadoJulgado.AGUARDANDO_REVISAO, EstadoJulgado.APROVADO},
    EstadoJulgado.PECA_MONTADA: set(),
}


class TransicaoInvalida(Exception):
    pass


@dataclass
class JulgadoState:
    event_id: str
    semana_iso: int = 0
    ano_iso: int = 0
    event_summary: str = ""
    event_start_iso: str = ""
    status: str = EstadoJulgado.DETECTADO
    pdf_path: str = ""
    dados_julgado: dict = field(default_factory=dict)
    copy_carrossel: dict = field(default_factory=dict)
    texto_linkedin: str = ""
    decisao: str = ""
    ajuste_texto: str = ""
    tentativas_ajuste: int = 0
    ai_tells_resumo: dict = field(default_factory=dict)
    erro_mensagem: str = ""
    atualizado_em: str = field(default_factory=agora_iso)
    historico: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "JulgadoState":
        campos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in dados.items() if k in campos})


def transition(estado: JulgadoState, novo_estado: str) -> None:
    permitidos = _TRANSICOES.get(estado.status, set())
    if novo_estado not in permitidos:
        raise TransicaoInvalida(
            f"transicao invalida: {estado.status} -> {novo_estado} "
            f"(permitidos: {sorted(permitidos)})"
        )
    estado.historico.append({"de": estado.status, "para": novo_estado, "em": agora_iso()})
    estado.status = novo_estado
    estado.atualizado_em = agora_iso()


_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_\-]")


def _safe_key(event_id: str) -> str:
    """Substitui qualquer char nao-alfanumerico/_/- por underscore."""
    return _SAFE_KEY_RE.sub("_", event_id)


class JulgadoStore:
    """CRUD de arquivos de estado em state/julgados/."""

    def __init__(self, state_dir: Path):
        self.dir = Path(state_dir) / "julgados"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, event_id: str) -> Path:
        return self.dir / f"{_safe_key(event_id)}.json"

    def exists(self, event_id: str) -> bool:
        return self._path(event_id).exists()

    def load(self, event_id: str) -> JulgadoState:
        dados = json.loads(self._path(event_id).read_text(encoding="utf-8"))
        return JulgadoState.from_dict(dados)

    def save(self, estado: JulgadoState) -> None:
        estado.atualizado_em = agora_iso()
        tmp = self._path(estado.event_id).with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(estado.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path(estado.event_id))

    def delete(self, event_id: str) -> None:
        self._path(event_id).unlink(missing_ok=True)

    def list_all(self) -> list[JulgadoState]:
        estados = []
        for arquivo in sorted(self.dir.glob("*.json")):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                estados.append(JulgadoState.from_dict(dados))
            except (json.JSONDecodeError, TypeError):
                continue
        return estados

    def lock(self, event_id: str):
        """Lock exclusivo nao-bloqueante (context manager). Levanta LockBusy se ocupado."""
        return _file_lock(self.dir / f"{_safe_key(event_id)}.lock")
