"""Testes do blog_corpus: limpeza HTML, cache 24h, fallback offline."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from src.blog_corpus import _formatar_para_prompt, _limpar_html, pegar_corpus_blog


def test_limpar_html_remove_tags():
    assert _limpar_html("<p>Texto</p><br/><strong>negrito</strong>") == "Texto negrito"


def test_limpar_html_decodifica_entidades():
    assert "Cláusula" in _limpar_html("<p>Cl&aacute;usula</p>")


def test_limpar_html_normaliza_espacos():
    assert _limpar_html("<p>a   b\n\n\nc</p>") == "a b c"


def test_limpar_html_trunca_no_limite_de_palavra():
    longo = "<p>" + ("palavra " * 200) + "</p>"
    saida = _limpar_html(longo, limite=50)
    assert len(saida) <= 51  # +1 pelo "…"
    assert saida.endswith("…")
    assert not saida.endswith(" …")  # nao quebra no meio da palavra


def _fake_post(idx, titulo, conteudo):
    return {
        "id": 1000 + idx,
        "slug": f"post-{idx}",
        "date": f"2026-05-{20-idx:02d}T10:00:00",
        "title": {"rendered": titulo},
        "content": {"rendered": conteudo},
        "categories": [],
    }


def test_busca_e_cacheia(tmp_path, monkeypatch):
    chamadas = []

    def fake_fetch(base, auth, n):
        chamadas.append(1)
        return [_fake_post(0, "Artigo A", "<p>conteudo A</p>")]

    texto1 = pegar_corpus_blog(
        tmp_path, "https://exemplo", ("u", "p"), top_n=5, fetcher=fake_fetch
    )
    assert "Artigo A" in texto1
    assert (tmp_path / "corpus-cache.json").exists()

    # segunda chamada nao deve fazer fetch (cache fresco)
    texto2 = pegar_corpus_blog(
        tmp_path, "https://exemplo", ("u", "p"), top_n=5, fetcher=fake_fetch
    )
    assert texto2 == texto1
    assert len(chamadas) == 1  # nao buscou de novo


def test_cache_expirado_re_busca(tmp_path):
    cache_path = tmp_path / "corpus-cache.json"
    # cache de ontem (>24h)
    velho = (_dt.datetime.now().astimezone() - _dt.timedelta(hours=48))
    cache_path.write_text(
        json.dumps(
            {"atualizado_em": velho.isoformat(timespec="seconds"), "texto": "antigo"}
        ),
        encoding="utf-8",
    )

    def fake_fetch(base, auth, n):
        return [_fake_post(0, "Novo Artigo", "<p>fresco</p>")]

    texto = pegar_corpus_blog(
        tmp_path, "https://exemplo", ("u", "p"), top_n=5, fetcher=fake_fetch
    )
    assert "Novo Artigo" in texto
    assert "antigo" not in texto


def test_falha_de_rede_usa_cache_antigo(tmp_path):
    velho = (_dt.datetime.now().astimezone() - _dt.timedelta(hours=72))
    (tmp_path / "corpus-cache.json").write_text(
        json.dumps(
            {"atualizado_em": velho.isoformat(timespec="seconds"), "texto": "salvo"}
        ),
        encoding="utf-8",
    )

    def fetch_quebra(base, auth, n):
        raise ConnectionError("simulada")

    texto = pegar_corpus_blog(
        tmp_path, "https://exemplo", ("u", "p"), top_n=5, fetcher=fetch_quebra
    )
    # fallback: cache antigo
    assert texto == "salvo"


def test_falha_de_rede_sem_cache_devolve_vazio(tmp_path):
    def fetch_quebra(base, auth, n):
        raise ConnectionError("simulada")

    texto = pegar_corpus_blog(
        tmp_path, "https://exemplo", ("u", "p"), top_n=5, fetcher=fetch_quebra
    )
    assert texto == ""


def test_formatar_inclui_titulo_slug_e_excerpt():
    artigos = [
        {
            "id": 1, "slug": "abc", "data": "2026-05-19",
            "titulo": "Titulo Bonito", "excerpt": "Trecho qualquer.",
        }
    ]
    texto = _formatar_para_prompt(artigos)
    assert "## Titulo Bonito" in texto
    assert "slug:** abc" in texto
    assert "2026-05-19" in texto
    assert "Trecho qualquer." in texto


def test_cache_corrompido_re_busca(tmp_path):
    (tmp_path / "corpus-cache.json").write_text("{NAO E JSON VALIDO", encoding="utf-8")

    def fake_fetch(base, auth, n):
        return [_fake_post(0, "Recuperado", "<p>x</p>")]

    texto = pegar_corpus_blog(
        tmp_path, "https://exemplo", ("u", "p"), top_n=5, fetcher=fake_fetch
    )
    assert "Recuperado" in texto


def test_corpus_vazio_devolve_string_vazia():
    assert _formatar_para_prompt([]) == ""
