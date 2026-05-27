"""Persistencia de estado da ponte de producao — um arquivo por artigo.

Arquivos em state/producao/<post_id>.json. A chave de idempotencia e o post_id
do WordPress: artigo com state nao e reprocessado.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.state import _file_lock, agora_iso


class EstadoProd:
    DETECTADO = "detectado"
    AGUARDANDO_REVISAO_COPY = "aguardando_revisao_copy"
    COPY_APROVADA = "copy_aprovada"
    PECA_MONTADA = "peca_montada"
    ERRO = "erro"


_TRANSICOES: dict[str, set[str]] = {
    EstadoProd.DETECTADO: {EstadoProd.AGUARDANDO_REVISAO_COPY, EstadoProd.ERRO},
    EstadoProd.AGUARDANDO_REVISAO_COPY: {EstadoProd.COPY_APROVADA, EstadoProd.ERRO},
    EstadoProd.COPY_APROVADA: {EstadoProd.PECA_MONTADA, EstadoProd.ERRO},
    EstadoProd.ERRO: {EstadoProd.AGUARDANDO_REVISAO_COPY, EstadoProd.COPY_APROVADA},
    EstadoProd.PECA_MONTADA: set(),
}


class TransicaoInvalida(Exception):
    pass


@dataclass
class ProducaoState:
    post_id: str
    status: str = EstadoProd.DETECTADO
    slug: str = ""
    titulo: str = ""
    thread_revisao_id: str = ""
    message_id: str = ""
    nossos_msg_ids: list = field(default_factory=list)
    artigo_texto: str = ""  # texto limpo do artigo (para regeneracao em ajustes)
    # slugs das categorias WP do artigo (resolve as skills de area na regeneracao)
    categorias_slugs: list = field(default_factory=list)
    # enriquecimento para o styler (nomes legiveis, imagem destacada original)
    categorias_nomes: list = field(default_factory=list)
    tags_nomes: list = field(default_factory=list)
    imagem_destaque_url: str = ""
    featured_media_id: int = 0
    # decisao registrada pelo painel: "" | "aprovar" | "ajustar"
    decisao: str = ""
    ajuste_texto: str = ""
    copy_carrossel: dict = field(default_factory=dict)  # {slides, legenda, hashtags}
    texto_linkedin: str = ""
    html_estilizado: str = ""
    # auditoria AI-tells por canal (preenchido na geracao):
    # {"carrossel": {forensic: N, strict: N, aesthetic: N, codigos: [...]},
    #  "linkedin":  {...}}
    ai_tells_resumo: dict = field(default_factory=dict)
    # Processos detectados no texto do artigo (cross-format anti-duplicata).
    # Cada item: {"texto_match", "classe", "numero", "uf", "chave_registry"}
    processos_mencionados: list = field(default_factory=list)
    # Lista de processos que JÁ FORAM publicados (presentes no registry).
    # Permite o painel mostrar warning antes de Mario aprovar.
    processos_ja_publicados: list = field(default_factory=list)
    tentativas_ajuste: int = 0
    atualizado_em: str = field(default_factory=agora_iso)
    historico: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "ProducaoState":
        campos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in dados.items() if k in campos})


def transition(peca: ProducaoState, novo_estado: str) -> None:
    permitidos = _TRANSICOES.get(peca.status, set())
    if novo_estado not in permitidos:
        raise TransicaoInvalida(
            f"transicao invalida: {peca.status} -> {novo_estado} "
            f"(permitidos: {sorted(permitidos)})"
        )
    peca.historico.append({"de": peca.status, "para": novo_estado, "em": agora_iso()})
    peca.status = novo_estado
    peca.atualizado_em = agora_iso()


class ProducaoStore:
    """CRUD de arquivos de estado em state/producao/."""

    def __init__(self, state_dir: Path):
        self.dir = Path(state_dir) / "producao"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, post_id) -> Path:
        return self.dir / f"{post_id}.json"

    def exists(self, post_id) -> bool:
        return self._path(post_id).exists()

    def load(self, post_id) -> ProducaoState:
        dados = json.loads(self._path(post_id).read_text(encoding="utf-8"))
        return ProducaoState.from_dict(dados)

    def save(self, peca: ProducaoState) -> None:
        peca.atualizado_em = agora_iso()
        tmp = self._path(peca.post_id).with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(peca.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path(peca.post_id))

    def delete(self, post_id) -> None:
        self._path(post_id).unlink(missing_ok=True)

    def list_all(self) -> list[ProducaoState]:
        pecas = []
        for arquivo in sorted(self.dir.glob("*.json")):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
                pecas.append(ProducaoState.from_dict(dados))
            except (json.JSONDecodeError, TypeError):
                continue
        return pecas

    def lock(self, post_id):
        """Lock exclusivo nao-bloqueante deste artigo (context manager).

        Mesma semantica de StateStore.lock. Levanta LockBusy se ocupado.
        """
        return _file_lock(self.dir / f"{post_id}.lock")
