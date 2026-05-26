"""Parser do Julgado da Semana — recebe path de PDF, devolve dict estruturado.

Pipeline:
  localizar_pdf_da_semana(julgados_dir, semana_iso) -> Path
  parse_julgado(pdf_path, anthropic_cli)            -> dict com:
    {area, orgao, orgao_completo, turma, processo_id, data_julgamento,
     relator, relator_curto, tese, citacao_principal, carimbo, fundamentos}

Convencao da pasta: producao/julgados/sem-NN/<qualquer>.pdf (exatamente 1 PDF).
Falha rapida: pasta inexistente, sem PDF, multiplos PDFs, PDF corrompido,
texto vazio ou campos obrigatorios sem resposta da IA.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class JulgadoParserError(Exception):
    """Erro no pipeline de parsing do Julgado (localizacao, leitura ou IA)."""


# Campos que a IA DEVE devolver preenchidos.
_CAMPOS_OBRIGATORIOS = (
    "area",
    "orgao",
    "processo_id",
    "relator",
    "tese",
    "citacao_principal",
    "carimbo",
)


def localizar_pdf_da_semana(julgados_dir: Path, semana_iso: int) -> Path:
    """Devolve o caminho do unico PDF em `julgados_dir / 'sem-NN'`.

    Levanta JulgadoParserError se:
    - a pasta da semana nao existe
    - a pasta esta vazia (sem .pdf)
    - a pasta tem 2+ PDFs (ambiguidade)
    """
    pasta = Path(julgados_dir) / f"sem-{semana_iso:02d}"
    if not pasta.exists():
        raise JulgadoParserError(f"pasta da semana nao existe: {pasta}")
    pdfs = sorted(pasta.glob("*.pdf"))
    if not pdfs:
        raise JulgadoParserError(f"nenhum PDF em {pasta}")
    if len(pdfs) > 1:
        nomes = ", ".join(p.name for p in pdfs)
        raise JulgadoParserError(
            f"mais de um PDF em {pasta} (esperado 1): {nomes}"
        )
    return pdfs[0]


def _extrair_texto_pdf(pdf_path: Path) -> str:
    """Le texto bruto do PDF via pypdf (texto concatenado de todas as paginas).

    Levanta JulgadoParserError se o arquivo nao existe ou nao e um PDF valido.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise JulgadoParserError(f"arquivo nao existe: {pdf_path}")
    try:
        reader = PdfReader(str(pdf_path))
    except (PdfReadError, OSError, ValueError) as exc:
        raise JulgadoParserError(f"falha ao ler PDF {pdf_path}: {exc}") from exc

    partes: list[str] = []
    for pagina in reader.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 — pypdf levanta varios tipos
            raise JulgadoParserError(
                f"falha ao extrair texto em {pdf_path}: {exc}"
            ) from exc
    return "\n".join(partes).strip()


def parse_julgado(pdf_path: Path, anthropic_cli) -> dict:
    """Le o PDF do acordao e devolve dict estruturado com os campos do julgado.

    Pipeline: extrai texto via pypdf -> envia para Anthropic com structured
    output -> valida campos obrigatorios -> devolve dict.

    Levanta JulgadoParserError com mensagem clara em qualquer falha.
    """
    texto = _extrair_texto_pdf(pdf_path)
    if not texto.strip():
        raise JulgadoParserError(
            f"texto extraido do PDF esta vazio: {pdf_path} — extracao impossivel"
        )

    dados = anthropic_cli.extrair_dados_julgado(texto)

    faltando = [c for c in _CAMPOS_OBRIGATORIOS if not str(dados.get(c, "")).strip()]
    if faltando:
        raise JulgadoParserError(
            f"campo obrigatorio vazio: {', '.join(faltando)} — IA nao conseguiu "
            f"estruturar o PDF. Revise o PDF e tente de novo."
        )

    fundamentos = dados.get("fundamentos", [])
    if not isinstance(fundamentos, list) or len(fundamentos) == 0:
        raise JulgadoParserError(
            "fundamentos vazios — IA nao identificou base juridica. "
            "Verifique se o PDF e um acordao completo."
        )

    return dados
