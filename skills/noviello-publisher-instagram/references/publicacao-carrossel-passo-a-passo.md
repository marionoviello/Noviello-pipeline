# Publicar carrossel no Instagram — passo a passo

## Visão geral
Publicar carrossel é um processo de **3 fases**:
1. Criar containers de imagem (1 por slide, com `is_carousel_item=true`)
2. Criar container de carrossel (agrupa os IDs anteriores, `media_type=CAROUSEL`)
3. Publicar o container do carrossel (`/media_publish`)

Cada fase exige aguardar status do container ficar `FINISHED` antes de seguir.

---

## Pré-requisitos
- Page Access Token válido com `instagram_content_publish`
- `ig-user-id` do perfil-alvo
- 2 a 10 imagens já hospedadas em URL pública (ver `hospedagem-de-imagens.md`)
- Validação de dimensão e formato concluída (ver `formatos-e-dimensoes.md`)
- Revisão OAB com status verde ou amarelo (ver `compliance-oab-pre-publicacao.md`)
- Aprovação de Mario via WhatsApp (ver `aprovacao-whatsapp.md`)

---

## Fase 1 — Criar containers de cada slide

Para **cada slide**, fazer:

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
?image_url={URL_PUBLICA}
&is_carousel_item=true
&access_token={page-token}
```

Resposta:
```json
{ "id": "17841001234567890" }
```

Esse `id` é o `container_id` do slide. **Guardar todos os IDs em ordem.**

### Validar status do container
```
GET https://graph.facebook.com/v21.0/{container-id}?fields=status_code&access_token={token}
```

Estados possíveis:
- `IN_PROGRESS` — esperar mais
- `FINISHED` — pronto para próxima fase
- `ERROR` — investigar (provavelmente URL inacessível)
- `EXPIRED` — container expirou (válido por 24h); recriar

Recomendação: **polling a cada 2 segundos**, timeout em 60 segundos. Para imagem, costuma ficar pronto em 5-15 segundos.

---

## Fase 2 — Criar container do carrossel

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
?media_type=CAROUSEL
&children={id1},{id2},{id3},...{idN}
&caption={LEGENDA_URL_ENCODED}
&access_token={page-token}
```

Notas:
- `children`: lista de IDs separados por vírgula, **na ordem em que devem aparecer**
- `caption`: legenda completa, URL-encoded — quebras de linha como `%0A`
- Mínimo 2, máximo 10 children

Resposta:
```json
{ "id": "17841009876543210" }
```

Esse é o `creation_id` do carrossel — guardar para a fase 3.

Validar status com o mesmo `GET /{id}?fields=status_code`.

---

## Fase 3 — Publicar o carrossel

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media_publish
?creation_id={CAROUSEL_CONTAINER_ID}
&access_token={page-token}
```

Resposta:
```json
{ "id": "17841005555555555" }
```

Esse é o `media_id` do post publicado. Para obter URL permanente:

```
GET https://graph.facebook.com/v21.0/{media-id}?fields=permalink&access_token={token}
```

Retorna:
```json
{
  "permalink": "https://www.instagram.com/p/Cxxxxxx/",
  "id": "..."
}
```

---

## Receita completa em Python (esqueleto)

```python
import requests, time, urllib.parse

GRAPH = "https://graph.facebook.com/v21.0"

def create_image_container(ig_user_id, image_url, token, is_carousel=False):
    params = {
        "image_url": image_url,
        "access_token": token,
    }
    if is_carousel:
        params["is_carousel_item"] = "true"
    r = requests.post(f"{GRAPH}/{ig_user_id}/media", params=params)
    r.raise_for_status()
    return r.json()["id"]

def wait_finished(container_id, token, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{GRAPH}/{container_id}", params={
            "fields": "status_code",
            "access_token": token,
        })
        status = r.json().get("status_code")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise Exception(f"Container {container_id} ERROR")
        time.sleep(2)
    raise TimeoutError(f"Container {container_id} timeout")

def create_carousel_container(ig_user_id, children_ids, caption, token):
    r = requests.post(f"{GRAPH}/{ig_user_id}/media", params={
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": token,
    })
    r.raise_for_status()
    return r.json()["id"]

def publish(ig_user_id, creation_id, token):
    r = requests.post(f"{GRAPH}/{ig_user_id}/media_publish", params={
        "creation_id": creation_id,
        "access_token": token,
    })
    r.raise_for_status()
    return r.json()["id"]

def get_permalink(media_id, token):
    r = requests.get(f"{GRAPH}/{media_id}", params={
        "fields": "permalink",
        "access_token": token,
    })
    return r.json()["permalink"]

# --- USO ---
def publish_carousel(ig_user_id, image_urls, caption, token):
    children = []
    for url in image_urls:
        cid = create_image_container(ig_user_id, url, token, is_carousel=True)
        wait_finished(cid, token)
        children.append(cid)
    carousel_id = create_carousel_container(ig_user_id, children, caption, token)
    wait_finished(carousel_id, token)
    media_id = publish(ig_user_id, carousel_id, token)
    permalink = get_permalink(media_id, token)
    return {"media_id": media_id, "permalink": permalink}
```

---

## Alt-text por slide

Alt-text **não é definido no momento da criação do container** — é definido por chamada à parte:

```
POST https://graph.facebook.com/v21.0/{slide-container-id}
?alt_text={ALT_TEXT_URL_ENCODED}
&access_token={page-token}
```

**Atenção**: a documentação Meta sobre alt-text em carrossel é instável. Em algumas versões da API, o `alt_text` precisa ser passado na criação do container individual. Validar comportamento na versão atual antes de produção.

Alternativa: usar `accessibility_caption` no momento do container (Graph API v19+).

---

## Erros recorrentes e correção

| Erro | Causa | Correção |
|------|-------|----------|
| `Error #2207009 Media format invalid` | PNG enviado | Converter para JPEG antes do upload no WP |
| `Error #110 Invalid parameter` na fase 2 | Algum container ainda em IN_PROGRESS | Aguardar TODOS estarem FINISHED |
| `Error #100 children must be at least 2` | Carrossel com 1 item | Validar antes de criar carousel container |
| Container EXPIRED após 24h | Demorou demais | Recriar container; containers duram só 24h |
| Carrossel publica em ordem errada | `children` enviado fora de ordem | Garantir ordem na lista |
| Caption truncada | > 2.200 chars | Cortar antes de enviar |
| Post sem hashtag | Hashtag dentro de comentário, não legenda | Mover hashtags para o final da legenda |

---

## Checklist final antes do disparo

```
[ ] IG user ID correto (perfil-alvo)
[ ] Token válido e com permissions
[ ] 2-10 imagens hospedadas em URL pública (HTTPS)
[ ] Cada imagem com aspecto 4:5 a 1.91:1, JPEG, ≤8MB
[ ] Legenda ≤ 2.200 chars
[ ] Hashtags ≤ 30 totais
[ ] Alt-texts preparados (≤ 1.000 chars cada)
[ ] OAB revisado (verde ou amarelo com nota)
[ ] Mario aprovou via WhatsApp
[ ] Disclosure de IA presente se aplicável
[ ] Hora de publicação dentro da janela editorial (não fora de horário comercial sem motivo)
```
