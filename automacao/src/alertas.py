"""Alertas por Gmail — disparados pelo pipeline em falhas criticas.

Throttle: cada (tipo, chave) tem TTL minimo entre disparos para evitar spam.
Estado: state/alertas.json.

Gravidades:
  critico — quebra de fluxo, requer acao imediata (token expirou, canal pausado)
  alto    — degradacao (peca em erro, backlog vazio prolongado)
  info    — heads-up (token expira em N dias)

Uso:
    from src.alertas import alertar
    alertar(cfg, gmail_cli, "circuit_pausado",
            chave="instagram",
            titulo="Instagram pausado por 1h (circuit breaker)",
            corpo="3 falhas consecutivas. Verifique IG token, etc.",
            gravidade="critico")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.state import agora_iso

ARQUIVO = "alertas.json"

# TTL minimo por gravidade (segundos)
TTL_POR_GRAVIDADE = {
    "critico": 3600,    # 1h — nao re-alerta a mesma cousa em menos de 1h
    "alto":    7200,    # 2h
    "info":    86400,   # 24h
}


def _path(state_dir: Path) -> Path:
    return Path(state_dir) / ARQUIVO


def _load(state_dir: Path) -> dict:
    p = _path(state_dir)
    if not p.exists():
        return {"ultimos": {}, "historico": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ultimos": {}, "historico": []}


def _save(state_dir: Path, dados: dict) -> None:
    p = _path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _idade(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except (ValueError, TypeError):
        return float("inf")


def deve_alertar(state_dir: Path, tipo: str, chave: str, gravidade: str) -> bool:
    """True se ainda nao houve alerta desse (tipo, chave) no TTL."""
    dados = _load(state_dir)
    k = f"{tipo}::{chave}"
    ultimo = dados.get("ultimos", {}).get(k)
    if not ultimo:
        return True
    ttl = TTL_POR_GRAVIDADE.get(gravidade, 3600)
    return _idade(ultimo) >= ttl


def alertar(
    cfg,
    gmail_cli,
    tipo: str,
    chave: str,
    titulo: str,
    corpo: str,
    gravidade: str = "alto",
    logger=None,
) -> bool:
    """Dispara alerta por email se passou do TTL. Devolve True se enviou.

    tipo+chave compõem a identidade do alerta (ex: 'circuit_pausado'+'instagram').
    """
    if not deve_alertar(cfg.state_dir, tipo, chave, gravidade):
        return False

    from src.emails import build_alert_email
    msg = build_alert_email(
        gravidade=gravidade,
        tipo=f"{tipo}::{chave}",
        titulo=titulo,
        corpo=corpo,
        email_aprovador=cfg.email_aprovador,
    )
    try:
        gmail_cli.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.info("alertas", status="falha_envio", tipo=tipo, erro=str(exc))
        return False

    # registra
    dados = _load(cfg.state_dir)
    dados.setdefault("ultimos", {})[f"{tipo}::{chave}"] = agora_iso()
    dados.setdefault("historico", []).append({
        "tipo": tipo, "chave": chave, "gravidade": gravidade,
        "titulo": titulo, "em": agora_iso(),
    })
    # mantem so as ultimas 50 entradas do historico
    dados["historico"] = dados["historico"][-50:]
    _save(cfg.state_dir, dados)

    if logger:
        logger.info("alertas", status="enviado", tipo=tipo, chave=chave, gravidade=gravidade)
    return True
