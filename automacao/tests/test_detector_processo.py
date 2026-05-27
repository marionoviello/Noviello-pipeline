"""Testes do detector de menções a processos em texto livre."""

from src.detector_processo import detectar, gerar_chaves_canonicas


# ---- STJ ------------------------------------------------------------------

def test_detecta_resp_simples():
    texto = "Conforme decidido no REsp 2.215.421/SE, o recibo basta."
    ds = detectar(texto)
    assert len(ds) == 1
    assert ds[0].classe == "RESP"
    assert ds[0].numero == "2215421"
    assert ds[0].uf == "SE"


def test_detecta_resp_sem_uf():
    """Padrão moderno do STJ — alguns acórdãos não trazem UF."""
    ds = detectar("Vide o REsp 1.234.567")
    assert len(ds) == 1
    assert ds[0].numero == "1234567"
    assert ds[0].uf == ""


def test_detecta_agrg_no_resp():
    ds = detectar("AgRg no REsp 652.449/SP, j. 23/3/2010")
    assert len(ds) == 1
    # AgRg no REsp é tratado como RESP (a normalização junta)
    assert ds[0].numero == "652449"
    assert ds[0].uf == "SP"


def test_detecta_aresp():
    ds = detectar("Conforme o AREsp 1.999.888/RJ.")
    assert len(ds) == 1
    assert ds[0].classe == "ARESP"
    assert ds[0].numero == "1999888"


def test_detecta_hc():
    ds = detectar("Habeas Corpus: HC 123.456/SP")
    assert any(d.classe == "HC" and d.numero == "123456" for d in ds)


def test_dedup_se_mesmo_processo_citado_duas_vezes():
    texto = "REsp 2.215.421/SE é o leading case. O REsp 2.215.421/SE foi unânime."
    ds = detectar(texto)
    assert len(ds) == 1


# ---- STF ------------------------------------------------------------------

def test_detecta_recurso_extraordinario():
    ds = detectar("Tema definido no RE 1.000.000/SP (Tema 1234).")
    re_proc = [d for d in ds if d.classe == "RE"]
    assert len(re_proc) == 1
    assert re_proc[0].numero == "1000000"


def test_detecta_are():
    ds = detectar("Vide o ARE 1.234.567/MG")
    assert any(d.classe == "ARE" and d.numero == "1234567" for d in ds)


def test_detecta_adpf():
    ds = detectar("Na ADPF 442, o STF...")
    assert any(d.classe == "ADPF" for d in ds)


# ---- CNJ (TJ-SP e outros) ------------------------------------------------

def test_detecta_padrao_cnj():
    ds = detectar(
        "Apelação Cível 1234567-89.2020.8.26.0100, 3ª Câmara Direito Privado."
    )
    cnj = [d for d in ds if d.classe == "CNJ"]
    assert len(cnj) == 1
    assert cnj[0].numero == "1234567-89.2020.8.26.0100"


def test_detecta_cnj_e_resp_no_mesmo_texto():
    """Texto editorial pode citar STJ + TJ-SP no mesmo parágrafo."""
    texto = (
        "A 3ª Turma do STJ, no REsp 2.215.421/SE, alinhou-se ao TJ-SP "
        "na Apelação 1234567-89.2020.8.26.0100."
    )
    ds = detectar(texto)
    classes = {d.classe for d in ds}
    assert "RESP" in classes
    assert "CNJ" in classes


# ---- Falsos positivos a evitar -------------------------------------------

def test_ignora_numeros_muito_curtos():
    """'RE 1' não é processo — é referência genérica."""
    ds = detectar("Veja o RE 1 ou o MS 12.")
    # nenhum deve passar do filtro de _MIN_DIGITS=4
    assert ds == []


def test_ignora_texto_sem_processo():
    ds = detectar("Este artigo discute usucapião sem citar julgado específico.")
    assert ds == []


def test_ignora_referencia_a_artigo_de_lei():
    """'Art. 1.242 do CC' não deve virar processo."""
    ds = detectar("Conforme o art. 1.242 do CC, são requisitos...")
    # nenhum match — 'art' não é classe processual
    assert ds == []


# ---- chaves canônicas pro registry ---------------------------------------

def test_gerar_chaves_canonicas_resp():
    ds = detectar("REsp 2.215.421/SE")
    chaves = gerar_chaves_canonicas(ds)
    # deve casar exatamente com a chave que o producer Julgado usa
    assert chaves == ["processo:resp-2215421-se"]


def test_gerar_chaves_canonicas_cross_format_matching():
    """Garantia: artigo de blog mencionando REsp X gera a MESMA chave que
    o Card Julgado da Semana usa pro mesmo processo. Essa é a garantia
    cross-format do anti-duplicata."""
    from src.publicacoes_unicas import chave_processo
    # Chave gerada pelo card julgado:
    chave_card = chave_processo("REsp 2.215.421/SE")
    # Chave gerada por detecção em texto de artigo:
    ds = detectar("Análise do REsp 2.215.421/SE no contexto da reforma.")
    chave_artigo = gerar_chaves_canonicas(ds)[0]
    assert chave_card == chave_artigo
    assert chave_card == "processo:resp-2215421-se"


def test_gerar_chaves_canonicas_dedup():
    """Mesmo processo citado 2× retorna 1 chave."""
    ds = detectar("REsp 2.215.421/SE foi importante. Vide o REsp 2.215.421/SE.")
    chaves = gerar_chaves_canonicas(ds)
    assert len(chaves) == 1


# ---- texto real (ementa de acórdão) --------------------------------------

def test_ementa_real_stj():
    """Trecho real da ementa do REsp 2.215.421/SE (smoke do nosso own caso)."""
    texto = """
    DIREITO CIVIL. RECURSO ESPECIAL. AÇÃO DE USUCAPIÃO. MODALIDADE
    ORDINÁRIA. ARTIGO 1.242 DO CÓDIGO CIVIL.

    A Súmula 237 do STF, segundo a qual "o usucapião pode ser arguido
    em defesa", evidencia que o direito do usucapiente já existe.

    A jurisprudência desta Corte entende, no REsp 652.449/SP, Terceira Turma,
    DJe 23/3/2010, que justo título é o ato ou fato jurídico que possa
    transmitir a propriedade.
    """
    ds = detectar(texto)
    # esperado: 1 RESP (652449/SP). Súmula NÃO é detectada — não é processo.
    resps = [d for d in ds if d.classe == "RESP"]
    assert any(d.numero == "652449" and d.uf == "SP" for d in resps)
