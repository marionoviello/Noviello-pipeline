"""Reorganiza calendario 'Noviello — Marketing' a partir de 25/05/2026.

Apaga eventos NOV-BLOG e NOV-MKT existentes na janela [25/05, 25/05 + 8sem]
e cria nova grade conforme Padrao A:

    Seg 19h00 : IG  (corte 1 do pilar da semana)
    Ter 08h30 : LI  (recorte B2B)
    Ter 10h00 : Blog (artigo principal)
    Qua 19h00 : IG  (corte 2)
    Qui 08h30 : LI  (desdobramento)
    Qui 10h00 : Blog (complementar)
    Sex 19h00 : IG  (corte 3 / CTA)

NOV-AGRO e NOV-RADAR sao PRESERVADOS.

Uso:
    .venv\\Scripts\\python.exe setup\\reorganizar_calendario.py --dry-run
    .venv\\Scripts\\python.exe setup\\reorganizar_calendario.py --executar
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# carrega .env
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

# ---- Configuracao ---------------------------------------------------------

INICIO = _dt.date(2026, 5, 25)   # segunda
SEMANAS = 8
TZ = "America/Sao_Paulo"

# (offset_dia_da_semana, hora, minuto, canal, sufixo_titulo, duracao_min, tipo)
# tipo:
#   "pilar"   — peca sobre o pilar editorial da semana
#   "julgado" — Julgado da Semana (STJ/TJ/STF) — formato que viralizou no LI
GRADE = [
    (0, 19, 0,  "IG",   "IG 19h",                    30, "pilar"),
    (1, 8,  30, "LI",   "LI 08h30 — Julgado",        30, "julgado"),  # NOVO: 1x/sem julgado
    (1, 10, 0,  "BLOG", "Publicação WordPress",      60, "pilar"),
    (2, 19, 0,  "IG",   "IG 19h",                    30, "pilar"),
    (3, 8,  30, "LI",   "LI 08h30",                  30, "pilar"),
    (3, 10, 0,  "BLOG", "Publicação WordPress",      60, "pilar"),
    (4, 19, 0,  "IG",   "IG 19h",                    30, "pilar"),
]

PILARES = [
    {"sem": 1, "tema": "ITBI LC 227 + Ata Notarial", "areas": "imobiliário/urbanístico",
     "julgado_sugerido": "STJ — ITBI ou registro de imóveis (REsp recente)"},
    {"sem": 2, "tema": "VE Condomínio Lei 18.403",   "areas": "condominial/imobiliário",
     "julgado_sugerido": "STJ — condominial (cobrança, multa, vaga, antissocial)"},
    {"sem": 3, "tema": "Zoneamento SP + HIS/HMP",    "areas": "urbanístico",
     "julgado_sugerido": "TJ-SP — zoneamento, alvará, OODC, ou STF urbanístico"},
    {"sem": 4, "tema": "Marco Legal Garantias",      "areas": "imobiliário/financeiro",
     "julgado_sugerido": "STJ — alienação fiduciária, garantia real, ou financeiro imobiliário"},
    {"sem": 5, "tema": "Anistia 60 dias + Recap",    "areas": "regularização/urbanístico",
     "julgado_sugerido": "STJ ou TJ-SP — regularização fundiária, REURB, usucapião extrajudicial"},
    {"sem": 6, "tema": "Holding Familiar",           "areas": "sucessório",
     "julgado_sugerido": "STJ — sucessório (ITCMD progressivo, doação com usufruto, holding patrimonial)"},
    {"sem": 7, "tema": "[A definir]",                "areas": "",
     "julgado_sugerido": "STJ/STF — escolher conforme pilar"},
    {"sem": 8, "tema": "[A definir]",                "areas": "",
     "julgado_sugerido": "STJ/STF — escolher conforme pilar"},
]

CATEGORIAS_A_APAGAR = ("BLOG", "MKT")  # NOV-AGRO e NOV-RADAR preservados


def conectar():
    cfg = load_config()
    creds = build_credentials(cfg.google)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
    cals = svc.calendarList().list().execute().get("items", [])
    target = next((c for c in cals if "noviello" in c.get("summary", "").lower()
                   and "marketing" in c.get("summary", "").lower()), None)
    if not target:
        raise SystemExit("Calendario 'Noviello — Marketing' nao encontrado.")
    return svc, target["id"]


def listar_a_apagar(svc, cal_id) -> list[dict]:
    inicio_iso = _dt.datetime.combine(INICIO, _dt.time(0, 0)).isoformat() + "-03:00"
    fim_iso = (
        _dt.datetime.combine(INICIO + _dt.timedelta(weeks=SEMANAS + 1), _dt.time(23, 59))
        .isoformat() + "-03:00"
    )
    resp = svc.events().list(
        calendarId=cal_id, timeMin=inicio_iso, timeMax=fim_iso,
        singleEvents=True, orderBy="startTime", maxResults=250,
    ).execute()

    pra_apagar = []
    for e in resp.get("items", []):
        titulo = e.get("summary", "")
        for cat in CATEGORIAS_A_APAGAR:
            if titulo.startswith(f"[NOV-{cat}]"):
                inicio_str = e.get("start", {}).get("dateTime", "")[:16]
                pra_apagar.append({
                    "id": e["id"], "titulo": titulo, "inicio": inicio_str,
                })
                break
    return pra_apagar


def montar_novos_eventos() -> list[dict]:
    eventos = []
    for semana in range(SEMANAS):
        inicio_semana = INICIO + _dt.timedelta(weeks=semana)
        pilar = PILARES[semana]
        for offset, hora, minuto, canal, sufixo, duracao, tipo in GRADE:
            dia = inicio_semana + _dt.timedelta(days=offset)
            dt_inicio = _dt.datetime.combine(dia, _dt.time(hora, minuto))
            dt_fim = dt_inicio + _dt.timedelta(minutes=duracao)

            prefixo = "NOV-BLOG" if canal == "BLOG" else "NOV-MKT"
            tema_resumo = pilar["tema"][:50]

            if tipo == "julgado":
                titulo = f"[{prefixo}] {sufixo} — Sem {pilar['sem']}"
                descricao_partes = [
                    f"<b>Julgado da Semana</b> (formato que viralizou — manter)",
                    f"<b>Sugestão:</b> {pilar['julgado_sugerido']}",
                    "<br><b>Estrutura padrão:</b>",
                    "• Manchete com a tese decidida<br>"
                    "• Identificação clara (STJ REsp / TJ-SP Apel / STF RE) + ministro/desembargador relator<br>"
                    "• Voto vencedor em 1-2 parágrafos diretos<br>"
                    "• Impacto prático (B2B): o que muda na atuação do advogado/incorporador<br>"
                    "• Sem citações genéricas — apenas o que o julgado decidiu<br>",
                    "<br><b>Tom:</b> técnico, autoridade, máximo 1300 chars. Sem hashtags promocionais "
                    "(máximo 3, e só se forem do tema). Hook nos primeiros 210 chars.",
                ]
            else:
                titulo = f"[{prefixo}] {sufixo} — {tema_resumo}"
                descricao_partes = [
                    f"<b>Pilar da semana {pilar['sem']}:</b> {pilar['tema']}",
                ]
                if pilar["areas"]:
                    descricao_partes.append(f"<b>Áreas:</b> {pilar['areas']}")
                if canal == "BLOG":
                    descricao_partes.append(
                        "<br><b>Checklist:</b><br>"
                        "• Meta-description revisada<br>"
                        "• Imagem destacada definida (ou AUTO_GERAR_HERO=true)<br>"
                        "• Categorias e tags corretas<br>"
                        "• Disclaimer OAB 205/2021 incluso"
                    )
                elif canal == "LI":
                    descricao_partes.append(
                        "<br><b>LinkedIn (B2B):</b> desdobramento do pilar, tom técnico, "
                        "máximo 3 hashtags, 1300 chars sweet spot, hook nos primeiros 210 chars."
                    )
                elif canal == "IG":
                    descricao_partes.append(
                        "<br><b>Instagram @novielloadv (B2C Sênior):</b> "
                        "carrossel 8-10 slides, hook stop-scroll no slide 1, "
                        "CTA aprovado no último slide, disclaimer OAB na legenda.<br>"
                        "Pipeline gera automaticamente após Blog aprovado."
                    )

            eventos.append({
                "titulo": titulo,
                "inicio": dt_inicio,
                "fim": dt_fim,
                "descricao": "<br>".join(descricao_partes),
                "canal": canal,
                "tipo": tipo,
                "semana": pilar["sem"],
            })
    return eventos


def main():
    if "--executar" not in sys.argv and "--dry-run" not in sys.argv:
        print("Uso: --dry-run | --executar")
        sys.exit(1)
    executar = "--executar" in sys.argv

    svc, cal_id = conectar()
    print(f"Calendario: {cal_id}\n")

    # 1. Backup
    pra_apagar = listar_a_apagar(svc, cal_id)
    backup = ROOT / "samples" / "calendario-backup-pre-reorg.json"
    backup.write_text(json.dumps(pra_apagar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backup do que sera apagado: {backup} ({len(pra_apagar)} eventos)")

    print(f"\n=== EVENTOS A APAGAR ({len(pra_apagar)}) ===")
    for e in pra_apagar:
        print(f"  [{e['inicio']}] {e['titulo'][:75]}")

    # 2. Novos eventos
    novos = montar_novos_eventos()
    print(f"\n=== EVENTOS A CRIAR ({len(novos)}) ===")
    for e in novos:
        print(f"  [{e['inicio'].strftime('%Y-%m-%d %a %H:%M')}] {e['titulo'][:75]}")

    print(f"\nResumo: apagar {len(pra_apagar)}, criar {len(novos)}")
    if not executar:
        print("\n(dry-run — nada foi alterado)")
        return

    # 3. Executar
    print("\n>>> EXECUTANDO <<<")
    print(f"Apagando {len(pra_apagar)} eventos...")
    apagados = 0
    for e in pra_apagar:
        try:
            svc.events().delete(calendarId=cal_id, eventId=e["id"]).execute()
            apagados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERRO ao apagar {e['titulo']}: {exc}")
    print(f"  apagados: {apagados}/{len(pra_apagar)}")

    print(f"\nCriando {len(novos)} eventos...")
    criados = 0
    for e in novos:
        body = {
            "summary": e["titulo"],
            "description": e["descricao"],
            "start": {"dateTime": e["inicio"].isoformat(), "timeZone": TZ},
            "end":   {"dateTime": e["fim"].isoformat(), "timeZone": TZ},
        }
        try:
            svc.events().insert(calendarId=cal_id, body=body).execute()
            criados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERRO ao criar {e['titulo']}: {exc}")
    print(f"  criados: {criados}/{len(novos)}")

    print("\nReorganizacao concluida.")


if __name__ == "__main__":
    main()
