"""Testa o publisher LinkedIn diretamente: modo texto puro x modo carrossel PDF.

Mocka as chamadas HTTP (_post_json, _put_bytes, _gerar_pdf) — sem rede.
"""

import json
from types import SimpleNamespace

import pytest

import src.publishers.linkedin as li_pub
from src.manifest import carregar_manifest
from src.publish_result import PULADO
from tests.helpers import criar_peca_dir


def _cfg():
    return SimpleNamespace(linkedin={"access_token": "tok", "person_urn": "u123"})


def _logger():
    return SimpleNamespace(info=lambda *a, **k: None)


class _FakeResp:
    def __init__(self, json_data=None, restli_id=""):
        self._json = json_data or {}
        self.headers = {"x-restli-id": restli_id} if restli_id else {}

    def json(self):
        return self._json


def _patch_post(monkeypatch):
    """Mocka _post_json; devolve a lista de chamadas (caminho, corpo)."""
    chamadas = []

    def fake_post(caminho, token, corpo):
        chamadas.append((caminho, corpo))
        if "documents" in caminho:
            return _FakeResp(json_data={"value": {
                "document": "urn:li:document:1",
                "uploadUrl": "https://upload.example/doc",
            }})
        return _FakeResp(restli_id="urn:li:share:999")

    monkeypatch.setattr(li_pub, "_post_json", fake_post)
    return chamadas


def _set_formato(mpath, formato: str):
    """Injeta ativos.linkedin.formato no MANIFEST ja criado."""
    dados = json.loads(mpath.read_text(encoding="utf-8"))
    dados["ativos"]["linkedin"]["formato"] = formato
    mpath.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


# ===== Modo texto puro =====

def test_publish_texto_puro_com_flag(tmp_path, monkeypatch):
    """formato='texto' -> POST em /posts SEM content.media."""
    mpath = criar_peca_dir(tmp_path / "p", canais=("linkedin",))
    _set_formato(mpath, "texto")
    peca = carregar_manifest(mpath)
    chamadas = _patch_post(monkeypatch)

    r = li_pub.publish(peca, _cfg(), _logger())

    assert r.ok is True
    # so 1 chamada: o POST do post (sem initializeUpload de documento)
    assert len(chamadas) == 1
    caminho, corpo = chamadas[0]
    assert caminho == "posts"
    assert corpo["commentary"] == "Texto do post LinkedIn."
    assert "content" not in corpo  # SEM media/documento
    assert corpo["lifecycleState"] == "PUBLISHED"
    assert "linkedin.com/feed/update/" in r.url


def test_publish_texto_puro_fallback_sem_slides(tmp_path, monkeypatch):
    """Sem flag, mas tem texto e nao tem slides -> cai em texto puro."""
    mpath = criar_peca_dir(tmp_path / "p", canais=("linkedin",))  # sem instagram = sem slides
    peca = carregar_manifest(mpath)
    chamadas = _patch_post(monkeypatch)

    r = li_pub.publish(peca, _cfg(), _logger())

    assert r.ok is True
    assert len(chamadas) == 1
    assert chamadas[0][0] == "posts"
    assert "content" not in chamadas[0][1]


def test_publish_texto_puro_sem_conteudo_pula(tmp_path, monkeypatch):
    """formato=texto mas arquivo de texto vazio -> pulado."""
    mpath = criar_peca_dir(tmp_path / "p", canais=("linkedin",))
    _set_formato(mpath, "texto")
    # zera o texto
    dados = json.loads(mpath.read_text(encoding="utf-8"))
    from pathlib import Path
    Path(dados["ativos"]["linkedin"]["texto"]).write_text("", encoding="utf-8")
    peca = carregar_manifest(mpath)
    _patch_post(monkeypatch)

    r = li_pub.publish(peca, _cfg(), _logger())
    assert r.status == PULADO
    assert "texto" in r.motivo.lower()


# ===== Modo carrossel (nao-regressao) =====

def test_publish_carrossel_ainda_usa_documento(tmp_path, monkeypatch):
    """Peca com slides (instagram) + linkedin -> modo carrossel com content.media."""
    mpath = criar_peca_dir(tmp_path / "p", canais=("instagram", "linkedin"))
    peca = carregar_manifest(mpath)
    chamadas = _patch_post(monkeypatch)
    monkeypatch.setattr(li_pub, "_put_bytes", lambda url, token, dados: None)

    def fake_pdf(slides, destino):
        destino.write_bytes(b"%PDF-fake")
        return destino
    monkeypatch.setattr(li_pub, "_gerar_pdf", fake_pdf)

    r = li_pub.publish(peca, _cfg(), _logger())

    assert r.ok is True
    caminhos = [c[0] for c in chamadas]
    assert any("documents" in c for c in caminhos)  # initializeUpload aconteceu
    assert "posts" in caminhos
    corpo_post = [c[1] for c in chamadas if c[0] == "posts"][0]
    assert "content" in corpo_post  # COM media/documento
    assert corpo_post["content"]["media"]["id"] == "urn:li:document:1"


def test_publish_carrossel_explicito_com_flag(tmp_path, monkeypatch):
    """formato='carrossel' forca o modo documento mesmo com texto presente."""
    mpath = criar_peca_dir(tmp_path / "p", canais=("instagram", "linkedin"))
    _set_formato(mpath, "carrossel")
    peca = carregar_manifest(mpath)
    chamadas = _patch_post(monkeypatch)
    monkeypatch.setattr(li_pub, "_put_bytes", lambda url, token, dados: None)
    monkeypatch.setattr(li_pub, "_gerar_pdf",
                        lambda slides, destino: (destino.write_bytes(b"%PDF"), destino)[1])

    r = li_pub.publish(peca, _cfg(), _logger())
    assert r.ok is True
    assert any("documents" in c[0] for c in chamadas)


# ===== Caso vazio =====

def test_publish_sem_ativos_linkedin_pula(tmp_path, monkeypatch):
    mpath = criar_peca_dir(tmp_path / "p", canais=("instagram",))  # sem linkedin
    peca = carregar_manifest(mpath)
    _patch_post(monkeypatch)
    r = li_pub.publish(peca, _cfg(), _logger())
    assert r.status == PULADO
    assert "ativos" in r.motivo.lower()
