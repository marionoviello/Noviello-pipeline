"""Retomada manual da publicacao de uma peca que falhou.

Uso (a partir de automacao/):
    .venv\\Scripts\\python.exe manual_retry.py <peca_id>

Recarrega o estado da peca e re-executa os stages 05-08 (handle_approve).
Canais ja publicados nao sao republicados.
"""

from __future__ import annotations

import sys

from src.config import load_config
from src.gmail_client import GmailClient
from src.logger import get_logger, setup_logging
from src.pipeline import handle_approve
from src.state import StateStore


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: python manual_retry.py <peca_id>")
        return 1
    peca_id = sys.argv[1]

    cfg = load_config()
    setup_logging(cfg.logs_dir)
    logger = get_logger("manual_retry")

    if not cfg.google_pronto():
        print("ERRO: credenciais Google ausentes no .env.")
        return 1

    store = StateStore(cfg.state_dir)
    if not store.exists(peca_id):
        print(f"ERRO: nao ha estado para a peca '{peca_id}' em {cfg.state_dir}.")
        return 1

    estado = store.load(peca_id)
    gmail = GmailClient(cfg.google)
    print(f"Retomando publicacao da peca '{peca_id}' (status atual: {estado.status})...")
    handle_approve(estado, cfg, gmail, store, logger)
    print("Concluido. Verifique o painel e os logs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
