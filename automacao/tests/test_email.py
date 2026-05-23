from src.emails import build_error_email, build_ping_email, build_publicado_email

APROVADOR = "mario@noviello.adv.br"
PAINEL = "http://localhost:8765"


def _texto(msg):
    plain = next(p for p in msg.walk() if p.get_content_type() == "text/plain")
    return plain.get_content()


def test_ping_email_plural():
    msg = build_ping_email(3, PAINEL, APROVADOR)
    assert "3 peças" in msg["Subject"]
    assert msg["To"] == APROVADOR
    assert PAINEL in _texto(msg)


def test_ping_email_singular():
    msg = build_ping_email(1, PAINEL, APROVADOR)
    assert "1 peça" in msg["Subject"]
    assert "peças" not in msg["Subject"]


def test_ping_email_tem_link_html():
    msg = build_ping_email(1, PAINEL, APROVADOR)
    html = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    assert PAINEL in html.get_content()


def test_publicado_email():
    urls = {
        "instagram": {"url": "https://instagram.com/p/abc"},
        "wordpress": {"status": "simulado"},
    }
    msg = build_publicado_email("Inventario Extrajudicial", urls, APROVADOR)
    assert msg["Subject"] == "[Publicado] Inventario Extrajudicial"
    corpo = msg.get_content()
    assert "instagram.com/p/abc" in corpo
    assert "wordpress: simulado" in corpo


def test_error_email():
    msg = build_error_email("social-11745", "stage.05", "canal fora do ar", "logs/x", APROVADOR)
    assert "[ERRO]" in msg["Subject"]
    assert "social-11745" in msg["Subject"]
    assert "canal fora do ar" in msg.get_content()
