"""Radar de Julgados — acervo local de julgados STJ + TJ-SP indexado em SQLite FTS5.

Modulos:
- config: constantes (areas-alvo, janela de anos, rate limits)
- models: dataclasses Julgado / Descartado
- db: conexao + schema + migrations
- feeds_stj: descoberta + download + parse de Informativos STJ
- feeds_tjsp: query API ESAJ cjsg + parse
- parser: extracao via pypdf + Anthropic
- indexer: insert/dedup/update FTS
- searcher: API de busca (full-text + filtros)
- backfill: orquestrador do backfill historico (python -m src.julgado_radar.backfill)
"""
