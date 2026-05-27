"""Dataclasses do Radar — Julgado e Descartado."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Julgado:
    """1 linha na tabela `julgados`. id e atribuido pelo SQLite."""

    tribunal: str                       # 'STJ' | 'TJ-SP'
    processo_id: str                    # 'REsp 2.215.421/SE'
    area: str                           # 'urbanistico' | 'imobiliario' | 'sucessorio'
    tese: str

    id: Optional[int] = None
    relator: str = ""
    orgao: str = ""                     # '3a Turma'
    data_julgamento: str = ""           # ISO date
    data_publicacao: str = ""
    classe: str = ""                    # 'Recurso Especial'
    ementa: str = ""
    citacao_voto: str = ""
    fundamentos: list[dict] = field(default_factory=list)  # [{fonte, texto}]
    url_fonte: str = ""
    pdf_local: str = ""
    info_origem: str = ""               # 'informativo-789-stj' | 'cjsg-2024-08-imobiliario'
    score_relevancia: int = 50
    usado_em_post: str = ""
    indexado_em: str = ""

    def to_row(self) -> dict:
        """Converte pra dict pronto pra SQL INSERT (fundamentos -> JSON)."""
        d = asdict(self)
        d["fundamentos_json"] = json.dumps(d.pop("fundamentos"), ensure_ascii=False)
        return d

    @classmethod
    def from_row(cls, row: dict) -> "Julgado":
        """Constroi Julgado a partir de uma linha SQL (fundamentos_json -> list)."""
        dados = dict(row)
        fund_json = dados.pop("fundamentos_json", "[]") or "[]"
        try:
            dados["fundamentos"] = json.loads(fund_json)
        except json.JSONDecodeError:
            dados["fundamentos"] = []
        return cls(**{k: v for k, v in dados.items() if k in cls.__dataclass_fields__})


@dataclass
class Descartado:
    """1 linha na tabela `descartados` — item fora do escopo, mantido pra auditoria."""

    tribunal: str
    processo_id: str
    motivo: str                          # 'area_fora_escopo' | 'sem_tese_extraida' | 'duplicata'

    id: Optional[int] = None
    payload: dict = field(default_factory=dict)
    descartado_em: str = ""

    def to_row(self) -> dict:
        d = asdict(self)
        d["payload_json"] = json.dumps(d.pop("payload"), ensure_ascii=False)
        return d
