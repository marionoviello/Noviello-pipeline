"""Testes do detector de AI-tells."""

from src.ai_tells_detector import deve_bloquear, detectar, resumir


def test_texto_limpo_nao_tem_issues():
    texto = "Doação com reserva de usufruto preserva controle. STJ confirma em 2024."
    assert detectar(texto) == []


def test_em_dash_unico_e_aesthetic():
    issues = detectar("A regra é dura — 90 dias para sair.")
    assert any(i["tier"] == "aesthetic" and "em-dash" in i["mensagem"].lower() for i in issues)
    assert not deve_bloquear(issues)


def test_em_dash_overuse_e_forensic():
    """3+ em-dashes em texto curto bloqueiam."""
    texto = "Hoje vou falar — sobre algo importante — mas antes — uma nota."
    issues = detectar(texto)
    forensic = [i for i in issues if i["tier"] == "forensic"]
    assert forensic, "Esperado bloqueio forensic"
    assert deve_bloquear(issues)


def test_vocabulario_blacklist_pt():
    texto = "Vamos alavancar essa estratégia fundamentalmente para otimizar resultados."
    issues = detectar(texto)
    vocab = [i for i in issues if i["codigo"] == "STR-001"]
    assert vocab
    trechos = vocab[0]["trechos"]
    assert "alavancar" in trechos
    assert "fundamentalmente" in trechos
    assert "otimizar" in trechos


def test_fecho_em_conclusao_e_strict():
    texto = "Bla bla bla. Em conclusão, isso é importante para todos."
    issues = detectar(texto)
    assert any(i["codigo"] == "STR-100" for i in issues)


def test_asterisco_enfase_aesthetic():
    texto = "Esse é um *ponto crítico* do contrato."
    issues = detectar(texto)
    assert any(i["codigo"] == "AES-002" for i in issues)


def test_marker_oaicite_forensic():
    texto = "Resposta com leakage oaicite no meio."
    issues = detectar(texto)
    assert deve_bloquear(issues)
    assert any(i["codigo"] == "FOR-001" for i in issues)


def test_disclaimer_cutoff_forensic():
    texto = "Até a minha última atualização, o ITCMD em SP era de 4%. Mas pode ter mudado."
    issues = detectar(texto)
    assert deve_bloquear(issues)


def test_placeholder_seu_nome_forensic():
    texto = "Saudações, [Seu Nome] da Noviello Advocacia."
    issues = detectar(texto)
    assert any(i["codigo"] == "FOR-030" for i in issues)
    assert deve_bloquear(issues)


def test_resumir_agrega_por_tier():
    texto = "Vou alavancar — fundamentalmente — em conclusão isso *ajuda* — todos."
    issues = detectar(texto)
    res = resumir(issues)
    assert res["total"] > 0
    assert res["forensic"] >= 1  # 3+ em-dashes
    assert res["strict"] >= 1    # vocab
    assert "codigos" in res


def test_idioma_en_amplia_blacklist():
    texto_pt = "We need to leverage this opportunity to streamline operations."
    issues_pt = detectar(texto_pt, idioma="pt")
    issues_en = detectar(texto_pt, idioma="en")
    assert resumir(issues_en)["strict"] > resumir(issues_pt)["strict"]


def test_estrutura_nao_e_apenas_x_mas_y():
    texto = "Não é apenas um contrato, é também uma proteção patrimonial."
    issues = detectar(texto)
    assert any(i["codigo"] == "STR-200" for i in issues)
