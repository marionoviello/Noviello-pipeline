"""Cliente Google Calendar — registra a publicacao no calendario 'Noviello — Marketing'.

Stage 08 (enriquecimento). Falha aqui nao e critica: o pipeline registra e segue.
"""

from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

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


class CalendarClient:
    def __init__(self, google_cfg: dict):
        creds = build_credentials(google_cfg)
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    @_retry
    def resolver_calendar_id(self, nome: str) -> str | None:
        """Converte o nome de exibicao do calendario no seu ID."""
        resp = self._svc.calendarList().list().execute()
        for cal in resp.get("items", []):
            if cal.get("summary", "").strip() == nome.strip():
                return cal["id"]
        return None

    @_retry
    def _buscar_evento(self, calendar_id: str, termo: str) -> dict | None:
        resp = (
            self._svc.events()
            .list(calendarId=calendar_id, q=termo, maxResults=10, singleEvents=True)
            .execute()
        )
        itens = resp.get("items", [])
        return itens[0] if itens else None

    @_retry
    def _patch_evento(self, calendar_id: str, event_id: str, descricao: str) -> None:
        self._svc.events().patch(
            calendarId=calendar_id, eventId=event_id, body={"description": descricao}
        ).execute()

    def registrar_publicacao(self, calendar_nome: str, peca, urls: dict, publicado_em: str) -> bool:
        """Acha o evento da peca e anexa as URLs publicadas na descricao.

        Devolve True se encontrou e atualizou; False se nao achou o evento.
        """
        calendar_id = self.resolver_calendar_id(calendar_nome)
        if not calendar_id:
            return False

        evento = self._buscar_evento(calendar_id, peca.titulo_curto) or self._buscar_evento(
            calendar_id, peca.peca_id
        )
        if not evento:
            return False

        linhas = [
            f"publicado_em: {publicado_em}",
            f"peca_id: {peca.peca_id}",
        ]
        for canal, info in urls.items():
            if info.get("url"):
                linhas.append(f"{canal}: {info['url']}")
        adendo = "\n".join(linhas)

        descricao = evento.get("description", "")
        nova = f"{descricao}\n\n--- automacao ---\n{adendo}".strip()
        self._patch_evento(calendar_id, evento["id"], nova)
        return True
