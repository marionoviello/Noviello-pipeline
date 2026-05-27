"""Registry de publicações únicas — evita duplicatas cross-canal.

Mantém um índice em ``state/publicacoes_unicas.json`` indexado por uma chave
normalizada (processo STJ, ID de post WP, etc.) com metadados da primeira
publicação. Antes de processar um conteúdo novo, o producer consulta o registry;
após uma publicação bem-sucedida, o pipeline registra automaticamente.

Causa raiz que motivou o módulo (2026-05-27): o mesmo REsp 2.215.421/SE foi
publicado 2x em LinkedIn — uma manual via script standalone e outra via
producer Julgado. Sem memória de publicações, smoke tests podem republicar
conteúdo já no ar.

Chaves canônicas:
- ``processo:resp-2215421-se``     — Julgado da Semana (processo_id normalizado)
- ``wp:11748``                     — Post do blog (post_id do WP)
- ``manual:<slug-livre>``          — Publicações manuais não-rastreáveis por ID

Comportamento idempotente: ``registrar()`` em chave existente atualiza
``ultima_tentativa_iso`` e incrementa ``tentativas``, sem perder a publicação
original.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.state import agora_iso

ARQUIVO = "publicacoes_unicas.json"


@dataclass
class RegistroPublicacao:
    """Linha do registry — 1 conteúdo único já publicado pelo pipeline."""

    chave: str  # "processo:resp-2215421-se", "wp:11748", ...
    tipo: str  # "processo" | "wp_post" | "manual"
    primeira_publicacao_iso: str
    ultima_tentativa_iso: str
    peca_id: str = ""  # peca_id do MANIFEST original
    titulo: str = ""
    canais_publicados: list = field(default_factory=list)  # ["instagram", "linkedin"]
    urls: dict = field(default_factory=dict)  # {canal: url}
    tentativas: int = 1  # quantas vezes o pipeline tentou processar essa chave
    notas: str = ""


def normalizar_processo_id(processo_id: str) -> str:
    """Normaliza um ID de processo (STJ/STF/TJ) para chave estável.

    Estratégia: remove pontos em NÚMEROS contíguos (separadores de milhares
    do padrão STJ: '2.215.421' -> '2215421'), mas preserva pontos em
    NUMERAÇÃO CNJ ('1234567-89.2020.8.26.0100') trocando-os por hyphens.

    Exemplos:
        'REsp 2.215.421/SE'                -> 'resp-2215421-se'
        'AgRg no REsp 1.234.567/RJ'        -> 'agrg-no-resp-1234567-rj'
        'RE 1.000.000/SP'                  -> 're-1000000-sp'
        'Apel. 1234567-89.2020.8.26.0100'  -> 'apel-1234567-89-2020-8-26-0100'
    """
    if not processo_id:
        return ""
    # remove acentos
    nfkd = unicodedata.normalize("NFKD", processo_id)
    s = "".join(c for c in nfkd if not unicodedata.combining(c))
    s = s.lower()
    # remove pontos que separam dígitos de milhares (ex: 2.215.421 -> 2215421),
    # mas preserva pontos em padrão CNJ (digito.digito após hyphen).
    # Estratégia: colapsa "DIGITO.DIGITO.DIGITO" SEM hyphen anterior próximo.
    s = re.sub(r"(\d)\.(?=\d{3}(?:\D|$))", r"\1", s)
    # qualquer não-alfanumérico vira hyphen
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def chave_processo(processo_id: str) -> str:
    """Constrói a chave canônica para um processo (ex: REsp 2.215.421/SE)."""
    norm = normalizar_processo_id(processo_id)
    return f"processo:{norm}" if norm else ""


def chave_wp_post(post_id: int | str) -> str:
    """Constrói a chave canônica para um post do WordPress pelo ID."""
    s = str(post_id).strip()
    return f"wp:{s}" if s else ""


def chave_manual(slug: str) -> str:
    """Chave para publicações manuais não-rastreáveis automaticamente."""
    s = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    return f"manual:{s}" if s else ""


class RegistroStore:
    """CRUD do registry em state/publicacoes_unicas.json."""

    def __init__(self, state_dir: Path):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.arq = self.dir / ARQUIVO

    def _load(self) -> dict[str, dict]:
        if not self.arq.exists():
            return {}
        try:
            return json.loads(self.arq.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, dados: dict[str, dict]) -> None:
        tmp = self.arq.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.arq)

    def existe(self, chave: str) -> bool:
        """True se a chave já foi publicada com sucesso em algum canal."""
        if not chave:
            return False
        return chave in self._load()

    def obter(self, chave: str) -> RegistroPublicacao | None:
        dados = self._load()
        if chave not in dados:
            return None
        d = dados[chave]
        campos = set(RegistroPublicacao.__dataclass_fields__)
        return RegistroPublicacao(**{k: v for k, v in d.items() if k in campos})

    def registrar(
        self,
        chave: str,
        *,
        tipo: str,
        peca_id: str = "",
        titulo: str = "",
        canais_publicados: list | None = None,
        urls: dict | None = None,
        notas: str = "",
    ) -> RegistroPublicacao:
        """Registra (ou atualiza) uma publicação.

        Idempotente: se a chave já existe, incrementa ``tentativas`` e
        atualiza ``ultima_tentativa_iso`` SEM sobrescrever a primeira
        publicação. Os campos novos (canais, urls) são mergidos.
        """
        if not chave:
            raise ValueError("chave vazia — use chave_processo()/chave_wp_post()/chave_manual()")
        dados = self._load()
        agora = agora_iso()
        if chave in dados:
            existente = dados[chave]
            existente["ultima_tentativa_iso"] = agora
            existente["tentativas"] = int(existente.get("tentativas", 1)) + 1
            # merge canais e urls (preserva os antigos, adiciona novos)
            if canais_publicados:
                merged = list(dict.fromkeys((existente.get("canais_publicados") or []) + canais_publicados))
                existente["canais_publicados"] = merged
            if urls:
                existente.setdefault("urls", {}).update(urls)
            dados[chave] = existente
        else:
            reg = RegistroPublicacao(
                chave=chave,
                tipo=tipo,
                primeira_publicacao_iso=agora,
                ultima_tentativa_iso=agora,
                peca_id=peca_id,
                titulo=titulo,
                canais_publicados=canais_publicados or [],
                urls=urls or {},
                tentativas=1,
                notas=notas,
            )
            dados[chave] = asdict(reg)
        self._save(dados)
        return self.obter(chave)  # type: ignore[return-value]

    def remover(self, chave: str) -> bool:
        """Remove uma chave (uso administrativo, ex: pra refazer um post)."""
        dados = self._load()
        if chave not in dados:
            return False
        del dados[chave]
        self._save(dados)
        return True

    def listar(self) -> list[RegistroPublicacao]:
        out = []
        for d in self._load().values():
            campos = set(RegistroPublicacao.__dataclass_fields__)
            out.append(RegistroPublicacao(**{k: v for k, v in d.items() if k in campos}))
        return sorted(out, key=lambda r: r.primeira_publicacao_iso, reverse=True)
