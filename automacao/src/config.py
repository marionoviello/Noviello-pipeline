"""Configuracao central do pipeline de aprovacao/publicacao.

Carrega credenciais e parametros de comportamento. Prioridade de resolucao:
  1. valor NAO-vazio no arquivo .env (raiz do projeto)
  2. variavel de ambiente do Windows

Isso permite que o token Meta (criado por scripts/setup-meta-token.ps1 como env var
do Windows) coexista com credenciais Google/LinkedIn/WordPress vindas do .env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

# automacao/src/config.py  ->  automacao  ->  Noviello-Produtividade
AUTOMACAO_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = AUTOMACAO_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"


def _bool(valor: str) -> bool:
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _default_skills_dir() -> Path | None:
    """Descobre o diretorio do stash de skills `noviello-*` no AppData do Claude.

    Procura em locais conhecidos do plugin de skills do Claude no Windows.
    Retorna None se nao encontrar (producer cai no comportamento legado).
    """
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    base = Path(appdata) / "Claude" / "local-agent-mode-sessions" / "skills-plugin"
    if not base.exists():
        return None
    # Estrutura: skills-plugin/<uuid1>/<uuid2>/skills/<skill-name>/SKILL.md
    for sub1 in base.iterdir():
        if not sub1.is_dir():
            continue
        for sub2 in sub1.iterdir():
            if not sub2.is_dir():
                continue
            candidato = sub2 / "skills"
            if (candidato / "noviello-marketing-creator" / "SKILL.md").exists():
                return candidato
    return None


@dataclass
class Config:
    """Snapshot imutavel da configuracao resolvida."""

    # Paths
    project_root: Path
    automacao_dir: Path
    producao_dir: Path
    publicado_dir: Path
    state_dir: Path
    logs_dir: Path
    templates_dir: Path

    # Comportamento
    enabled_channels: list[str]
    dry_run: bool
    email_aprovador: str

    # Credenciais por integracao
    google: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    linkedin: dict = field(default_factory=dict)
    wordpress: dict = field(default_factory=dict)
    anthropic: dict = field(default_factory=dict)

    # Timeouts (horas)
    followup_horas: int = 12
    erro_horas: int = 24

    # Ponte de producao
    wp_categoria_fila_social: str = "Fila Social"

    # Diretorio das skills `noviello-*` (stash local) — se nao definido,
    # o producer roda com brief-marca.txt apenas (comportamento legado).
    skills_dir: Path | None = None

    # Cadencia semanal automatica (Batch 5)
    cadencia_ativa: bool = True  # kill switch via .env (override do estado do painel)
    cadencia_calendario: str = "Noviello — Marketing"
    cadencia_filtro_titulo: str = "[NOV-BLOG] Publicação WordPress"
    cadencia_janela_horas: int = 48
    wp_categoria_backlog: str = "Backlog Editorial"

    # Geracao de hero do artigo via Gemini (opt-in)
    auto_gerar_hero: bool = False
    google_ai_api_key: str = ""

    def channel_enabled(self, canal: str) -> bool:
        return canal in self.enabled_channels

    def google_pronto(self) -> bool:
        g = self.google
        return bool(g.get("client_id") and g.get("client_secret") and g.get("refresh_token"))

    def meta_pronto(self) -> bool:
        m = self.meta
        return bool(m.get("page_token") and m.get("ig_business_id"))

    def linkedin_pronto(self) -> bool:
        li = self.linkedin
        return bool(li.get("access_token") and li.get("person_urn"))

    def wordpress_pronto(self) -> bool:
        wp = self.wordpress
        return bool(wp.get("user") and (wp.get("app_password_noviello") or wp.get("app_password_imobiliario")))

    def anthropic_pronto(self) -> bool:
        return bool(self.anthropic.get("api_key"))


def _make_getter(env_path: Path):
    """Retorna funcao _get(key) com prioridade .env-nao-vazio > os.environ."""
    arquivo = dotenv_values(env_path) if env_path.exists() else {}

    def _get(key: str, default: str = "") -> str:
        valor = arquivo.get(key)
        if valor:  # nao-vazio
            return valor.strip()
        return os.environ.get(key, default).strip()

    return _get


def load_config() -> Config:
    """Le .env + env vars do Windows e devolve um Config resolvido."""
    _get = _make_getter(ENV_PATH)

    enabled_raw = _get("ENABLED_CHANNELS", "instagram")
    enabled = [c.strip().lower() for c in enabled_raw.split(",") if c.strip()]

    # paths configuraveis (uteis pra migrar pra VPS Linux ou Docker)
    state_dir = Path(_get("NOVIELLO_STATE_DIR")) if _get("NOVIELLO_STATE_DIR") else AUTOMACAO_DIR / "state"
    logs_dir = Path(_get("NOVIELLO_LOGS_DIR")) if _get("NOVIELLO_LOGS_DIR") else AUTOMACAO_DIR / "logs"
    producao_dir = Path(_get("NOVIELLO_PRODUCAO_DIR")) if _get("NOVIELLO_PRODUCAO_DIR") else PROJECT_ROOT / "producao"

    cfg = Config(
        project_root=PROJECT_ROOT,
        automacao_dir=AUTOMACAO_DIR,
        producao_dir=producao_dir,
        publicado_dir=producao_dir / "_publicado",
        state_dir=state_dir,
        logs_dir=logs_dir,
        templates_dir=AUTOMACAO_DIR / "templates",
        enabled_channels=enabled,
        dry_run=_bool(_get("DRY_RUN", "true")),
        email_aprovador=_get("EMAIL_APROVADOR", "mario@noviello.adv.br"),
        google={
            "client_id": _get("GMAIL_OAUTH_CLIENT_ID"),
            "client_secret": _get("GMAIL_OAUTH_CLIENT_SECRET"),
            "refresh_token": _get("GMAIL_OAUTH_REFRESH_TOKEN"),
            "calendar_id": _get("GOOGLE_CALENDAR_ID", "Noviello — Marketing"),
        },
        meta={
            "page_token": _get("META_PAGE_TOKEN"),
            # reconcilia nome do manifesto com nome legado do setup-meta-token.ps1
            "ig_business_id": _get("META_IG_BUSINESS_ID") or _get("IG_USER_ID_NOVIELLOADV"),
            "page_id": _get("META_PAGE_ID"),
        },
        linkedin={
            "access_token": _get("LI_ACCESS_TOKEN"),
            "refresh_token": _get("LI_REFRESH_TOKEN"),
            "person_urn": _get("LI_PERSON_URN"),
        },
        wordpress={
            "user": _get("WP_USER"),
            "app_password_noviello": _get("WP_APP_PASSWORD_NOVIELLO"),
            "app_password_imobiliario": _get("WP_APP_PASSWORD_IMOBILIARIO"),
        },
        anthropic={
            "api_key": _get("ANTHROPIC_API_KEY"),
            "model": _get("ANTHROPIC_MODEL", "claude-opus-4-7"),
        },
        wp_categoria_fila_social=_get("WP_CATEGORIA_FILA_SOCIAL", "Fila Social"),
        skills_dir=Path(_get("NOVIELLO_SKILLS_DIR")) if _get("NOVIELLO_SKILLS_DIR") else _default_skills_dir(),
        cadencia_ativa=_bool(_get("CADENCIA_ATIVA", "true")),
        cadencia_calendario=_get("CADENCIA_CALENDARIO", "Noviello — Marketing"),
        cadencia_filtro_titulo=_get("CADENCIA_FILTRO_TITULO", "[NOV-BLOG] Publicação WordPress"),
        cadencia_janela_horas=int(_get("CADENCIA_JANELA_HORAS", "48") or "48"),
        wp_categoria_backlog=_get("WP_CATEGORIA_BACKLOG", "Backlog Editorial"),
        auto_gerar_hero=_bool(_get("AUTO_GERAR_HERO", "false")),
        google_ai_api_key=_get("GOOGLE_AI_API_KEY"),
    )

    # garante que as pastas de trabalho existem
    for d in (cfg.state_dir, cfg.logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    return cfg
