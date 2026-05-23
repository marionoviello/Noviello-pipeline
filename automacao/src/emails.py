"""Montagem dos emails do pipeline.

Com o painel de aprovacao, o Gmail nao carrega mais a decisao — serve apenas para
avisos curtos: o email-ping (ha pecas pendentes), a confirmacao de publicacao e o
alerta de erro.
"""

from __future__ import annotations

from email.message import EmailMessage


def build_alert_email(
    gravidade: str, tipo: str, titulo: str, corpo: str, email_aprovador: str,
) -> EmailMessage:
    """Alerta de pipeline (degradacao/erro/heads-up)."""
    msg = EmailMessage()
    msg["Subject"] = f"[Noviello Pipeline] {gravidade.upper()} — {titulo}"
    msg["To"] = email_aprovador
    msg["From"] = email_aprovador
    msg.set_content(
        f"{titulo}\n\n"
        f"{corpo}\n\n"
        f"---\n"
        f"Tipo: {tipo}\n"
        f"Gravidade: {gravidade}\n"
        f"Painel:  http://localhost:8765\n"
        f"Health:  http://localhost:8765/health.html\n"
    )
    cor = {"critico": "#9b1c2e", "alto": "#b8860b", "info": "#4a5568"}.get(gravidade, "#4a5568")
    msg.add_alternative(
        f'<div style="font-family:Georgia,serif;font-size:14px;color:#1a1a1a;max-width:560px;">'
        f'<div style="background:{cor};color:#fff;padding:10px 14px;border-radius:4px 4px 0 0;'
        f'text-transform:uppercase;font-size:11px;letter-spacing:1.5px;font-weight:bold;">'
        f'{gravidade}</div>'
        f'<div style="border:1px solid #eee;border-top:none;padding:18px 20px;border-radius:0 0 4px 4px;">'
        f'<h3 style="margin:0 0 10px;color:{cor};">{titulo}</h3>'
        f'<pre style="white-space:pre-wrap;font-family:inherit;font-size:14px;margin:0;">{corpo}</pre>'
        f'<p style="margin-top:18px;font-size:12px;color:#666;">Tipo: <code>{tipo}</code></p>'
        f'<p><a href="http://localhost:8765/health.html" style="color:{cor};font-weight:bold;">'
        f'Abrir health &rarr;</a></p>'
        f'</div></div>',
        subtype="html",
    )
    return msg


def build_ping_email(quantidade: int, painel_url: str, email_aprovador: str) -> EmailMessage:
    """Aviso curto: ha pecas pendentes. A decisao e feita no painel, nao no email."""
    msg = EmailMessage()
    plural = "peça" if quantidade == 1 else "peças"
    msg["Subject"] = f"[Painel] {quantidade} {plural} para revisar"
    msg["To"] = email_aprovador
    msg["From"] = email_aprovador
    msg.set_content(
        f"Você tem {quantidade} {plural} aguardando sua decisão.\n\n"
        f"Abra o painel para revisar e decidir: {painel_url}"
    )
    msg.add_alternative(
        '<div style="font-family:Georgia,serif;font-size:15px;color:#1a1a1a;">'
        f"<p>Você tem <strong>{quantidade} {plural}</strong> aguardando sua decisão.</p>"
        f'<p><a href="{painel_url}" style="color:#9b1c2e;font-weight:bold;">'
        "Abrir o painel de aprovação &rarr;</a></p></div>",
        subtype="html",
    )
    return msg


def build_publicado_email(titulo: str, urls: dict, email_aprovador: str) -> EmailMessage:
    """Confirmacao curta de que a peca foi publicada."""
    linhas = []
    for canal in ("instagram", "linkedin", "wordpress"):
        r = urls.get(canal)
        if r and r.get("url"):
            linhas.append(f"  {canal}: {r['url']}")
        elif r and r.get("status") in ("pulado", "simulado"):
            linhas.append(f"  {canal}: {r['status']}")
    msg = EmailMessage()
    msg["Subject"] = f"[Publicado] {titulo}"
    msg["To"] = email_aprovador
    msg["From"] = email_aprovador
    msg.set_content(f"Publicado: {titulo}\n\n" + "\n".join(linhas))
    return msg


def build_error_email(
    peca_id: str, stage: str, erro: str, log_path: str, email_aprovador: str
) -> EmailMessage:
    """Alerta de erro."""
    msg = EmailMessage()
    msg["Subject"] = f"[ERRO] {stage} — peca_id: {peca_id}"
    msg["To"] = email_aprovador
    msg["From"] = email_aprovador
    msg.set_content(
        f"Falha em {stage}.\n\n"
        f"Peca: {peca_id}\n"
        f"Detalhe: {erro}\n"
        f"Log: {log_path}\n\n"
        f"Retomada manual: python manual_retry.py {peca_id}"
    )
    return msg
