"""Cliente Gmail — envio, leitura de threads e manipulacao de labels.

Retry exponencial (3x: 2s/8s/32s) em erros HTTP transitorios (429 e 5xx).
"""

from __future__ import annotations

import base64
from email.message import EmailMessage

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.google_creds import build_credentials

_STATUS_TRANSITORIOS = {429, 500, 502, 503, 504}


def _transitorio(exc: BaseException) -> bool:
    if isinstance(exc, HttpError):
        return getattr(exc.resp, "status", None) in _STATUS_TRANSITORIOS
    return isinstance(exc, (TimeoutError, ConnectionError))


_retry = retry(
    retry=retry_if_exception(_transitorio),
    wait=wait_exponential(multiplier=2, min=2, max=32),
    stop=stop_after_attempt(3),
    reraise=True,
)


class GmailClient:
    def __init__(self, google_cfg: dict):
        creds = build_credentials(google_cfg)
        # cache_discovery=False evita warning e dependencia de cache em disco
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # ---- envio -----------------------------------------------------------
    @_retry
    def send_message(self, mensagem: EmailMessage, thread_id: str | None = None) -> dict:
        """Envia um EmailMessage ja montado. Devolve {id, threadId}."""
        raw = base64.urlsafe_b64encode(mensagem.as_bytes()).decode("ascii")
        corpo: dict = {"raw": raw}
        if thread_id:
            corpo["threadId"] = thread_id
        return self._svc.users().messages().send(userId="me", body=corpo).execute()

    # ---- leitura ---------------------------------------------------------
    @_retry
    def list_threads(self, query: str) -> list[dict]:
        resp = (
            self._svc.users()
            .threads()
            .list(userId="me", q=query)
            .execute()
        )
        return resp.get("threads", [])

    @_retry
    def get_thread(self, thread_id: str, full: bool = False) -> dict:
        formato = "full" if full else "metadata"
        return (
            self._svc.users()
            .threads()
            .get(userId="me", id=thread_id, format=formato)
            .execute()
        )

    # ---- labels ----------------------------------------------------------
    @_retry
    def list_labels(self) -> list[dict]:
        resp = self._svc.users().labels().list(userId="me").execute()
        return resp.get("labels", [])

    @_retry
    def delete_label(self, label_id: str) -> None:
        self._svc.users().labels().delete(userId="me", id=label_id).execute()

    @_retry
    def create_label(self, nome: str) -> dict:
        corpo = {
            "name": nome,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        return self._svc.users().labels().create(userId="me", body=corpo).execute()

    @_retry
    def modify_message_labels(
        self,
        message_id: str,
        adicionar: list[str] | None = None,
        remover: list[str] | None = None,
    ) -> dict:
        corpo = {
            "addLabelIds": adicionar or [],
            "removeLabelIds": remover or [],
        }
        return (
            self._svc.users()
            .messages()
            .modify(userId="me", id=message_id, body=corpo)
            .execute()
        )

    @_retry
    def modify_thread_labels(
        self,
        thread_id: str,
        adicionar: list[str] | None = None,
        remover: list[str] | None = None,
    ) -> dict:
        corpo = {
            "addLabelIds": adicionar or [],
            "removeLabelIds": remover or [],
        }
        return (
            self._svc.users()
            .threads()
            .modify(userId="me", id=thread_id, body=corpo)
            .execute()
        )
