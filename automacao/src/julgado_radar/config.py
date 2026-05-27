"""Constantes do Radar de Julgados."""

from __future__ import annotations

# Areas-alvo do acervo (carro-chefe + complementares Noviello).
# Itens fora dessas areas vao para tabela `descartados` (auditavel).
AREAS_ALVO = ("urbanistico", "imobiliario", "sucessorio")

# Valor canonico usado quando a IA classifica fora do escopo.
AREA_FORA = "fora"

# Janela de anos para backfill historico (atual: 2021-2026).
JANELA_ANOS_DEFAULT = 5

# Fontes suportadas pelo backfill.
FONTES = ("stj", "tjsp")

# Rate limits HTTP (segundos entre chamadas por fonte).
RATE_LIMIT_STJ_SEG = 1.0
RATE_LIMIT_TJSP_SEG = 3.0

# Workers paralelos por fonte (limite superior — respeitando rate limit acima).
WORKERS_STJ = 4
WORKERS_TJSP = 2

# Top N acordaos por mes/area no TJ-SP cjsg (limita volume).
TJSP_TOP_POR_MES_AREA = 30

# Tribunal codes canonicos.
TRIBUNAL_STJ = "STJ"
TRIBUNAL_TJSP = "TJ-SP"

# Termos de busca por area no TJ-SP cjsg (combinados como OR no campo de pesquisa).
# Cada lista representa termos a serem buscados na ementa.
TERMOS_BUSCA_TJSP: dict[str, tuple[str, ...]] = {
    "urbanistico": (
        "regularizacao fundiaria",
        "REURB",
        "parcelamento do solo",
        "loteamento irregular",
        "outorga onerosa",
        "operacao urbana",
    ),
    "imobiliario": (
        "usucapiao",
        "ITBI",
        "incorporacao imobiliaria",
        "compra e venda imovel",
        "alienacao fiduciaria imovel",
        "condominio edilicio",
    ),
    "sucessorio": (
        "inventario",
        "heranca",
        "testamento",
        "holding familiar",
        "partilha de bens",
        "doacao com reserva",
    ),
}
