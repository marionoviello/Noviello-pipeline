"""Parser de Informativos STJ + acordaos TJ-SP.

STJ: cada PDF contem N itens (julgados destacados). Esta fonte:
1. Extrai texto bruto do PDF via pypdf.
2. Particiona em blocos (1 bloco por julgado destacado).
3. Para cada bloco, manda pro Anthropic com STJ_ITEM_SCHEMA pra classificar
   area e extrair campos estruturados.
4. Itens com area='fora' viram Descartado.

TJ-SP: input ja e o HTML da listagem cjsg (sem PDF). parser usa a ementa
extraida pelo feeds_tjsp.parse_cjsg_resultado e classifica area via IA.

Reusa AnthropicClient existente (mas com schema diferente).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from src.julgado_radar.config import AREA_FORA, AREAS_ALVO


class ParserError(Exception):
    pass


# Schema JSON para extracao de UM item de Informativo STJ.
STJ_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "relevante": {"type": "boolean"},
        "area": {
            "type": "string",
            "enum": list(AREAS_ALVO) + [AREA_FORA],
        },
        "processo_id": {"type": "string"},
        "relator": {"type": "string"},
        "orgao": {"type": "string"},
        "data_julgamento": {"type": "string"},
        "classe": {"type": "string"},
        "tese": {"type": "string"},
        "ementa": {"type": "string"},
        "citacao_voto": {"type": "string"},
        "fundamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fonte": {"type": "string"},
                    "texto": {"type": "string"},
                },
                "required": ["fonte", "texto"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["relevante", "area", "processo_id", "tese"],
    "additionalProperties": False,
}


# Regex pra particionar texto de informativo STJ em itens.
# Os itens tipicamente comecam com cabecalho "PROCESSO" ou similar.
# Conservador: divide por marcadores comuns; quem chamar valida o resultado.
_RE_DIVISOR_ITEM = re.compile(
    r"(?=^\s*(?:PROCESSO|RECURSO\s+ESPECIAL|HABEAS\s+CORPUS|"
    r"AGRAVO|AGRAVO\s+REGIMENTAL|EMBARGOS|MANDADO|"
    r"REsp\s+\d|HC\s+\d|AgInt|EREsp))",
    re.MULTILINE | re.IGNORECASE,
)


def particionar_itens(texto_pdf: str) -> list[str]:
    """Divide o texto bruto do informativo em blocos (1 por julgado destacado).

    Heuristica simples: divide quando encontra cabecalho de processo no inicio
    de linha. Devolve lista de blocos NAO-vazios com >= 200 chars (filtra ruido
    de header/footer do PDF).
    """
    if not texto_pdf or not texto_pdf.strip():
        return []
    partes = _RE_DIVISOR_ITEM.split(texto_pdf)
    # Primeiro elemento de split com lookahead pode ser preambulo — filtra.
    blocos = [p.strip() for p in partes if p and p.strip()]
    return [b for b in blocos if len(b) >= 200]


def _ler_pdf(pdf_path: Path) -> str:
    """Extrai texto bruto via pypdf — wrapper local pra facilitar mock."""
    from pypdf import PdfReader  # noqa: PLC0415
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        raise ParserError(f"falha ao abrir PDF {pdf_path}: {exc}") from exc
    partes: list[str] = []
    for pagina in reader.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            raise ParserError(f"falha ao extrair pagina: {exc}") from exc
    return "\n".join(partes).strip()


def extrair_item_via_ia(bloco_texto: str, anthropic_cli) -> dict:
    """Manda 1 bloco pro AnthropicClient classificar + extrair campos.

    Reusa o metodo de extrair_dados_julgado do AnthropicClient se possivel,
    mas como o schema e diferente, chamamos via metodo dedicado (definido
    no AnthropicClient como `extrair_item_stj` — adicionado em parser_ai.py).

    Aqui assumimos que `anthropic_cli` tem o metodo `extrair_item_stj`.
    Sem rede em testes (mock do anthropic_cli).
    """
    return anthropic_cli.extrair_item_stj(bloco_texto, STJ_ITEM_SCHEMA)


def extrair_itens_de_informativo(
    pdf_path: Path,
    anthropic_cli,
    *,
    ler_pdf=None,
) -> dict:
    """Le PDF de informativo do STJ e devolve {'aceitos': [...], 'descartados': [...]}.

    aceitos: itens com area em AREAS_ALVO + campos required preenchidos
    descartados: itens com area='fora' ou sem campos required (motivo registrado)
    """
    leitor = ler_pdf if ler_pdf is not None else _ler_pdf
    texto = leitor(Path(pdf_path))
    blocos = particionar_itens(texto)

    aceitos: list[dict] = []
    descartados: list[dict] = []

    for bloco in blocos:
        try:
            item = extrair_item_via_ia(bloco, anthropic_cli)
        except Exception as exc:  # noqa: BLE001
            descartados.append({
                "motivo": "ia_falhou",
                "trecho": bloco[:300],
                "erro": str(exc),
            })
            continue

        # validacao basica
        area = (item.get("area") or "").lower()
        processo_id = (item.get("processo_id") or "").strip()
        tese = (item.get("tese") or "").strip()

        if not processo_id or not tese:
            descartados.append({
                "motivo": "sem_campos_obrigatorios",
                "item": item,
            })
            continue

        if area not in AREAS_ALVO:
            descartados.append({
                "motivo": "area_fora_escopo",
                "item": item,
            })
            continue

        aceitos.append(item)

    return {"aceitos": aceitos, "descartados": descartados}


# ===== TJ-SP — Parse de resultado da pesquisa cjsg =====
# Diferente do STJ: nao usa PDF, usa o JSON/dict que feeds_tjsp.parse_cjsg
# ja devolve. Aqui so classificamos a area via IA quando o termo da pesquisa
# nao foi suficiente pra confirmar.

def classificar_area_via_ia(ementa: str, anthropic_cli) -> str:
    """Pede pro Anthropic classificar a area do julgado (1 chamada curta).

    Devolve uma das AREAS_ALVO ou AREA_FORA. Sem rede em testes.
    """
    return anthropic_cli.classificar_area(ementa, list(AREAS_ALVO) + [AREA_FORA])
