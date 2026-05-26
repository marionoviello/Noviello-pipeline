"""Gera card visual do Julgado da Semana (STJ REsp 2.215.421) e publica
em Instagram + LinkedIn como single-image post.

Dados extraidos do PDF anexado pelo Mario. Blog vai separado (Mario faz manual).
"""

from __future__ import annotations

import html as _html
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for env_file in (ROOT / ".env", ROOT.parent / ".env"):
    if env_file.exists():
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---- Dados estruturados do julgado --------------------------------------

JULGADO = {
    "area": "Direito Imobiliário",
    "orgao": "STJ",
    "orgao_completo": "Terceira Turma do STJ",
    "tese": "Recibo de compra basta como justo título na usucapião ordinária",
    "processo": "REsp 2.215.421/SE",
    "data_julgamento": "10/03/2026",
    "relator": "Min. Nancy Andrighi",
    "relator_curto": "Min. Nancy Andrighi",
    "turma": "3ª Turma · Unanimidade",
    "citacao_principal": (
        "O justo título deve ser interpretado de forma ampla, "
        "de modo a abranger elementos que permitam concluir "
        "pela existência do intento de transmissão da propriedade."
    ),
    "label_doc": "Documento Analisado",
    "legenda_doc": "Recibo de compra e venda analisado pelo STJ",
    "fundamentos": [
        {"fonte": "Art. 1.242 CC", "texto": "Usucapião ordinária — posse mansa e pacífica + justo título + boa-fé por 10 anos (ou 5 com requisitos do parágrafo único)."},
        {"fonte": "Súmula 237 STF", "texto": "O usucapião pode ser arguido em defesa — o direito já existe quando preenchidos os requisitos."},
        {"fonte": "REsp 652.449/SP", "texto": "Justo título = ato ou fato jurídico que, em tese, possa transmitir a propriedade, ainda que defeituoso (precedente da 3ª Turma)."},
        {"fonte": "Função social", "texto": "Interpretação extensiva concretiza a função social da propriedade e o direito fundamental social à moradia."},
    ],
    "tema_rodape": "Usucapião Ordinária",
    "tema_rodape_sub": "Recibo de Compra como Justo Título",
    "assinatura": "T. M. S.",
    # Subtítulo varia por canal — pra LinkedIn (B2B), evitar "Direito Sênior"
    # (terminologia editorial pro IG B2C). Pro card de LinkedIn, usar área
    # técnica do julgado.
    "subtitulo_marca_li": "Advocacia · Imobiliário e Sucessório",
    "subtitulo_marca_ig": "Advocacia · Direito Sênior",
}


def montar_html(dados: dict, canal: str = "li") -> str:
    """Monta HTML do card. `canal` define o subtitulo da marca:
    - 'li' (LinkedIn): area tecnica do julgado (sem "Direito Senior")
    - 'ig' (Instagram): "Advocacia · Direito Senior" (terminologia B2C)
    """
    template = (ROOT / "templates" / "julgado-card.html").read_text(encoding="utf-8")

    fundamentos_html = "\n".join(
        f'<div class="fund-item"><div class="fonte">{_html.escape(f["fonte"])}</div>'
        f'<div class="texto">{_html.escape(f["texto"])}</div></div>'
        for f in dados["fundamentos"]
    )

    # subtitulo da marca depende do canal
    subtitulo = dados.get(f"subtitulo_marca_{canal}", "Advocacia")

    out = template
    for k, v in dados.items():
        if k == "fundamentos":
            continue
        if k.startswith("subtitulo_marca_"):
            continue  # tratado abaixo
        out = out.replace("{" + k + "}", _html.escape(str(v)) if k != "citacao_principal" else _html.escape(v))
    out = out.replace("{fundamentos_html}", fundamentos_html)
    out = out.replace("{subtitulo_marca}", _html.escape(subtitulo))
    return out


def renderizar(html: str, destino: Path) -> Path:
    from playwright.sync_api import sync_playwright
    # Copia logo pro mesmo diretorio do HTML (path relativo no img src)
    import shutil
    logo_src = ROOT / "templates" / "logo-noviello-branco.png"
    logo_dst = destino.parent / "logo-noviello-branco.png"
    if logo_src.exists():
        shutil.copy(logo_src, logo_dst)
    arq_html = destino.with_suffix(".html")
    arq_html.write_text(html, encoding="utf-8")
    arq_jpg = destino.with_suffix(".jpg")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        page.goto(f"file://{arq_html.as_posix()}", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=str(arq_jpg), full_page=False, type="jpeg", quality=92,
                        clip={"x": 0, "y": 0, "width": 1080, "height": 1080})
        browser.close()
    return arq_jpg


# ---- Legendas / Posts -----------------------------------------------------

LEGENDA_IG = """STJ revoluciona usucapião: recibo de compra basta como justo título.

A 3ª Turma do STJ, sob relatoria da Min. Nancy Andrighi, decidiu por unanimidade em 10/03/2026: o recibo de compra e venda do imóvel basta para preencher o requisito de "justo título" na usucapião ordinária (art. 1.242 CC).

A tese rompe com a leitura tradicional. Antes, exigia-se documento formalmente apto à transferência (escritura pública defeituosa, contrato de promessa, venda a non domino). Agora, qualquer elemento que demonstre a intenção inequívoca de transmissão da propriedade serve.

Por quê importa: milhares de famílias brasileiras adquiriram imóveis informalmente, com recibo simples, sem escritura. Antes desse julgado, regularização exigia outros caminhos (adjudicação compulsória, REURB). Agora, a usucapião ordinária se abre como via direta.

REsp 2.215.421/SE. Caso real: Maria do Carmo, Aracaju/SE, comprou imóvel por R$ 16 mil em 2014, sem escritura. 1ª instância e TJ-SE negaram. Defensoria Pública levou ao STJ e ganhou.

Se você comprou ou herdou imóvel "no recibo" e ocupa há 10+ anos, esse julgado abre caminho para regularizar a propriedade em seu nome.

⚠️ Este conteúdo é educativo e não substitui análise individualizada do seu caso por advogado especializado. Cada situação patrimonial tem particularidades que exigem orientação técnica.

#usucapiao #direitoimobiliario #regularizacaodeimoveis #stj #justotitulo #planejamentopatrimonial #novielloadv #advocaciasenior #direitosenior #publicosenior"""

POST_LINKEDIN = """STJ acaba de mudar a leitura do justo título na usucapião ordinária. Quem trabalha com regularização de imóveis precisa conhecer esse julgado.

REsp 2.215.421/SE, 3ª Turma, relatoria da Min. Nancy Andrighi, julgado em 10/03/2026, unânime.

A tese: o recibo de compra e venda do imóvel basta para preencher o requisito do justo título no art. 1.242 do Código Civil. Não precisa de escritura pública defeituosa, contrato de promessa registrado nem venda a non domino. Basta o elemento que demonstre a intenção de transmissão da propriedade.

Como a Ministra colocou: "o justo título deve ser interpretado de forma ampla, de modo a abranger elementos que permitam concluir pela existência do intento de transmissão da propriedade".

O fundamento é dogmático e político: dogmático porque o justo título nunca foi o documento em si, mas o fundamento do direito (a Ministra cita Pontes de Miranda e Cristiano Chaves); político porque a interpretação restritiva esvaziava o instituto, já que a parte poderia regularizar por outras vias (adjudicação compulsória). Soma-se a função social da propriedade e o direito fundamental à moradia (art. 6º CF).

Caso concreto: Maria do Carmo, Aracaju/SE, comprou imóvel de R$ 16 mil em 2014, com recibo simples. Ocupou mansa e pacificamente por mais de 7 anos até ajuizar. Sentença de improcedência. TJ-SE manteve. STJ reformou.

Impacto prático para o advogado imobiliário: amplia drasticamente o universo de imóveis usucapíveis pela via ordinária. Casos que antes exigiam usucapião extraordinária (15 anos sem justo título) agora podem ser resolvidos em 10 anos pela ordinária. Em situações com posse-trabalho/moradia, em 5 anos pelo parágrafo único.

Vale revisitar a carteira ativa: clientes com imóveis "no recibo" há mais de 10 anos têm um caminho mais curto agora.

Análise completa no blog: https://noviello.adv.br/usucapiao-ordinaria-stj-confirma-recibo-de-compra-e-venda-como-justo-titulo/

#usucapiao #direitoimobiliario #stj"""


def publicar_ig(jpg_path: Path, legenda: str) -> str:
    import httpx
    from src.wp_client import WordPressClient

    token = os.environ["META_PAGE_TOKEN"]
    ig_id = os.environ["IG_USER_ID_NOVIELLOADV"]
    HOST = "https://graph.facebook.com/v21.0"

    # 1. sobe pro WP pra ter URL publica
    wp = WordPressClient(os.environ["WP_USER"], {"noviello": os.environ["WP_APP_PASSWORD_NOVIELLO"]})
    midia = wp.upload_media(str(jpg_path), "noviello")
    url = midia["source_url"]
    print(f"  WP url: {url}")

    # 2. cria container single image
    r = httpx.post(f"{HOST}/{ig_id}/media",
        data={"image_url": url, "caption": legenda, "access_token": token}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"create container falhou: {r.text[:300]}")
    cid = r.json()["id"]
    print(f"  container: {cid}")

    # 3. espera 30s (single image é mais rapido que carrossel)
    print("  aguardando 30s...")
    time.sleep(30)

    # 4. publica
    r = httpx.post(f"{HOST}/{ig_id}/media_publish",
        data={"creation_id": cid, "access_token": token}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"publish falhou: {r.text[:300]}")
    media_id = r.json()["id"]
    print(f"  publicado IG: {media_id}")
    return media_id


def publicar_linkedin(jpg_path: Path, texto: str) -> str:
    """Publica single-image post no LinkedIn via REST v202506."""
    import httpx

    token = os.environ["LI_ACCESS_TOKEN"]
    person = os.environ["LI_PERSON_URN"]
    if not person.startswith("urn:li:person:"):
        person = f"urn:li:person:{person}"

    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": "202506",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # 1. cria asset de imagem
    r = httpx.post("https://api.linkedin.com/rest/images?action=initializeUpload",
        headers=headers,
        json={"initializeUploadRequest": {"owner": person}}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"init upload falhou {r.status_code}: {r.text[:300]}")
    val = r.json()["value"]
    upload_url = val["uploadUrl"]
    image_urn = val["image"]
    print(f"  asset URN: {image_urn}")

    # 2. faz upload do jpg
    with open(jpg_path, "rb") as f:
        r = httpx.put(upload_url, content=f.read(), headers={"Authorization": f"Bearer {token}"}, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"upload falhou {r.status_code}: {r.text[:300]}")
    print("  upload OK")

    # 3. cria post
    post_body = {
        "author": person,
        "commentary": texto,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "media": {
                "id": image_urn,
            },
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    r = httpx.post("https://api.linkedin.com/rest/posts",
        headers={**headers, "Content-Type": "application/json"},
        json=post_body, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"post create falhou {r.status_code}: {r.text[:500]}")

    post_id = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id", "")
    print(f"  publicado LI: {post_id}")
    return post_id


# ---- Main -----------------------------------------------------------------

def main():
    destino_base = ROOT / "samples" / "julgado-card-stj-2215421"

    # Renderiza 2 cards: 1 pra LI (subtitulo neutro) e 1 pra IG (subtitulo Senior)
    print("[1/3] Montando HTML + renderizando 2 cards (LI + IG)...")
    jpg_li = renderizar(montar_html(JULGADO, "li"), destino_base.with_name("julgado-card-li"))
    jpg_ig = renderizar(montar_html(JULGADO, "ig"), destino_base.with_name("julgado-card-ig"))
    print(f"  LI: {jpg_li.name}  ({jpg_li.stat().st_size:,} bytes)")
    print(f"  IG: {jpg_ig.name}  ({jpg_ig.stat().st_size:,} bytes)")

    if "--so-render" in sys.argv:
        print("--so-render: parando antes de publicar.")
        return

    if "--so-li" in sys.argv:
        print("\n[2/2] Publicando LinkedIn (IG pulado a pedido)...")
        try:
            li_id = publicar_linkedin(jpg_li, POST_LINKEDIN)
            print(f"  >>> LI OK: {li_id} <<<")
        except Exception as exc:
            print(f"  ERRO LI: {exc}")
            import traceback; traceback.print_exc()
        return

    print("\n[2/3] Publicando IG...")
    try:
        ig_id = publicar_ig(jpg_ig, LEGENDA_IG)
        print(f"  >>> IG OK: {ig_id} <<<")
    except Exception as exc:
        print(f"  ERRO IG: {exc}")

    print("\n[3/3] Publicando LinkedIn...")
    try:
        li_id = publicar_linkedin(jpg_li, POST_LINKEDIN)
        print(f"  >>> LI OK: {li_id} <<<")
    except Exception as exc:
        print(f"  ERRO LI: {exc}")

    print("\nPronto.")


if __name__ == "__main__":
    main()
