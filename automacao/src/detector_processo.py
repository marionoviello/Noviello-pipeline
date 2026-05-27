"""Detector de menções a processos em texto livre.

Usado pelo producer Blog pra escanear o conteúdo de um artigo da Fila Social
e identificar processos citados (REsp do STJ, RE do STF, Apelação do TJ-SP, etc).
Cada processo detectado vira uma chave de unicidade ``processo:<normalizado>``
que pode ser cruzada com o registry de publicações já feitas.

Caso de uso: Mario escreve no blog "Análise do REsp 2.215.421/SE". O producer
detecta a citação, consulta o registry. Se ``processo:resp-2215421-se`` já
existe (foi tema de Card Julgado da Semana, por exemplo), o painel mostra
warning "tema já coberto em <peça>".

Padrões cobertos:
- STJ: REsp, AREsp, HC, MS, RHC, MC, EREsp, AgRg/AgInt no <tipo>
- STF: RE, ARE, AI, HC, MS, MI, ADPF, ADI, ADO, ADC
- TJ/CNJ: padrão NNNNNNN-DD.AAAA.J.TR.OOOO (apelações, agravos, ações em geral)

Não tenta perfeição: erra pra menos (preferimos missar alguma citação obscura
a marcar uma referência genérica como processo). Testes cobrem ementas reais
do STJ/TJ-SP pra calibrar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessoDetectado:
    """Um processo identificado em texto livre."""

    texto_match: str  # texto original capturado ("REsp 2.215.421/SE")
    classe: str  # 'REsp', 'RE', 'CNJ', etc.
    numero: str  # número canônico ("2215421" ou padrão CNJ completo)
    uf: str = ""  # UF opcional (STJ)


# Padrões STJ (mais comuns na nossa prática Imobiliário/Sucessório)
_CLASSES_STJ = (
    r"REsp|RE\.\s?Esp|R\.\s?Esp"
    r"|AREsp|EREsp|AgRg(?:\s+em)?(?:\s+(?:no|na))?\s+REsp"
    r"|AgInt(?:\s+em)?(?:\s+(?:no|na))?\s+(?:REsp|AREsp)"
    r"|EDcl\s+(?:em|no)\s+(?:REsp|AREsp)"
    r"|HC|RHC|MC|MS|RMS|MI|RR"
)
_PADRAO_STJ = re.compile(
    rf"\b(?P<classe>{_CLASSES_STJ})\s*"
    r"(?:n[º°.]\s*)?"
    r"(?P<numero>\d{1,3}(?:\.\d{3})*(?:\.\d{1,3})?)"  # 2.215.421 ou 123.456
    r"(?:\s*/\s*(?P<uf>[A-Z]{2}))?",  # /SE opcional
    re.IGNORECASE,
)

# Padrões STF
_CLASSES_STF = (
    r"RE|ARE|AI|ADPF|ADI|ADO|ADC|AC|MS|MI|HC|RHC|RCL"
)
_PADRAO_STF = re.compile(
    rf"\b(?P<classe>{_CLASSES_STF})\s*"
    r"(?:n[º°.]\s*)?"
    r"(?P<numero>\d{1,3}(?:\.\d{3})*)"
    r"(?:\s*/\s*(?P<uf>[A-Z]{2}))?",
    re.IGNORECASE,
)

# Padrão CNJ unificado (TJs em geral) — NNNNNNN-DD.AAAA.J.TR.OOOO
_PADRAO_CNJ = re.compile(
    r"\b(?P<numero>\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})\b"
)


# Falsos positivos comuns que devem ser excluídos:
# - "RE 1" / "MS 1" muito curtos (provavelmente abrevia outra coisa)
# - "REsp" sem número ("o REsp 2.215.421" ✓, "esse Resp foi tema" ✗)
_MIN_DIGITS = 4  # mínimo geral
# Classes de ação constitucional STF — numeração é sequencial baixa
# (ADPF 442 é real e relevante). Aceitamos 3+ dígitos.
_CLASSES_CURTAS = {"ADPF", "ADI", "ADO", "ADC", "MI"}
_MIN_DIGITS_CURTAS = 3


def _normalizar_numero(numero: str) -> str:
    """Remove separadores de milhar do número (.). Mantém hyphens do CNJ."""
    if "-" in numero or "/" in numero:
        # padrão CNJ: preserva
        return numero
    return numero.replace(".", "")


def detectar(texto: str) -> list[ProcessoDetectado]:
    """Detecta menções a processos em texto livre.

    Devolve lista única (dedup por (classe, numero_canon, uf)) na ordem
    de aparição no texto.
    """
    if not texto:
        return []
    encontrados: list[ProcessoDetectado] = []
    visto: set[tuple[str, str, str]] = set()

    # CNJ primeiro (mais específico, evita confusão com numeros curtos)
    for m in _PADRAO_CNJ.finditer(texto):
        num = m.group("numero")
        chave = ("CNJ", num, "")
        if chave in visto:
            continue
        visto.add(chave)
        encontrados.append(ProcessoDetectado(
            texto_match=m.group(0), classe="CNJ", numero=num,
        ))

    # STJ
    for m in _PADRAO_STJ.finditer(texto):
        classe = m.group("classe").upper().replace(" ", "").replace(".", "")
        # normaliza variações: REsp/R.Esp/RE.Esp → RESP
        classe = re.sub(r"R\s*ESP", "RESP", classe, flags=re.IGNORECASE)
        numero_raw = m.group("numero")
        numero = _normalizar_numero(numero_raw)
        if len(numero) < _MIN_DIGITS:
            continue
        uf = (m.group("uf") or "").upper()
        chave = (classe, numero, uf)
        if chave in visto:
            continue
        # também evita duplicata se o mesmo CNJ veio antes
        visto.add(chave)
        encontrados.append(ProcessoDetectado(
            texto_match=m.group(0), classe=classe, numero=numero, uf=uf,
        ))

    # STF (depois do STJ pra dar preferência ao mais específico se ambígua)
    for m in _PADRAO_STF.finditer(texto):
        classe = m.group("classe").upper().replace(".", "")
        numero_raw = m.group("numero")
        numero = _normalizar_numero(numero_raw)
        # classes constitucionais (ADPF/ADI/...) aceitam números curtos
        min_dig = _MIN_DIGITS_CURTAS if classe in _CLASSES_CURTAS else _MIN_DIGITS
        if len(numero) < min_dig:
            continue
        uf = (m.group("uf") or "").upper()
        chave = (classe, numero, uf)
        if chave in visto:
            continue
        visto.add(chave)
        encontrados.append(ProcessoDetectado(
            texto_match=m.group(0), classe=classe, numero=numero, uf=uf,
        ))

    return encontrados


def gerar_chaves_canonicas(detectados: list[ProcessoDetectado]) -> list[str]:
    """Converte ProcessoDetectado em chave canônica do registry de unicidade.

    Reusa ``publicacoes_unicas.normalizar_processo_id`` pra que a chave gerada
    aqui case com a chave gerada quando um Julgado da Semana é publicado.
    """
    from src.publicacoes_unicas import chave_processo
    chaves: list[str] = []
    visto: set[str] = set()
    for d in detectados:
        # reconstrói o texto canônico pra normalização consistente
        if d.classe == "CNJ":
            texto = d.numero  # padrão CNJ já é canônico
        else:
            texto = f"{d.classe} {d.numero}"
            if d.uf:
                texto += f"/{d.uf}"
        chave = chave_processo(texto)
        if chave and chave not in visto:
            visto.add(chave)
            chaves.append(chave)
    return chaves
