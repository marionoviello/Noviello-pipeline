"""Detector de "cara de IA" em textos gerados (porta do linkedin-humanizer).

Aplica regras tiered baseadas em Sergey Bulaev's linkedin-skills (MIT). Adaptado
pra PT-BR e pro contexto juridico/Noviello.

Tiers:
  FORENSIC — leakage de ferramenta IA, nenhum humano produz. Bloquear.
  STRICT   — vocabulario corporativo/AI-slop. Reescrever.
  AESTHETIC — preferencias de estilo (em-dash, double-space). Avisar.

Cada detector devolve {tier, codigo, mensagem, trechos: list[str]}.

Uso:
    issues = detectar(texto)
    if any(i["tier"] == "forensic" for i in issues):
        # bloqueia publicacao
        ...
    elif any(i["tier"] == "strict" for i in issues):
        # avisa Mario no painel mas nao bloqueia
        ...
"""

from __future__ import annotations

import re


# ---- FORENSIC: leakage de ferramenta IA ---------------------------------

_FORENSIC_MARKERS = [
    (re.compile(r"\boaicite\b", re.I),          "FOR-001", "Marker ChatGPT 'oaicite'"),
    (re.compile(r"\bcontentReference\b", re.I), "FOR-002", "Marker ChatGPT 'contentReference'"),
    (re.compile(r"\bturn\d+search\d+\b", re.I), "FOR-003", "Marker tool-call OpenAI 'turn0search0'"),
    (re.compile(r"\battached_file\b", re.I),    "FOR-004", "Marker file-ref Claude/GPT"),
    (re.compile(r"\bgrok_card\b", re.I),        "FOR-005", "Marker Grok 'grok_card'"),
    (re.compile(r"\boai_citation\b", re.I),     "FOR-006", "Marker OpenAI citation"),
]

_CUTOFF_DISCLAIMERS_PT = [
    (re.compile(r"(?i)at[ée] (a minha )?(ultima |última )?(atualiza[çc][ãa]o|data de corte|cutoff)[^.]*\."),
     "FOR-010", "Disclaimer de cutoff: 'até a minha última atualização'"),
    (re.compile(r"(?i)at[ée] (janeiro|junho|outubro|novembro) de 202\d[^.]*\."),
     "FOR-011", "Disclaimer datado: 'até X de 202Y'"),
    (re.compile(r"(?i)n[ãa]o (posso|consigo) (fornecer|dar) (informa[çc][ãa]o|dados) (em tempo real|atualizad[ao])[^.]*\."),
     "FOR-012", "Disclaimer: 'não consigo informação em tempo real'"),
    (re.compile(r"(?i)meus dados de treinamento[^.]*\."),
     "FOR-013", "Disclaimer: 'meus dados de treinamento'"),
]

_CUTOFF_DISCLAIMERS_EN = [
    (re.compile(r"(?i)As of (my )?(last update|knowledge cutoff|training cutoff)[^.]*\."),
     "FOR-020", "EN: 'As of my last update...'"),
    (re.compile(r"(?i)Based on (information|data) (available|up to) [^.]*\."),
     "FOR-021", "EN: 'Based on information available...'"),
]

_PHRASAL_TEMPLATES = [
    (re.compile(r"\[Seu Nome\]"),     "FOR-030", "Placeholder '[Seu Nome]' não preenchido"),
    (re.compile(r"\[Sua Empresa\]"),  "FOR-031", "Placeholder '[Sua Empresa]'"),
    (re.compile(r"\[Insira [^\]]+\]"),"FOR-032", "Placeholder '[Insira ...]'"),
    (re.compile(r"\[Descreva [^\]]+\]"), "FOR-033", "Placeholder '[Descreva ...]'"),
    (re.compile(r"\[Your Name\]"),    "FOR-040", "Placeholder EN '[Your Name]'"),
    (re.compile(r"\[Insert [^\]]+\]"),"FOR-041", "Placeholder EN '[Insert ...]'"),
    (re.compile(r"202\d-XX-XX"),      "FOR-050", "Data placeholder '202X-XX-XX'"),
]


# ---- STRICT: vocabulario corporativo / AI-slop ---------------------------

# Em PT-BR — palavras tipicas de saida de IA juridica/corporativa que
# escapam a voz da casa. Lista calibrada por contexto Noviello.
_VOCAB_BLACKLIST_PT = [
    "alavancar", "alavancando", "alavanca",
    "utilizar", "utilizando",  # use "usar"
    "facilitar", "facilita",
    "otimizar", "otimizando", "otimização", "otimizacao",
    "robusto", "robusta", "robustez",
    "seamless", "perfeito de ponta a ponta",
    "navegar pelos", "navegar pela",  # "navegar pelas complexidades"
    "desvendar", "desbloquear",
    "fomentar", "fomenta", "fomentando",
    "cultivar", "cultiva", "cultivando",
    "fundamentalmente", "essencialmente",
    "em última análise", "em ultima analise",
    "crucialmente", "notavelmente",
    "panorama", "ecossistema", "paradigma",
    "no panorama atual", "no cenário atual", "no cenario atual",
    "no mundo de hoje", "no mundo acelerado de hoje",
    "no fim das contas", "ao final do dia",
    "uma jornada", "essa jornada", "essa nossa jornada",
    "game-changer", "divisor de águas",
    "mergulho profundo", "deep dive",
    "trazer à tona", "trazer a tona",
]

_VOCAB_BLACKLIST_EN = [
    "leverage", "leveraging",
    "utilize", "utilizing",
    "delve", "delving",
    "harness", "harnessing",
    "foster", "fostering",
    "streamline", "streamlining",
    "fundamentally", "essentially", "ultimately", "crucially", "notably",
    "landscape", "ecosystem", "paradigm", "realm", "tapestry",
    "game-changer", "deep dive",
    "at the end of the day",
    "in today's fast-paced world",
]

_OUTLINE_CLOSERS_PT = [
    (re.compile(r"(?i)\bem conclus[ãa]o,"),    "STR-100", "Fecho de IA: 'Em conclusão,'"),
    (re.compile(r"(?i)\bpara resumir,"),       "STR-101", "Fecho de IA: 'Para resumir,'"),
    (re.compile(r"(?i)\bem resumo,"),          "STR-102", "Fecho de IA: 'Em resumo,'"),
    (re.compile(r"(?i)\bolhando (para )?o futuro,"),       "STR-103", "Fecho de IA: 'Olhando para o futuro,'"),
    (re.compile(r"(?i)\bem [úu]ltima an[áa]lise,"),       "STR-104", "Fecho de IA: 'Em última análise,'"),
]

_NAO_E_APENAS_X = re.compile(
    r"(?i)n[ãa]o (?:[ée]|se trata)? ?apenas (?:de |sobre )?[\w\s]+,?\s+(?:mas|[ée]) (?:tamb[ée]m )?(?:de |sobre )?[\w\s]+",
)


# ---- AESTHETIC: preferencias de estilo -----------------------------------

def _contar_em_dashes(texto: str) -> int:
    """Conta em-dash, en-dash e double-dash."""
    return texto.count("—") + texto.count("–") + len(re.findall(r"(?<!-)--(?!-)", texto))


# ---- API pública ----------------------------------------------------------

def detectar(texto: str, *, idioma: str = "pt") -> list[dict]:
    """Devolve lista de issues encontradas no texto.

    Cada issue: {tier, codigo, mensagem, trechos: list[str]}
    tier ∈ {forensic, strict, aesthetic}
    """
    issues: list[dict] = []
    palavras = len(texto.split())

    # FORENSIC — markers
    for regex, codigo, msg in _FORENSIC_MARKERS:
        matches = regex.findall(texto)
        if matches:
            issues.append({
                "tier": "forensic", "codigo": codigo, "mensagem": msg,
                "trechos": list(set(matches))[:5],
            })

    # FORENSIC — cutoff disclaimers
    cutoffs = _CUTOFF_DISCLAIMERS_PT + (_CUTOFF_DISCLAIMERS_EN if idioma == "en" else [])
    for regex, codigo, msg in cutoffs:
        ms = regex.findall(texto)
        if ms:
            issues.append({
                "tier": "forensic", "codigo": codigo, "mensagem": msg,
                "trechos": [m if isinstance(m, str) else str(m) for m in ms[:3]],
            })

    # FORENSIC — placeholders
    for regex, codigo, msg in _PHRASAL_TEMPLATES:
        ms = regex.findall(texto)
        if ms:
            issues.append({
                "tier": "forensic", "codigo": codigo, "mensagem": msg,
                "trechos": [str(m) for m in ms[:3]],
            })

    # AESTHETIC/FORENSIC — em-dash overuse
    em = _contar_em_dashes(texto)
    if em >= 3 and palavras < 300:
        issues.append({
            "tier": "forensic", "codigo": "FOR-200",
            "mensagem": f"Overuse de em-dash: {em} em texto de {palavras} palavras",
            "trechos": [],
        })
    elif em >= 1:
        issues.append({
            "tier": "aesthetic", "codigo": "AES-001",
            "mensagem": f"Uso de em-dash/en-dash detectado ({em}×). Preferir ':', ',' ou '..'.",
            "trechos": [],
        })

    # STRICT — vocabulario blacklist
    vocab = _VOCAB_BLACKLIST_PT + (_VOCAB_BLACKLIST_EN if idioma == "en" else [])
    encontrados: list[str] = []
    texto_lower = texto.lower()
    for palavra in vocab:
        if re.search(r"\b" + re.escape(palavra.lower()) + r"\b", texto_lower):
            encontrados.append(palavra)
    if encontrados:
        issues.append({
            "tier": "strict", "codigo": "STR-001",
            "mensagem": f"Vocabulário AI/corporativo detectado ({len(encontrados)} palavras)",
            "trechos": encontrados[:10],
        })

    # STRICT — outline closers
    closers = _OUTLINE_CLOSERS_PT
    for regex, codigo, msg in closers:
        if regex.search(texto):
            issues.append({
                "tier": "strict", "codigo": codigo, "mensagem": msg,
                "trechos": [],
            })

    # STRICT — "não é apenas X, mas Y" (overused na IA)
    if _NAO_E_APENAS_X.search(texto):
        issues.append({
            "tier": "strict", "codigo": "STR-200",
            "mensagem": "Estrutura overused: 'Não é apenas X, mas Y'",
            "trechos": [],
        })

    # AESTHETIC — asterisco de ênfase
    asteriscos = re.findall(r"\*\*?[^\s*][^*]*?\*\*?", texto)
    if asteriscos:
        issues.append({
            "tier": "aesthetic", "codigo": "AES-002",
            "mensagem": f"Asteriscos de ênfase ({len(asteriscos)}×). LinkedIn não renderiza, fica visível.",
            "trechos": asteriscos[:5],
        })

    return issues


def resumir(issues: list[dict]) -> dict:
    """Resumo por tier (pra logger/painel)."""
    return {
        "total": len(issues),
        "forensic": sum(1 for i in issues if i["tier"] == "forensic"),
        "strict": sum(1 for i in issues if i["tier"] == "strict"),
        "aesthetic": sum(1 for i in issues if i["tier"] == "aesthetic"),
        "codigos": [i["codigo"] for i in issues],
    }


def deve_bloquear(issues: list[dict]) -> bool:
    """True se ha issues forensic (publicacao deveria ser bloqueada)."""
    return any(i["tier"] == "forensic" for i in issues)
