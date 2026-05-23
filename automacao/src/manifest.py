"""Leitura e validacao do MANIFEST.json de uma peca (stage 01).

O MANIFEST.json e produzido pelas skills do ecossistema (fora deste pipeline).
Contrato: ver io_contracts.MANIFEST_da_peca em workflow-aprovacao-publicacao-v2-email.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CANAIS = ("instagram", "linkedin", "wordpress")


class ValidacaoError(Exception):
    """MANIFEST presente mas reprovado na validacao do stage 01."""


@dataclass
class Peca:
    peca_id: str
    manifest_path: Path
    manifest_dir: Path
    dados: dict

    @property
    def tipo(self) -> str:
        return self.dados.get("tipo", "")

    @property
    def pilar(self) -> str:
        return self.dados.get("pilar", "")

    @property
    def titulo_curto(self) -> str:
        return self.dados.get("titulo_curto", "")

    @property
    def data_publicacao_alvo(self) -> str:
        return self.dados.get("data_publicacao_alvo", "")

    def ativos(self, canal: str) -> dict | None:
        return self.dados.get("ativos", {}).get(canal)

    def canais_no_manifest(self) -> list[str]:
        return [c for c in CANAIS if self.dados.get("ativos", {}).get(c)]

    def cross_link(self) -> dict:
        return self.dados.get("cross_link", {})


def _paths_de_ativos(dados: dict):
    """Gera (rotulo, path_str) de todo campo que aponta para um arquivo local."""
    ativos = dados.get("ativos", {})

    ig = ativos.get("instagram") or {}
    for i, img in enumerate(ig.get("imagens", []) or []):
        yield (f"instagram.imagens[{i}]", img)
    if ig.get("legenda"):
        yield ("instagram.legenda", ig["legenda"])

    li = ativos.get("linkedin") or {}
    if li.get("imagem"):
        yield ("linkedin.imagem", li["imagem"])
    if li.get("texto"):
        yield ("linkedin.texto", li["texto"])

    wp = ativos.get("wordpress") or {}
    if wp.get("conteudo_html"):
        yield ("wordpress.conteudo_html", wp["conteudo_html"])
    if wp.get("imagem_destaque"):
        yield ("wordpress.imagem_destaque", wp["imagem_destaque"])


def carregar_manifest(path: Path) -> Peca:
    """Le e parseia o MANIFEST.json sem validar regras de negocio."""
    path = Path(path)
    dados = json.loads(path.read_text(encoding="utf-8"))
    peca_id = dados.get("peca_id")
    if not peca_id:
        raise ValidacaoError(f"{path}: MANIFEST sem peca_id")
    return Peca(
        peca_id=peca_id,
        manifest_path=path,
        manifest_dir=path.parent,
        dados=dados,
    )


def validate_manifest(path: Path) -> Peca:
    """Stage 01: carrega o MANIFEST e aplica as regras de validacao.

    Levanta ValidacaoError se a peca nao estiver pronta para aprovacao.
    """
    peca = carregar_manifest(path)
    dados = peca.dados

    status = dados.get("status")
    if status != "pronta_para_aprovacao":
        raise ValidacaoError(
            f"{peca.peca_id}: status='{status}', esperado 'pronta_para_aprovacao'"
        )

    val = dados.get("validacoes", {})
    if val.get("oab_205") != "aprovado":
        raise ValidacaoError(
            f"{peca.peca_id}: validacoes.oab_205='{val.get('oab_205')}', "
            "esperado 'aprovado' (Provimento OAB 205/2021)"
        )
    if val.get("marca") != "v2-conforme":
        raise ValidacaoError(
            f"{peca.peca_id}: validacoes.marca='{val.get('marca')}', esperado 'v2-conforme'"
        )

    if not peca.canais_no_manifest():
        raise ValidacaoError(f"{peca.peca_id}: nenhum canal em 'ativos'")

    faltando = []
    for rotulo, path_str in _paths_de_ativos(dados):
        if not Path(path_str).exists():
            faltando.append(f"{rotulo}: {path_str}")
    if faltando:
        raise ValidacaoError(
            f"{peca.peca_id}: assets ausentes no disco:\n  " + "\n  ".join(faltando)
        )

    return peca
