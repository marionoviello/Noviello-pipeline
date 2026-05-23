"""Estado da cadencia semanal automatica — promotor de backlog (Batch 5).

state/cadencia.json:
{
  "ativa": true,                              # toggle controlado pelo painel
  "ultimo_run_iso": "2026-05-23T08:00:00",
  "eventos_promovidos": {                     # idempotencia por event_id do Google
    "<google_event_id>": {
      "data_evento_iso": "...",
      "titulo_evento": "...",
      "post_id": 11750,
      "post_titulo": "...",
      "promovido_em_iso": "..."
    }
  }
}
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.state import agora_iso

ARQUIVO = "cadencia.json"


@dataclass
class PromocaoRegistro:
    data_evento_iso: str
    titulo_evento: str
    post_id: int
    post_titulo: str
    promovido_em_iso: str


@dataclass
class CadenciaState:
    """Estado persistido em state/cadencia.json."""

    ativa: bool = True
    ultimo_run_iso: str = ""
    # google_event_id -> PromocaoRegistro (serializado como dict)
    eventos_promovidos: dict = field(default_factory=dict)

    @classmethod
    def carregar(cls, state_dir: Path) -> "CadenciaState":
        arq = Path(state_dir) / ARQUIVO
        if not arq.exists():
            return cls()
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        campos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in dados.items() if k in campos})

    def salvar(self, state_dir: Path) -> None:
        arq = Path(state_dir) / ARQUIVO
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(arq)

    def evento_ja_promovido(self, event_id: str) -> bool:
        return event_id in self.eventos_promovidos

    def registrar_promocao(
        self,
        event_id: str,
        data_evento_iso: str,
        titulo_evento: str,
        post_id: int,
        post_titulo: str,
    ) -> None:
        self.eventos_promovidos[event_id] = asdict(
            PromocaoRegistro(
                data_evento_iso=data_evento_iso,
                titulo_evento=titulo_evento,
                post_id=post_id,
                post_titulo=post_titulo,
                promovido_em_iso=agora_iso(),
            )
        )

    def marcar_run(self) -> None:
        self.ultimo_run_iso = agora_iso()
