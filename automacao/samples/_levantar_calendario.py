"""Levanta todos eventos do 'Noviello — Marketing' nos proximos 60 dias.
Categoriza por tipo (BLOG/MKT-LI/MKT-IG/AGRO/RADAR/etc) e devolve JSON pra
reorganizar manualmente."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for env_file in (ROOT / ".env", ROOT.parent / ".env"):
    if env_file.exists():
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from googleapiclient.discovery import build  # noqa: E402
from src.config import load_config  # noqa: E402
from src.google_creds import build_credentials  # noqa: E402

cfg = load_config()
creds = build_credentials(cfg.google)
svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

cals = svc.calendarList().list().execute().get("items", [])
target = next((c for c in cals if "noviello" in c.get("summary", "").lower()
               and "marketing" in c.get("summary", "").lower()), None)
if not target:
    print("nao achei o calendario")
    sys.exit(1)

cal_id = target["id"]
agora = _dt.datetime.now(_dt.timezone.utc)
fim = agora + _dt.timedelta(days=60)
resp = svc.events().list(
    calendarId=cal_id,
    timeMin=agora.isoformat(),
    timeMax=fim.isoformat(),
    singleEvents=True,
    orderBy="startTime",
    maxResults=250,
).execute()

eventos = resp.get("items", [])
print(f"{len(eventos)} eventos nos proximos 60 dias\n")

# Categoriza por prefixo [NOV-XXX]
por_categoria: dict[str, list] = defaultdict(list)
for e in eventos:
    titulo = e.get("summary", "")
    m = re.match(r"\[NOV-(\w+)\]\s*(.*)", titulo)
    cat = m.group(1) if m else "SEM-PREFIXO"
    resto = m.group(2) if m else titulo
    inicio = e.get("start", {})
    data = (inicio.get("dateTime") or inicio.get("date", ""))[:16]
    por_categoria[cat].append({
        "data": data,
        "titulo_simples": resto,
        "titulo_completo": titulo,
        "id": e["id"],
        "descricao": (e.get("description") or "").replace("<br>", "\n")[:200],
    })

# Resumo
print("RESUMO POR CATEGORIA:")
for cat in sorted(por_categoria):
    print(f"  [{cat:8}] {len(por_categoria[cat])} eventos")

# Salva pra inspecao detalhada
out = ROOT / "samples" / "calendario-atual.json"
out.write_text(json.dumps(dict(por_categoria), ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nDetalhes salvos: {out}")

# Imprime os de publicacao reais (BLOG-pub, MKT-LI, MKT-IG)
print("\n=== PUBLICACOES PROGRAMADAS ===")
def filtrar_pub(itens):
    pub = []
    for it in itens:
        t = it["titulo_simples"].lower()
        if any(k in t for k in ("publica", "li ", "ig ", "reels", "carrossel", "post est")):
            pub.append(it)
    return pub

for cat in ("BLOG", "MKT", "AGRO"):
    items = filtrar_pub(por_categoria.get(cat, []))
    if not items:
        continue
    print(f"\n[{cat}] {len(items)} publicacoes:")
    for it in items[:20]:
        print(f"  {it['data']}  {it['titulo_simples'][:65]}")
    if len(items) > 20:
        print(f"  ... e mais {len(items) - 20}")
