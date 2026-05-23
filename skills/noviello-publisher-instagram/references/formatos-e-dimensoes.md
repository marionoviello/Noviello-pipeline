# Formatos e dimensões — Instagram Graph API

## Quadro de bolso

### Feed — Imagem

| Tipo | Aspecto | Resolução recomendada | Formato | Peso máx |
|------|---------|------------------------|---------|----------|
| Vertical (preferido Noviello) | 4:5 | **1080 × 1350** | JPEG | 8 MB |
| Quadrado | 1:1 | 1080 × 1080 | JPEG | 8 MB |
| Horizontal | 1.91:1 | 1080 × 566 | JPEG | 8 MB |

**Aspecto válido**: entre 4:5 (vertical) e 1.91:1 (horizontal). Fora dessa faixa: erro #110.

**Formato aceito**: **JPEG apenas no feed**. PNG é rejeitado. Conversão obrigatória antes do upload.

### Feed — Carrossel

- Mínimo **2 itens**, máximo **10 itens** (carrossel com 1 item dá erro)
- Cada item: aspecto entre 4:5 e 1.91:1
- Mistura de aspectos no mesmo carrossel: o Instagram crop-a tudo para o aspecto do **primeiro item** — manter consistência

### Reels

| Parâmetro | Valor |
|-----------|-------|
| Aspecto | **9:16** estrito |
| Resolução | **1080 × 1920** |
| Codec vídeo | H.264 |
| Codec áudio | AAC |
| Frame rate | 23-60 fps |
| Duração | 3 segundos a 15 minutos (recomendado 30-60s) |
| Tamanho de arquivo | até 100 MB (recomendado <50 MB) |
| Formato | MP4 ou MOV |
| Bitrate | ≥ 5 Mbps |

### Stories

| Tipo | Aspecto | Resolução | Formato | Duração |
|------|---------|-----------|---------|---------|
| Imagem | 9:16 | 1080 × 1920 | JPEG ou PNG | até 5s exibição |
| Vídeo | 9:16 | 1080 × 1920 | MP4/MOV | até 60s |

---

## Texto

### Legenda do post (caption)

| Parâmetro | Limite |
|-----------|--------|
| Caracteres totais | **2.200** |
| Quebras de linha | Preservadas |
| Hashtags | até **30** no total (legenda + alt-text) |
| Mentions (@) | até 20 |
| Emojis | aceitos, contam como 1-2 caracteres |

### Alt-text por mídia

| Parâmetro | Limite |
|-----------|--------|
| Caracteres por alt-text | **1.000** |
| Definido por item em carrossel | Sim, 1 por slide |

### Primeira linha visível

Os primeiros ~125 caracteres aparecem antes do "..., mais". Concentrar o gancho aqui.

---

## Validação pré-upload (checklist Noviello)

```
[ ] Imagem(ns) em JPEG (não PNG) — só para feed
[ ] Aspecto entre 4:5 e 1.91:1 para feed
[ ] Resolução mínima 1080px no lado maior
[ ] Peso < 8 MB por imagem
[ ] Carrossel com 2-10 itens
[ ] Aspecto consistente em todo o carrossel
[ ] Legenda ≤ 2.200 chars
[ ] Hashtags ≤ 30 totais
[ ] Alt-text ≤ 1.000 chars por mídia
[ ] Reels: MP4 H.264 + AAC, 1080x1920, ≤ 90s
[ ] Stories: 1080x1920, 9:16
```

Se algum item falhar, **não criar container**. Devolver para correção.

---

## Identidade visual canônica Noviello

Para garantir consistência (e velocidade de produção pela skill `noviello-carrossel-creator`):

| Elemento | Especificação |
|----------|---------------|
| Logo "Noviello Advocacia" | SVG canônico, topo direito de cada peça, 8% da largura |
| Paleta master | Claret #6B2C39, areia #F4E8D8, verde-oliva #6B7A4F, marrom-terra #5D4037 |
| Paleta agro | Mesma paleta master (sub-marca, não independente) |
| Tipografia headline | Serif elegante (Playfair Display, peso 500-700) |
| Tipografia corpo | Sans-serif limpa (Inter, peso 400) |
| Padrão de capa carrossel | I-Editorial (Sênior/Sucessório), II-Blueprint (Imobiliário), III-Ateliê (técnico) |
| Margem de segurança | 80px em todas as bordas (evita corte em outras plataformas) |
| Safe area Reels | manter elementos críticos dentro do retângulo central 720×1280 |

---

## Conversões úteis

### Crop centralizado de imagem qualquer para 1080x1350

```bash
# Usando ImageMagick
convert input.png \
  -resize "1080x1350^" \
  -gravity center -extent 1080x1350 \
  -quality 90 \
  output.jpg
```

### Validar dimensão e formato (Python)

```python
from PIL import Image

def validate_feed_image(path):
    img = Image.open(path)
    w, h = img.size
    aspect = w / h
    ok = (
        img.format == "JPEG" and
        w >= 1080 and
        0.8 <= aspect <= 1.91
    )
    return ok, {"w": w, "h": h, "aspect": round(aspect, 2), "format": img.format}
```

### Validar Reels (ffprobe)

```bash
ffprobe -v error -show_entries stream=width,height,codec_name,r_frame_rate -of default=noprint_wrappers=1 reels.mp4
```

Esperar `width=1080, height=1920, codec_name=h264` e frame rate ≥ 23.

---

## Erros frequentes de formato

| Sintoma | Causa típica | Correção |
|---------|--------------|----------|
| `Error #110 Invalid aspect ratio` | Imagem 16:9 enviada para feed | Recortar para 4:5 ou 1:1 |
| `Error #2207009 Media format invalid` | PNG no feed | Converter para JPEG |
| `Error #2207026 Aspect ratio is not supported` | Vídeo 16:9 enviado como Reels | Recortar para 9:16 |
| Reels publica como post | `media_type=REELS` esquecido no container | Sempre setar `media_type=REELS` |
| Carrossel não publica | Algum item não terminou processamento | Aguardar status FINISHED de TODOS antes de publish |
