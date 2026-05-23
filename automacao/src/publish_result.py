"""Resultado padronizado de uma tentativa de publicacao em um canal."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# valores de status
OK = "ok"
SIMULADO = "simulado"
PULADO = "pulado"
ERRO = "erro"


@dataclass
class PublishResult:
    canal: str
    ok: bool = False
    status: str = ERRO  # ok | simulado | pulado | erro
    url: str = ""
    ids: dict = field(default_factory=dict)
    motivo: str = ""  # explica 'pulado'
    erro: str = ""  # explica 'erro'

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def pulado(cls, canal: str, motivo: str) -> "PublishResult":
        return cls(canal=canal, ok=True, status=PULADO, motivo=motivo)

    @classmethod
    def simulado(cls, canal: str, peca_id: str) -> "PublishResult":
        return cls(
            canal=canal,
            ok=True,
            status=SIMULADO,
            url=f"https://dry-run.local/{canal}/{peca_id}",
        )

    @classmethod
    def sucesso(cls, canal: str, url: str, ids: dict | None = None) -> "PublishResult":
        return cls(canal=canal, ok=True, status=OK, url=url, ids=ids or {})

    @classmethod
    def falha(cls, canal: str, erro: str) -> "PublishResult":
        return cls(canal=canal, ok=False, status=ERRO, erro=erro)
