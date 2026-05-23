# Rate limits e troubleshooting — Graph API Instagram

## Rate limits oficiais

### Por conta IG Business
| Limite | Valor |
|--------|-------|
| Publicações por janela 24h | **100 posts** |
| Carrossel conta como | 1 publicação (independente do número de slides) |
| Reels conta como | 1 publicação |
| Story conta como | 1 publicação |

### Por App (Business Use Case — BUC)
| Limite | Valor |
|--------|-------|
| Calls por janela móvel de 60 min | 200 calls por usuário |
| Calls totais por hora | depende do tier do App |

### Penalidades por exceder
- Resposta com `Error #4 Application request limit reached`
- Header `X-Business-Use-Case-Usage` mostra % de uso e tempo até reset
- Bloqueio temporário (15 min a 60 min)
- Uso reiterado pode resultar em rate limit permanente reduzido

**Implicação Noviello**: 100 posts/24h é folgado para a cadência atual (3 perfis × 3 posts/semana = 9 posts/semana = 1.3/dia). Sem risco real.

---

## Erros mais comuns — tabela exaustiva

### Autenticação (1xx, 2xx)

| Código | Mensagem | Causa | Solução |
|--------|----------|-------|---------|
| #190 | OAuthException | Token expirado | Renovar com `/oauth/access_token` |
| #200 | Permissions error | Falta permission `instagram_content_publish` | App Review (produção) ou conceder em dev |
| #200 | (variant) Page admin role missing | Usuário não é admin da Page | Adicionar role no BM |
| #100 | Invalid OAuth access token signature | Token corrompido na concatenação | Reverificar serialização do token |
| #803 | Object does not exist | `ig-user-id` errado ou conta IG não conectada à Page | Conferir conexão IG ↔ Page no BM |

### Mídia (110, 220x)

| Código | Mensagem | Causa | Solução |
|--------|----------|-------|---------|
| #100 | Image URL not accessible | URL não pública, expirada ou com redirect | Hospedar em CDN persistente (WP); usar URL direta sem redirect |
| #110 | Invalid parameter (aspect ratio) | Aspect fora de 4:5 a 1.91:1 | Recortar para 1080x1350 ou 1080x1080 |
| #2207001 | Invalid file format | Content-Type errado no servidor | Confirmar servidor retorna `image/jpeg` |
| #2207003 | Image not found | URL retorna 404 | Verificar caminho; testar `curl -I` |
| #2207009 | Media format invalid | PNG enviado no feed | Converter para JPEG |
| #2207026 | Aspect ratio not supported (REELS) | Vídeo não é 9:16 | Reenquadrar para 1080x1920 |
| #2207050 | Container processing error | Codec ou bitrate inválido (Reels) | Reencodar com H.264 + AAC |

### Publicação (4x, 5x)

| Código | Mensagem | Causa | Solução |
|--------|----------|-------|---------|
| #4 | Application request limit reached | Rate limit BUC | Aguardar reset; ler header `X-Business-Use-Case-Usage` |
| #506 | Duplicate post | Mesmo texto/imagem publicado recentemente | Variar conteúdo ou aguardar 24h |
| #1 | Unknown error / internal | Erro temporário Meta | Retry com backoff exponencial |
| #100 | children must be at least 2 | Carrossel com 1 item | Validar antes de criar carousel container |
| #100 | Maximum 10 children | Carrossel >10 | Dividir em 2 carrosséis |

### Container (status_code)

| Status | Significado | Conduta |
|--------|-------------|---------|
| `IN_PROGRESS` | Processando | Aguardar (polling 2-10s) |
| `FINISHED` | Pronto | Próxima etapa (publish) |
| `ERROR` | Falha | Ver campo `status` para detalhes; recriar com correção |
| `EXPIRED` | Container expirou (>24h) | Recriar do zero |
| `PUBLISHED` | Já publicado | Ignorar |

---

## Retry com backoff exponencial

```python
import time, random

def with_retry(fn, max_attempts=5, base_delay=2):
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

Aplicar em todas as chamadas Graph API. Backoff cresce: 2s → 4s → 8s → 16s → 32s.

---

## Monitor de rate limit (Python)

```python
import requests

def check_buc_usage(token, app_id):
    r = requests.get(f"https://graph.facebook.com/v21.0/{app_id}", params={
        "fields": "name",
        "access_token": token,
    })
    usage_header = r.headers.get("X-Business-Use-Case-Usage", "{}")
    # Parse JSON; cada usuário tem entrada com call_count, total_time, total_cputime
    import json
    return json.loads(usage_header)
```

Logar uso após cada publicação. Alertar Mario se algum dos 3 valores estiver >75%.

---

## Sintomas de shadowban / queda de alcance

Não são erros formais da API, mas merecem atenção:

| Sintoma | Possível causa | Diagnóstico |
|---------|----------------|-------------|
| Alcance cai pela metade subitamente | Uso de hashtag banida | Conferir lista de hashtags ativas no momento |
| Post não aparece em pesquisa por hashtag | Shadowban temporário | Pausar publicações por 48-72h; remover hashtags suspeitas |
| Comentários sumiram | Filtro automático Meta | Verificar Comments Filter nas configurações da conta |
| Stories não aparece para seguidores | Conta marcada como inativa | Engajar manualmente por alguns dias |
| Métricas zeradas após publicar | Bug temporário | Aguardar 24-48h |

**Política Noviello**: monitorar alcance médio dos últimos 10 posts toda semana. Queda >40% sustentada por 2 semanas = investigação obrigatória.

---

## Recuperação de erros — playbook

### Erro #100 Image URL not accessible

1. Testar URL no navegador (deve abrir a imagem)
2. `curl -I {url}` — confirmar `HTTP/1.1 200 OK` e `Content-Type: image/jpeg`
3. Se WP, verificar permissões do arquivo (chmod 644)
4. Se Drive, confirmar que está "Qualquer pessoa com link"
5. Se houver redirect (302), substituir por URL direta

### Erro #200 Permissions

1. Em `https://developers.facebook.com/tools/explorer/`, gerar novo User Token com todas as 5 permissions
2. Verificar status do App em App Review
3. Se em dev mode, adicionar Mario como Test User
4. Renovar Page Token

### Container ficou EXPIRED

1. Recriar container do zero
2. Publicar imediatamente após FINISHED
3. Containers duram 24h — não criar com muita antecedência

### Reels não termina processamento

1. Confirmar tamanho do arquivo ≤ 100 MB
2. Reencodar para H.264 baseline profile + AAC 48kHz
3. Se persistir, dividir em 2 Reels menores

---

## Quando escalar para suporte Meta

Casos em que vale abrir ticket no Business Help Center:
- Erro persistente sem código documentado
- App bloqueado sem motivo aparente
- Permission concedida mas não funcional
- Rate limit anormalmente baixo

Link: https://business.facebook.com/business/help

---

## Política de tentativas Noviello

```
1ª falha → retry imediato (1x)
2ª falha → backoff 30s + retry
3ª falha → backoff 5min + retry
4ª falha → mandar alerta WhatsApp para Mario com erro completo + parar
```

Mario decide se aguarda, ajusta ou cancela.
