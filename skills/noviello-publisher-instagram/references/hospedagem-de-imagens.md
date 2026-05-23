# Hospedagem de imagens — URL pública para Graph API

## Por que é necessária

A Graph API do Instagram **não aceita upload binário** de imagem. Toda chamada para criar um container de mídia (`POST /media`) exige o parâmetro `image_url` (ou `video_url` para Reels) — uma URL HTTPS pública acessível **durante o tempo de processamento da Meta** (5 segundos a 5 minutos para imagem, até várias horas para vídeo).

Se a URL não estiver acessível quando a Meta tentar baixar a mídia, o container falha com `Error #100 Image URL not accessible`.

---

## Opções avaliadas — Noviello

| Opção | Custo | Setup | Velocidade | Persistência | Recomendado para |
|-------|-------|-------|------------|--------------|-------------------|
| **WordPress (uploads)** | 0 (já pago) | Baixo | Alta | Indefinida | **Padrão Noviello** |
| Amazon S3 + CloudFront | US$ 1-3/mês | Médio | Muito alta | Indefinida | Escala grande |
| Google Drive (link público) | 0 | Baixo | Média | Indefinida | Backup |
| Imgur API | 0 | Baixo | Alta | 6 meses+ | Teste rápido |
| Bucket Backblaze B2 | US$ 0.005/GB | Médio | Alta | Indefinida | Alternativa S3 |

**Decisão Noviello**: **WordPress como host primário**. Razões:
1. Já está pago e operado
2. Aceita upload via REST API (`POST /wp-json/wp/v2/media`)
3. URL pública e estável
4. Aparece nas mídias do WP (gestão visual)
5. Permite reaproveitamento em futuros artigos
6. CDN do hosting (se houver) acelera

---

## Estrutura de pastas recomendada

```
/wp-content/uploads/ig/
    /novielloadv/
        /2026/05/slide-1.jpg
        /2026/05/slide-2.jpg
    /novielloadv_agro/
        /2026/05/post-credito-rural.jpg
        /2026/05/reels-prorrogacao.mp4
```

Organização por perfil + ano + mês facilita auditoria e backup.

---

## Upload via REST API WordPress

### Autenticação
WordPress REST API requer autenticação. Opções:
- **Application Password** (recomendado): gerado em `Usuários → Perfil → Application Passwords`. Header: `Authorization: Basic base64(user:app-password)`
- JWT Plugin (mais flexível)
- OAuth2 (overkill para uso interno)

### Endpoint
```
POST https://noviello.adv.br/wp-json/wp/v2/media
Content-Type: image/jpeg
Authorization: Basic {base64}
Content-Disposition: attachment; filename="slide-1.jpg"

[binary]
```

### Resposta
```json
{
  "id": 12345,
  "source_url": "https://noviello.adv.br/wp-content/uploads/2026/05/slide-1.jpg",
  "media_details": { ... }
}
```

O `source_url` é o que vai para a Graph API.

### Snippet Python

```python
import requests, base64

def upload_to_wp(filepath, wp_user, wp_app_password, wp_url):
    auth = base64.b64encode(f"{wp_user}:{wp_app_password}".encode()).decode()
    headers = {
        "Content-Type": "image/jpeg",
        "Authorization": f"Basic {auth}",
        "Content-Disposition": f'attachment; filename="{filepath.split("/")[-1]}"'
    }
    with open(filepath, "rb") as f:
        r = requests.post(f"{wp_url}/wp-json/wp/v2/media", headers=headers, data=f.read())
    r.raise_for_status()
    return r.json()["source_url"]
```

---

## Boa prática — manter URL pública por 24h+

Mesmo que a Meta processe a mídia em segundos, **não delete o arquivo antes de 24h**. Razões:
- Reprocessamento (retry) em caso de erro
- Auditoria de o-que-foi-publicado
- Reaproveitamento em republicação ou em LI/WP

Política Noviello: **persistência mínima de 90 dias** para todas as mídias publicadas no IG. Limpeza opcional após esse prazo.

---

## URL pública sem WordPress (alternativas)

Caso o WordPress esteja fora do ar ou indisponível, fallback temporário:

### Imgur (anônimo)
```bash
curl -X POST "https://api.imgur.com/3/upload" \
  -H "Authorization: Client-ID {client-id}" \
  -F "image=@slide.jpg"
```
Retorna `data.link` com URL pública. Expira em alguns meses.

### transfer.sh
```bash
curl --upload-file slide.jpg https://transfer.sh/slide.jpg
```
URL pública por 14 dias. Sem autenticação. Bom para teste.

### Drive público
1. Upload no Drive
2. Compartilhar publicamente
3. Pegar ID do arquivo
4. URL: `https://drive.google.com/uc?export=download&id={file-id}`

**Atenção**: Drive nem sempre serve a imagem com `Content-Type` correto, o que pode causar falha na Graph API. Imgur e WordPress são mais previsíveis.

---

## Vídeo (Reels)

Mesmo princípio, mas:
- Tamanho do arquivo costuma ser maior (>10 MB)
- WordPress aceita até 64MB por padrão; ajustar `upload_max_filesize` no PHP se necessário
- Resposta da Meta para processamento de vídeo é assíncrona — pode levar minutos

**Recomendação**: para Reels, S3 + CloudFront é mais robusto que WordPress. Mas para começar, WordPress funciona.

---

## Erros de hospedagem mais comuns

| Erro Graph API | Causa hospedagem | Solução |
|----------------|-------------------|---------|
| `Error #100 Image URL not accessible` | URL retorna 404 ou 403 | Verificar permissão do arquivo no WP; testar `curl -I` |
| `Error #2207003 Image not found` | URL com redirect (302) | Usar URL final direta, sem redirect |
| `Error #2207001 Invalid file format` | Content-Type errado | Garantir que o servidor responde `Content-Type: image/jpeg` |
| Timeout no processamento | URL muito lenta (≥ 30s) | Trocar para hosting mais rápido (S3) |
