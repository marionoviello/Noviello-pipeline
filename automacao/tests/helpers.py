"""Fabrica de pecas de teste: cria uma pasta com MANIFEST.json + assets dummy.

Tambem expoe FakeGmail — um Gmail em memoria para testar watcher/poller/pipeline.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path


class FakeGmail:
    """Gmail em memoria. Modela threads, mensagens e labels."""

    def __init__(self):
        self.threads: dict[str, dict] = {}
        self.enviados: list = []  # EmailMessage enviados (para asserts simples)
        self._seq = 0

    def _novo_id(self, prefixo: str) -> str:
        self._seq += 1
        return f"{prefixo}{self._seq}"

    def send_message(self, mensagem, thread_id=None):
        mid = self._novo_id("msg")
        if thread_id is None:
            thread_id = self._novo_id("thread")
            self.threads[thread_id] = {"messages": []}
        self.threads[thread_id]["messages"].append(
            {"id": mid, "labelIds": ["INBOX"], "_subject": mensagem["Subject"]}
        )
        self.enviados.append(mensagem)
        return {"id": mid, "threadId": thread_id}

    def get_thread(self, thread_id, full=False):
        return {"messages": list(self.threads[thread_id]["messages"])}

    def modify_thread_labels(self, thread_id, adicionar=None, remover=None):
        for m in self.threads[thread_id]["messages"]:
            labels = set(m["labelIds"])
            labels.update(adicionar or [])
            labels.difference_update(remover or [])
            m["labelIds"] = sorted(labels)
        return {}

    def modify_message_labels(self, message_id, adicionar=None, remover=None):
        return {}

    # ---- helpers de teste (simulam acoes do Mario) ----
    def mario_move_label(self, thread_id, label_id):
        self.modify_thread_labels(thread_id, adicionar=[label_id])

    def mario_responde(self, thread_id, texto):
        mid = self._novo_id("reply")
        data = base64.urlsafe_b64encode(texto.encode("utf-8")).decode("ascii")
        self.threads[thread_id]["messages"].append(
            {
                "id": mid,
                "labelIds": ["INBOX"],
                "payload": {"mimeType": "text/plain", "body": {"data": data}},
            }
        )
        return mid

    def assuntos(self, thread_id):
        return [m.get("_subject", "") for m in self.threads[thread_id]["messages"]]

_JPEG_FAKE = b"\xff\xd8\xff\xe0" + b"conteudo-falso-de-imagem" * 4


def criar_peca_dir(
    base,
    peca_id: str = "2026-S20-teste",
    *,
    status: str = "pronta_para_aprovacao",
    oab: str = "aprovado",
    marca: str = "v2-conforme",
    canais=("instagram",),
    quebrar_path: bool = False,
) -> Path:
    """Cria <base>/<peca_id>/MANIFEST.json + assets. Devolve o path do MANIFEST."""
    d = Path(base) / peca_id
    d.mkdir(parents=True, exist_ok=True)
    ativos: dict = {}

    if "instagram" in canais:
        img1 = d / "slide1.jpg"
        img1.write_bytes(_JPEG_FAKE)
        img2 = d / "slide2.jpg"
        img2.write_bytes(_JPEG_FAKE)
        leg = d / "legenda.txt"
        leg.write_text("Legenda de teste do carrossel.", encoding="utf-8")
        ativos["instagram"] = {
            "imagens": [str(img1), str(img2)],
            "legenda": str(leg),
            "hashtags": ["#DireitoImobiliario", "#Noviello"],
            "tipo_post": "carrossel",
        }

    if "wordpress" in canais:
        html = d / "artigo.html"
        html.write_text("<p>Conteudo do artigo.</p>", encoding="utf-8")
        destaque = d / "destaque.jpg"
        destaque.write_bytes(_JPEG_FAKE)
        ativos["wordpress"] = {
            "site_destino": "noviello",
            "titulo": "Artigo de teste",
            "slug": "artigo-de-teste",
            "categoria": "Imobiliario",
            "tags": ["certidoes"],
            "conteudo_html": str(html),
            "imagem_destaque": str(destaque),
            "meta_description": "Descricao de teste.",
            "status_alvo": "publish",
        }

    if "linkedin" in canais:
        li_img = d / "li.jpg"
        li_img.write_bytes(_JPEG_FAKE)
        li_txt = d / "li.txt"
        li_txt.write_text("Texto do post LinkedIn.", encoding="utf-8")
        ativos["linkedin"] = {
            "imagem": str(li_img),
            "texto": str(li_txt),
            "url_artigo_wp": "https://noviello.adv.br/artigo-de-teste",
        }

    if quebrar_path and "instagram" in ativos:
        ativos["instagram"]["imagens"].append(str(d / "nao-existe.jpg"))

    manifest = {
        "peca_id": peca_id,
        "tipo": "carrossel",
        "pilar": "Direito Imobiliario",
        "titulo_curto": "4 certidoes inegociaveis",
        "data_publicacao_alvo": "2026-05-20T10:00:00-03:00",
        "status": status,
        "validacoes": {"oab_205": oab, "marca": marca, "ortografia": "ok"},
        "ativos": ativos,
        "cross_link": {"ig_para_wp": True, "li_para_wp": True, "linktree_topo": True},
    }
    mpath = d / "MANIFEST.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return mpath
