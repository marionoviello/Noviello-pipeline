# Publicar Reels no Instagram

## Visão geral
Reels é vídeo vertical 9:16 que aparece no feed e no espaço dedicado Reels. Processo de publicação é similar ao carrossel mas com particularidades:
1. Container com `media_type=REELS`
2. Espera de processamento mais longa (vídeo)
3. Possibilidade de thumbnail customizado
4. Compartilhamento opcional no feed

---

## Pré-requisitos
- Page Access Token com `instagram_content_publish`
- `ig-user-id`
- Vídeo MP4 ou MOV: H.264 + AAC, 1080×1920 (9:16), 3s a 15min (recomendado 30-60s), ≤100MB
- Vídeo hospedado em URL pública estável (CDN robusto recomendado)
- Thumbnail JPEG opcional (1080×1920)
- OAB verde + aprovação Mario

---

## Especificações técnicas
| Parâmetro | Valor obrigatório |
|-----------|-------------------|
| `media_type` | `REELS` |
| Aspect ratio | 9:16 (1080×1920) — estrito |
| Codec vídeo | H.264 |
| Codec áudio | AAC |
| Sample rate áudio | 48 kHz |
| Frame rate | 23-60 fps |
| Duração | 3s a 15min (90s recomendado máximo para Reels) |
| Bitrate vídeo | ≥ 5 Mbps |
| Bitrate áudio | ≥ 128 kbps |
| Tamanho do arquivo | ≤ 100 MB |
| Formato | MP4 ou MOV |
| Cor space | Rec. 709 |

---

## Fluxo de publicação

### Etapa 1 — Criar container
```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
?media_type=REELS
&video_url={URL_PUBLICA_HTTPS}
&caption={LEGENDA_URL_ENCODED}
&share_to_feed=true
&thumb_offset=2000
&access_token={page-token}
```

Parâmetros adicionais úteis:
- `share_to_feed=true` — Reels também aparece no feed principal (recomendado)
- `thumb_offset` — milissegundo do vídeo a ser usado como capa (padrão: 0)
- `cover_url` — URL de uma imagem JPEG 1080×1920 para usar como thumbnail (alternativa a thumb_offset)
- `audio_name` — nome do áudio (aparece em "Áudio original de @user")

Resposta:
```json
{ "id": "17841001234567890" }
```

### Etapa 2 — Aguardar processamento (mais longo)

```
GET https://graph.facebook.com/v21.0/{container-id}?fields=status_code,status&access_token={token}
```

Status possíveis:
- `IN_PROGRESS` — processando (esperar)
- `FINISHED` — pronto
- `ERROR` — falhou (ver detalhes em `status`)
- `EXPIRED` — container expirou (>24h sem publicar)

**Atenção**: Reels podem demorar **vários minutos** para processar (especialmente arquivos grandes ou em horários de pico). Polling a cada 5-10 segundos, timeout em 10 minutos. Se EXPIRED, recriar.

### Etapa 3 — Publicar
```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media_publish
?creation_id={CONTAINER_ID}
&access_token={page-token}
```

Resposta: `{ "id": "{media-id}" }`

### Etapa 4 — Obter permalink
```
GET https://graph.facebook.com/v21.0/{media-id}?fields=permalink&access_token={token}
```

---

## Receita Python (esqueleto)

```python
import requests, time, urllib.parse

GRAPH = "https://graph.facebook.com/v21.0"

def publish_reels(ig_user_id, video_url, caption, token, cover_url=None, thumb_offset=2000):
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token,
    }
    if cover_url:
        params["cover_url"] = cover_url
    else:
        params["thumb_offset"] = str(thumb_offset)

    # Criar container
    r = requests.post(f"{GRAPH}/{ig_user_id}/media", params=params)
    r.raise_for_status()
    container_id = r.json()["id"]

    # Esperar FINISHED (timeout maior para vídeo)
    start = time.time()
    while time.time() - start < 600:  # 10 min
        rs = requests.get(f"{GRAPH}/{container_id}", params={
            "fields": "status_code,status",
            "access_token": token,
        })
        data = rs.json()
        if data.get("status_code") == "FINISHED":
            break
        if data.get("status_code") == "ERROR":
            raise Exception(f"Reels container ERROR: {data.get('status')}")
        time.sleep(10)
    else:
        raise TimeoutError("Reels processing timeout")

    # Publicar
    rp = requests.post(f"{GRAPH}/{ig_user_id}/media_publish", params={
        "creation_id": container_id,
        "access_token": token,
    })
    rp.raise_for_status()
    return rp.json()["id"]
```

---

## Casos de uso Noviello

### @novielloadv (B2C 3ª idade)
- **Hook 3 segundos**: pergunta direta ("Sua mãe assinou sem entender?")
- **Desenvolvimento**: tese clara com 1 fato técnico + 1 exemplo concreto
- **CTA verbal**: "leia o artigo no link da bio"
- **Duração ideal**: 30-45s
- **Visual**: Mario à câmera ou screen-record com narração TTS calibrada
- **Música**: instrumental sutil, não compete com voz

### @novielloadv.agro
- **Hook 3 segundos**: alerta forte com cifra ou data ("Sua dívida rural vence em 90 dias? Existe uma saída na lei")
- **Visual**: pode incluir B-roll de campo (lavoura, gado, casa rural) — Veo 3 gera essas cenas
- **Duração ideal**: 30-60s
- **Voz**: ideal Mario; alternativa avatar IA (HeyGen) ou TTS premium (ElevenLabs)

---

## Cenário Mario sem gravar — usando Veo 3 + TTS

Roteiro recomendado:
1. **Hook (3s)**: cena Veo 3 (lavoura, gado, máquina) + texto na tela
2. **Tese (10s)**: cena Veo 3 + voz TTS narrando
3. **Desdobramento (10-15s)**: 2-3 cenas Veo 3 + voz TTS
4. **CTA (5s)**: card final com "leia no link da bio" + logo Noviello

Produção:
- Gerar 4-5 cenas Veo 3 (8s cada)
- Editar no CapCut, DaVinci ou FFmpeg
- Voiceover TTS premium (ElevenLabs com voz clonada de Mario — opcional, mas recomendado para autoridade)
- Música de fundo: bibliotecas YouTube Audio Library ou Epidemic Sound

---

## Erros recorrentes Reels

| Erro | Causa | Correção |
|------|-------|----------|
| `status_code=ERROR` no container | Codec ou resolução fora do padrão | Reencodar com FFmpeg: `ffmpeg -i in.mov -c:v libx264 -c:a aac -b:v 8M -vf scale=1080:1920 out.mp4` |
| Aspect ratio inválido | Vídeo 16:9 | Crop ou recompose para 9:16 |
| Vídeo sem áudio | Trilha de áudio removida na edição | Adicionar áudio (mesmo que seja silêncio) — Reels exige trilha de áudio |
| Demora >10 min para processar | Vídeo muito grande | Reduzir bitrate ou resolução (ainda 1080×1920) |
| Reels publica como vídeo normal | Esqueceu `media_type=REELS` | Sempre setar `media_type=REELS` |
| Thumbnail genérica | `thumb_offset` no momento ruim | Ajustar `thumb_offset` ou usar `cover_url` |

---

## Checklist Reels antes de publicar

```
[ ] Vídeo MP4 H.264 + AAC, 1080×1920, ≤90s, ≤100MB
[ ] Tem trilha de áudio (mesmo silêncio)
[ ] Hospedado em URL pública estável
[ ] Caption ≤ 2.200 chars
[ ] Hashtags ≤ 30
[ ] Hook nos primeiros 3 segundos
[ ] CTA verbal e visual claros
[ ] Disclosure de IA se usado avatar ou TTS
[ ] OAB revisado
[ ] Mario aprovou via WhatsApp
[ ] `media_type=REELS` no container
[ ] `share_to_feed=true` se for cross-feed
```
