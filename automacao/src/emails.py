"""Montagem dos emails do pipeline.

Com o painel de aprovacao, o Gmail nao carrega mais a decisao — serve apenas para
avisos curtos: o email-ping (ha pecas pendentes), a confirmacao de publicacao e o
alerta de erro.
"""

from __future__ import annotations

from email.message import EmailMessage


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
