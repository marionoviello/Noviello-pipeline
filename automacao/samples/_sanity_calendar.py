"""Sanity: lista proximos 14 dias do calendario 'Noviello — Marketing'.
Quero ver o padrao de titulos pra decidir o filtro do promotor de cadencia."""

from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

for env_file in (ROOT / ".env", ROOT.parent / ".env"):
    if env_file.exists():
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from googleapiclient.discovery import build  # noqa: E402

from src.google_creds import build_credentials  # noqa: E402
from src.config import load_config  # noqa: E402

cfg = load_config()
creds = build_credentials(cfg.google)
svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

# resolve id por nome
cals = svc.calendarList().list().execute().get("items", [])
target = next((c for c in cals if "noviello" in c.get("summary", "").lower()
               and "marketing" in c.get("summary", "").lower()), None)
if not target:
    print("Calendario 'Noviello — Marketing' nao encontrado entre:")
    for c in cals:
        print(f"  - {c.get('summary')}")
    sys.exit(1)

cal_id = target["id"]
nome = target.get("summary")
print(f"Calendario: {nome}\n")

agora = _dt.datetime.now(_dt.timezone.utc)
fim = agora + _dt.timedelta(days=14)
resp = svc.events().list(
    calendarId=cal_id,
    timeMin=agora.isoformat(),
    timeMax=fim.isoformat(),
    singleEvents=True,
    orderBy="startTime",
    maxResults=50,
).execute()

eventos = resp.get("items", [])
print(f"{len(eventos)} eventos nos proximos 14 dias:\n")
for e in eventos:
    inicio = e.get("start", {})
    dia = inicio.get("dateTime") or inicio.get("date", "?")
    titulo = e.get("summary", "(sem titulo)")
    descricao = (e.get("description") or "").split("\n")[0][:80]
    print(f"  [{dia[:16]}] {titulo}")
    if descricao:
        print(f"               desc: {descricao}")
