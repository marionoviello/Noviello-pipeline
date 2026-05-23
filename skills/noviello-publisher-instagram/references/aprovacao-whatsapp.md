# Aprovação humano-in-the-loop via WhatsApp

## Por que existir
Mesmo com OAB verde e pacote pronto, **nenhuma publicação sai sem aprovação explícita de Mario**. A skill prepara tudo, mas o disparo final é manual.

Razões:
- Compliance OAB (responsabilidade do advogado pelo conteúdo)
- Risco reputacional (algo escapa da revisão técnica e cai mal)
- Mario quer manter feeling humano sobre o que sai
- Permite ajuste de última hora (substituir slide, mudar legenda, mover horário)

---

## Arquitetura do fluxo

```
[Skill noviello-publisher-instagram pronta para publicar]
        ↓
[Envia notificação WhatsApp para Mario]
        ↓
Card no WhatsApp contém:
  - Perfil-alvo (@novielloadv ou @novielloadv.agro)
  - Tipo (carrossel / post / reels / story)
  - Preview dos slides (link Imgur ou Drive)
  - Legenda completa
  - OAB status
  - 3 botões: ✓ Aprovar  ✎ Ajustar  ✗ Cancelar
        ↓
[Mario clica]
        ├── ✓ Aprovar → bot dispara API → publica
        ├── ✎ Ajustar → bot retorna o pacote para correção (texto, slide, OAB)
        └── ✗ Cancelar → arquiva, não publica, registra cancelamento
```

---

## Stack proposta para implementação

### Opção A — Twilio WhatsApp Business API + Make
- Twilio fornece API WhatsApp Business
- Make orquestra: recebe trigger da skill → envia mensagem com botões → escuta webhook de resposta → dispara publicação
- Custo: US$ 0.005 por mensagem template; US$ 9-12/mês Make Starter
- Mais profissional, suporta múltiplos templates

### Opção B — WhatsApp pessoal + bot Z-API ou Evolution API
- Z-API e Evolution API permitem operar WhatsApp pessoal via API (não Business)
- Custo: Z-API a partir de R$ 30/mês; Evolution API self-hosted gratuito
- Funciona, mas WhatsApp pode bloquear se considerar uso não-pessoal
- Para uso solo do Mario, baixo risco

### Opção C — Telegram Bot dedicado
- Telegram tem bot framework nativo, gratuito, robusto
- Botões inline (callback_query) funcionam perfeitamente
- Desvantagem: Mario teria que adotar Telegram como canal de aprovação
- Vantagem: zero custo, infraestrutura sólida

**Recomendação Noviello**: começar com **Opção B (Z-API)** — Mario já vive no WhatsApp, fricção zero. Migrar para Opção A se escalar.

---

## Anatomia da mensagem de aprovação

```
🦅 NOVIELLO PUBLISHER — pendente de aprovação

Perfil: @novielloadv.agro
Tipo: Carrossel (5 slides)
Pilar: Crédito Rural
Programado para: Quarta 19/05 19h00

📸 Preview: https://drive.google.com/.../preview-{id}
   (slide 1 a 5 + capa)

📝 Legenda (157 chars + 8 hashtags):
"Sua safra frustrou? Sua dívida pode ser prorrogada.
O Manual de Crédito Rural (MCR 2-6-9) protege o produtor
quando há frustração de safra. [continua...]"

⚖️ OAB: ✅ Verde — Prov. 205 ok
🤖 Disclosure IA: presente no rodapé

[✓ APROVAR]  [✎ AJUSTAR]  [✗ CANCELAR]
```

---

## Detalhamento de cada botão

### ✓ Aprovar
- Bot recebe callback
- Dispara `POST /media_publish` da Graph API
- Aguarda confirmação de sucesso
- Envia mensagem de volta: "🟢 Publicado às 19h02. Permalink: https://instagram.com/p/..."
- Atualiza planilha-pauta com status `postado` + permalink

### ✎ Ajustar
- Bot pergunta "O que ajustar?" com opções:
  - **Texto da legenda** → bot envia legenda atual, Mario edita, bot atualiza pacote
  - **Trocar slide X** → Mario envia novo slide, bot substitui
  - **Mudar horário** → Mario envia novo horário, bot reagenda
  - **Mudar disclosure IA** → bot ajusta rodapé
- Após ajuste, volta ao card de aprovação

### ✗ Cancelar
- Bot pergunta motivo (opcional, livre)
- Arquiva o pacote em pasta `cancelados/{yyyy-mm-dd}/`
- Registra na planilha-pauta com status `cancelado` + motivo
- Não dispara publicação
- Slot na agenda pode virar replanejamento

---

## Tempo de espera

Pacote fica em fila por **6 horas** aguardando aprovação. Depois disso:
- Notificação de re-aviso (1ª nas 4h, 2ª nas 6h)
- Após 6h sem resposta → arquiva como `expirado_sem_aprovacao` e libera o slot

Isso evita que pacotes fiquem perdidos e mantém o calendário em movimento.

---

## Vésperas como ritual de aprovação

O calendário Noviello tem **eventos VÉSPERA** já programados (T-1 às 20h). A skill `noviello-publisher-instagram` dispara o card de aprovação **18h** do dia anterior à publicação — Mario tem das 18h até 9h do dia seguinte para aprovar. A janela é generosa porque cobre o ritual já existente.

---

## Pseudocódigo do bot (Z-API)

```python
import requests

ZAPI_URL = "https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}"
MARIO_PHONE = "5511XXXXXXXXX"

def send_approval_card(pkg):
    msg = f"""🦅 NOVIELLO PUBLISHER — pendente
Perfil: @{pkg['perfil']}
Tipo: {pkg['tipo']}
Pilar: {pkg['pilar']}
Programado: {pkg['agendamento']}

📸 {pkg['preview_url']}

📝 {pkg['legenda'][:200]}...

⚖️ OAB: {pkg['oab_status']}

Responda:
A — Aprovar
B — Ajustar
C — Cancelar"""

    requests.post(f"{ZAPI_URL}/send-text", json={
        "phone": MARIO_PHONE,
        "message": msg,
    })

def handle_response(message_received, pkg_id):
    if message_received.strip().upper() == "A":
        publish_now(pkg_id)
    elif message_received.strip().upper() == "B":
        ask_what_to_adjust(pkg_id)
    elif message_received.strip().upper() == "C":
        archive(pkg_id, "cancelado_por_mario")
```

---

## Auditoria do fluxo

Cada interação fica registrada em `logs/aprovacoes/{yyyy-mm-dd}/{pkg_id}.json`:

```json
{
  "pkg_id": "agro-2026-05-20-carrossel",
  "perfil": "novielloadv_agro",
  "tipo": "carousel",
  "created_at": "2026-05-19T18:00:00",
  "approval_sent_at": "2026-05-19T18:00:00",
  "response_at": "2026-05-19T19:45:00",
  "response": "A",
  "published_at": "2026-05-19T19:46:12",
  "permalink": "https://instagram.com/p/Cxxx/"
}
```

Auditoria semanal cruza esses logs com a planilha-pauta para detectar:
- Pacotes que ficaram em fila > 6h
- Cancelamentos (e motivos)
- Tempo médio de aprovação
- Quais pilares Mario mais ajusta antes de aprovar (sinal de calibração de skill)
