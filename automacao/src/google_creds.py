"""Constroi credenciais OAuth do Google a partir do refresh_token salvo no .env.

A biblioteca renova o access_token automaticamente a cada uso.
"""

from __future__ import annotations

from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    # 'calendar' (acesso total) cobre tanto calendarList.list (achar a agenda pelo
    # nome) quanto events.patch. 'calendar.events' sozinho nao lista agendas.
    "https://www.googleapis.com/auth/calendar",
]


class CredencialAusente(Exception):
    pass


def build_credentials(google_cfg: dict) -> Credentials:
    """google_cfg = config.google (client_id, client_secret, refresh_token)."""
    faltando = [k for k in ("client_id", "client_secret", "refresh_token") if not google_cfg.get(k)]
    if faltando:
        raise CredencialAusente(
            f"credencial Google incompleta no .env: {', '.join(faltando)}. "
            "Rode setup/gmail_auth.py."
        )
    return Credentials(
        token=None,
        refresh_token=google_cfg["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=google_cfg["client_id"],
        client_secret=google_cfg["client_secret"],
        scopes=SCOPES,
    )
