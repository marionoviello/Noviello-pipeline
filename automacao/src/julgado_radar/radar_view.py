"""Lógica da view /radar — buscar, materializar julgado na pasta da semana.

Funções puras (recebem conn + paths). O painel.py adiciona apenas as rotas
HTTP que delegam aqui — manter o painel.py mais magro possivel.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from src.julgado_radar import db, searcher
from src.julgado_radar.config import AREAS_ALVO, FONTES
from src.julgado_radar.models import Julgado


def buscar_para_view(
    state_dir: Path,
    termo: str = "",
    *,
    area: Optional[str] = None,
    tribunal: Optional[str] = None,
    ano: Optional[int] = None,
    classe: Optional[str] = None,
    limit: int = 30,
) -> dict:
    """Helper de alto nivel: abre conn, busca, devolve dict pronto pro template.

    Estrutura:
      {
        "filtros": {"termo": "...", "area": "...", "tribunal": "...", "ano": ..., "classe": "..."},
        "areas_validas": [...],
        "tribunais_validos": [...],
        "anos_validos": [...],
        "total": N,
        "resultados": [Julgado_dict, ...],
      }
    """
    conn = db.abrir(state_dir)
    try:
        resultados = searcher.buscar(
            conn, termo,
            area=area, tribunal=tribunal, ano=ano, classe=classe, limit=limit,
        )
        anos_validos = _anos_disponiveis(conn)
        return {
            "filtros": {
                "termo": termo, "area": area or "",
                "tribunal": tribunal or "", "ano": ano or "",
                "classe": classe or "",
            },
            "areas_validas": list(AREAS_ALVO),
            "tribunais_validos": ["STJ", "TJ-SP"],
            "anos_validos": anos_validos,
            "total": len(resultados),
            "resultados": [_julgado_to_view(j) for j in resultados],
        }
    finally:
        conn.close()


def _julgado_to_view(j: Julgado) -> dict:
    """Converte Julgado em dict pronto pro template (campos primitivos)."""
    return {
        "id": j.id,
        "tribunal": j.tribunal,
        "processo_id": j.processo_id,
        "relator": j.relator,
        "orgao": j.orgao,
        "data_julgamento": j.data_julgamento,
        "area": j.area,
        "classe": j.classe,
        "tese": j.tese,
        "ementa_resumida": (j.ementa or "")[:300] + ("..." if len(j.ementa or "") > 300 else ""),
        "url_fonte": j.url_fonte,
        "usado_em_post": j.usado_em_post,
    }


def _anos_disponiveis(conn) -> list[int]:
    """Devolve lista de anos distintos extraidos de data_julgamento (ISO ou DD/MM)."""
    anos: set[int] = set()
    cur = conn.execute("SELECT DISTINCT data_julgamento FROM julgados WHERE data_julgamento != ''")
    for row in cur.fetchall():
        d = row["data_julgamento"]
        # tenta ISO YYYY-MM-DD ou DD/MM/YYYY
        m = re.match(r"(\d{4})-\d{2}-\d{2}", d) or re.search(r"/(\d{4})$", d)
        if m:
            try:
                anos.add(int(m.group(1)))
            except ValueError:
                continue
    return sorted(anos, reverse=True)


# ===== "Usar este" — materializa julgado na pasta da semana ISO atual =====

def semana_iso_atual(hoje: Optional[_dt.date] = None) -> tuple[int, int]:
    """Devolve (ano_iso, semana_iso) de hoje (ou data injetada)."""
    d = hoje or _dt.date.today()
    ano, semana, _ = d.isocalendar()
    return ano, semana


def _slug_processo(processo_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", processo_id.lower()).strip("-") or "sem-processo"


def materializar_julgado(
    state_dir: Path,
    julgado_id: int,
    julgado_dir: Path,
    *,
    hoje: Optional[_dt.date] = None,
    baixar_pdf: Optional[Callable[[str, Path], Path]] = None,
) -> dict:
    """Cria `producao/julgados/sem-NN/` com PDF + JSON do julgado escolhido.

    - state_dir: onde fica o radar.db
    - julgado_id: id na tabela julgados
    - julgado_dir: cfg.julgado_dir (ex: producao/julgados)
    - hoje: data de referencia (default: today) — para testar
    - baixar_pdf: funcao opcional (url, destino_dir) -> Path. Se None e julgado
      tem `pdf_local` valido, copia esse. Se nao, gera um placeholder TXT.

    Devolve {pasta, pdf_path, json_path, semana_iso, ano_iso, julgado_id, ja_existia}.

    Levanta RadarViewError se julgado nao existe ou pasta ja tem PDF de outro
    julgado (caller decide o que fazer).
    """
    conn = db.abrir(state_dir)
    try:
        julgado = searcher.get_por_id(conn, julgado_id)
        if julgado is None:
            raise RadarViewError(f"julgado id={julgado_id} nao encontrado")

        ano_iso, semana_iso = semana_iso_atual(hoje)
        pasta = Path(julgado_dir) / f"sem-{semana_iso:02d}"
        pasta.mkdir(parents=True, exist_ok=True)

        slug = _slug_processo(julgado.processo_id)
        pdf_destino = pasta / f"{slug}.pdf"
        json_destino = pasta / f"{slug}.json"

        ja_existia = pdf_destino.exists()

        # 1) PDF: prioridade source (pdf_local > baixar_pdf > placeholder TXT no .pdf)
        if not pdf_destino.exists():
            pdf_origem = Path(julgado.pdf_local) if julgado.pdf_local else None
            if pdf_origem and pdf_origem.exists():
                shutil.copy(pdf_origem, pdf_destino)
            elif baixar_pdf is not None and julgado.url_fonte:
                baixado = baixar_pdf(julgado.url_fonte, pasta)
                if baixado != pdf_destino:
                    shutil.move(str(baixado), pdf_destino)
            else:
                # Placeholder com ementa/tese — producer julgado_parser le como
                # texto valido (pypdf falha em texto cru; producer trata erro
                # como sinal pro Mario revisar manualmente).
                pdf_destino.write_text(
                    _placeholder_pdf_texto(julgado), encoding="utf-8",
                )

        # 2) JSON com os campos ja extraidos
        json_destino.write_text(
            json.dumps({
                "julgado_id": julgado.id,
                "tribunal": julgado.tribunal,
                "processo_id": julgado.processo_id,
                "relator": julgado.relator,
                "orgao": julgado.orgao,
                "data_julgamento": julgado.data_julgamento,
                "area": julgado.area,
                "classe": julgado.classe,
                "tese": julgado.tese,
                "ementa": julgado.ementa,
                "citacao_voto": julgado.citacao_voto,
                "fundamentos": julgado.fundamentos,
                "url_fonte": julgado.url_fonte,
                "info_origem": julgado.info_origem,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 3) Marca julgado como usado
        conn.execute(
            "UPDATE julgados SET usado_em_post=? WHERE id=?",
            (f"radar-sem-{ano_iso}-S{semana_iso:02d}", julgado_id),
        )
        conn.commit()

        return {
            "pasta": str(pasta),
            "pdf_path": str(pdf_destino),
            "json_path": str(json_destino),
            "semana_iso": semana_iso,
            "ano_iso": ano_iso,
            "julgado_id": julgado_id,
            "ja_existia": ja_existia,
        }
    finally:
        conn.close()


def _placeholder_pdf_texto(j: Julgado) -> str:
    """Texto plain que serve de placeholder quando nao ha PDF disponivel."""
    linhas = [
        f"JULGADO: {j.tribunal} {j.processo_id}",
        f"Relator: {j.relator}",
        f"Orgao: {j.orgao}",
        f"Data: {j.data_julgamento}",
        f"Classe: {j.classe}",
        "",
        f"TESE: {j.tese}",
        "",
        "EMENTA:",
        j.ementa or "(nao disponivel — extracao a partir da pesquisa)",
        "",
        "CITACAO:",
        j.citacao_voto or "",
        "",
        "URL_FONTE: " + j.url_fonte,
    ]
    return "\n".join(linhas)


class RadarViewError(Exception):
    pass
