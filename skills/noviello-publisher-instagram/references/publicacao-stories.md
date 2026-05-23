# Publicar Stories no Instagram

## Visão geral
Stories são o formato de menor compromisso — duração curta, alta frequência, descartável após 24h (ou destaque). Excelente para bastidor, teaser de próximo post, lembrete e prova social.

## Pré-requisitos
- Page Access Token com `instagram_content_publish`
- `ig-user-id`
- Mídia hospedada em URL pública
- Imagem: 1080×1920 JPEG ou PNG ≤ 8MB
- Vídeo: 1080×1920 MP4/MOV, ≤ 60s, ≤ 100MB

---

## Especificações
| Parâmetro | Valor |
|-----------|-------|
| Aspect ratio | 9:16 (1080×1920) |
| Formato imagem | JPEG ou PNG |
| Formato vídeo | MP4 ou MOV |
| Duração vídeo | até 60s |
| Trilha de áudio | obrigatória se vídeo (mesmo silêncio) |
| Caption | NÃO suportada via API (Stories não tem caption) |
| Stickers, polls, perguntas | NÃO suportados via API (somente app oficial) |

**Limitação importante**: a Graph API permite publicar Stories **estáticas** apenas. Stickers interativos (polls, perguntas, quizzes, GIFs, música) **só funcionam quando publicados pelo app oficial Instagram**. Para uso Noviello, Stories via API servem para:
- Teaser do post da quinta (com link/swipe-up nativo se >10k seguidores)
- Anúncio "novo artigo no blog"
- Republicação automática do post do feed em Stories
- Stories agendados em sequência

---

## Fluxo de publicação

### Imagem Stories

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
?media_type=STORIES
&image_url={URL_PUBLICA}
&access_token={page-token}
```

Esperar FINISHED, depois:

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media_publish
?creation_id={container-id}
&access_token={page-token}
```

### Vídeo Stories

```
POST https://graph.facebook.com/v21.0/{ig-user-id}/media
?media_type=STORIES
&video_url={URL_PUBLICA}
&access_token={page-token}
```

Esperar FINISHED (pode levar 1-5 min para vídeo), depois publicar.

---

## Receita Python

```python
def publish_story_image(ig_user_id, image_url, token):
    r = requests.post(f"{GRAPH}/{ig_user_id}/media", params={
        "media_type": "STORIES",
        "image_url": image_url,
        "access_token": token,
    })
    r.raise_for_status()
    container_id = r.json()["id"]
    wait_finished(container_id, token, timeout=60)
    rp = requests.post(f"{GRAPH}/{ig_user_id}/media_publish", params={
        "creation_id": container_id,
        "access_token": token,
    })
    rp.raise_for_status()
    return rp.json()["id"]
```

(`wait_finished` definido em `publicacao-carrossel-passo-a-passo.md`.)

---

## Padrão Noviello — sequência Stories de quinta

Quando o artigo WP sai (quinta 10h), sequência automática de 3-5 Stories:

| # | Mídia | Texto na imagem | Função |
|---|-------|-----------------|--------|
| 1 | Capa do artigo recortada 9:16 | "Saiu hoje no blog" | Anúncio |
| 2 | Trecho-chave em card | Citação curta do artigo (≤15 palavras) | Teaser |
| 3 | Card "5 pontos" | Lista numerada com 3-5 pontos do artigo | Resumo |
| 4 | CTA card | "Leia no link da bio" + seta animada | CTA |
| 5 | (opcional) Foto bastidor | "Por trás desse artigo" + Mario na ponta | Humanização |

Cada Stories aparece sequencialmente nas 24h seguintes.

---

## Stories como agente do funil

Stories são especialmente valiosos para Noviello porque:
1. Reaproveitam carrossel do feed (custo zero adicional)
2. Mantêm o perfil sempre "ativo" (algoritmo recompensa)
3. Direcionam tráfego para link na bio (Linktree em montagem)
4. Aparecem no topo da feed dos seguidores (alta visibilidade)

A skill `noviello-publisher-instagram` automatiza essa sequência: ao publicar um carrossel ou artigo WP, dispara automaticamente a sequência de 3-5 Stories complementares.

---

## Checklist Stories

```
[ ] Mídia 1080×1920 (9:16)
[ ] Imagem JPEG/PNG ≤ 8MB ou vídeo MP4 ≤ 100MB
[ ] Vídeo com trilha de áudio (mesmo silêncio)
[ ] URL pública estável
[ ] Texto sobre a imagem dentro de safe area central (1080×1920 → manter elementos críticos no retângulo 720×1280 central)
[ ] Logo Noviello em canto seguro
[ ] OAB revisado (Prov. 205)
[ ] Mario aprovou
```

---

## Erros comuns

| Erro | Causa | Correção |
|------|-------|----------|
| Stories cortado em cima/baixo | Mídia não é 9:16 | Reenquadrar para 1080×1920 |
| Elementos críticos cortados | Fora de safe area | Manter no retângulo central 720×1280 |
| Stories sem áudio (vídeo) | Trilha removida | Adicionar áudio mesmo que silêncio |
| Stories não aparece para seguidores | Conta com baixa atividade ou shadowban | Verificar saúde da conta |
