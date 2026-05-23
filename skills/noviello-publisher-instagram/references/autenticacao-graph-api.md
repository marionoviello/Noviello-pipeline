# Autenticação Graph API — Instagram Business

## Sumário
1. Pré-requisitos da conta
2. Page Access Token vs User Access Token
3. Permissions necessárias
4. Setup passo a passo
5. Renovação e expiração
6. Identificação do IG Business Account ID
7. Troubleshooting de autenticação

---

## 1. Pré-requisitos da conta

Para publicar via Graph API, o perfil Instagram precisa:

1. Ser **Conta Profissional** (Negócio ou Criador de Conteúdo)
2. Estar **conectado a uma Página do Facebook** (Page)
3. A Page e a conta IG estarem no mesmo Business Manager (BM)
4. O usuário operador da Graph API ter **role de admin** na Page

Os dois perfis Noviello precisam atender esses requisitos:
- **@novielloadv** — conectar à Page "Noviello Advocacia"
- **@novielloadv.agro** — conectar à Page agro (criar se não existir)

---

## 2. Page Access Token vs User Access Token

**User Access Token**: emitido para o login pessoal de Mario. Bom para teste; ruim para automação (expira rápido, depende da sessão do navegador).

**Page Access Token**: emitido para a Page do Facebook. É o token correto para automação — pode ser "Long-Lived" (60 dias) ou "Page Token Never-Expiring" (depende do escopo concedido).

Padrão Noviello: **Page Access Token Long-Lived** com renovação automática a cada 50 dias por workflow N8N (ou alerta de renovação manual).

---

## 3. Permissions necessárias

| Permission | Função |
|------------|--------|
| `instagram_basic` | Ler informações básicas da conta IG conectada |
| `instagram_content_publish` | **Publicar conteúdo** (carrossel, post, Reels) |
| `pages_show_list` | Listar Pages que o usuário administra |
| `pages_read_engagement` | Ler engajamento dos posts |
| `business_management` | Gerenciar ativos do BM |

Em ambiente de teste (App em Development Mode), todas funcionam. Para produção, App precisa estar em **App Review** com essas permissions aprovadas pela Meta — processo que leva 1-4 semanas. **Importante**: se Mario já operou Meta Ads, o App provavelmente já está aprovado para a maioria das permissions; confirmar antes.

---

## 4. Setup passo a passo

### Etapa 1 — Criar/usar App no Meta for Developers
- https://developers.facebook.com → My Apps → Create App
- Tipo: **Business**
- Adicionar produto **Instagram Graph API**

### Etapa 2 — Vincular Páginas e Contas Instagram ao App
- Settings → Basic → confirmar App ID e App Secret
- Instagram Graph API → adicionar a Page da Noviello
- Confirmar que a conta IG profissional está vinculada à Page

### Etapa 3 — Obter Page Access Token de longa duração
1. Em `https://developers.facebook.com/tools/explorer/`, escolher o App, gerar User Access Token com as 5 permissions acima
2. Trocar User Token por Long-Lived User Token (chamada `/oauth/access_token` com `grant_type=fb_exchange_token`)
3. Obter Long-Lived Page Access Token (chamada `/me/accounts` usando Long-Lived User Token, pegar `access_token` da Page desejada)
4. Esse Page Token não-expirante (em regra) é o que vai para a variável de ambiente

### Etapa 4 — Armazenar tokens com segurança
- Variáveis de ambiente locais: `IG_PAGE_TOKEN_NOVIELLOADV` e `IG_PAGE_TOKEN_NOVIELLOADV_AGRO`
- Nunca commitar em repositório público
- Rotação preventiva a cada 50 dias

### Etapa 5 — Identificar IG Business Account ID
```
GET /{page-id}?fields=instagram_business_account&access_token={page-token}
```
Retorna `instagram_business_account.id` — guardar como `IG_USER_ID_NOVIELLOADV` e `IG_USER_ID_NOVIELLOADV_AGRO`.

---

## 5. Renovação e expiração

| Token | Validade típica | Como renovar |
|-------|-----------------|--------------|
| User Access Token (debug) | 1-2 horas | Refazer login no Tools Explorer |
| Long-Lived User Token | 60 dias | `/oauth/access_token` com `fb_exchange_token` |
| Long-Lived Page Token (App em prod) | Sem expiração | Em regra, não expira; checar status com `/debug_token` |
| Long-Lived Page Token (App em dev) | 60 dias | Repetir Etapa 3 |

**Rotina Noviello**: workflow N8N agendado para o dia 25 de cada mês roda `/debug_token` em ambos os tokens, alerta Mario via WhatsApp se algum estiver expirando em < 15 dias.

---

## 6. Identificação do IG Business Account ID

Cada perfil IG conectado a uma Page tem um `ig-user-id` distinto do Page ID. **Esse é o ID usado em todas as chamadas de publicação**, não o Page ID.

Forma rápida de obter:
```bash
curl -X GET "https://graph.facebook.com/v21.0/{page-id}?fields=instagram_business_account&access_token={page-token}"
```

Resposta:
```json
{
  "instagram_business_account": {
    "id": "17841401234567890"
  },
  "id": "page-id"
}
```

O `17841...` é o `ig-user-id` (sempre começa com `17841`).

---

## 7. Troubleshooting de autenticação

| Erro | Causa | Solução |
|------|-------|---------|
| `Error #190 OAuthException` | Token expirado | Renovar com `/oauth/access_token` |
| `Error #200 Permissions error: missing instagram_content_publish` | App sem aprovação ou permission não concedida | App Review (produção) ou conceder em dev mode |
| `Error #100 Invalid parameter: object not found` | `ig-user-id` errado | Recuperar com `/me/accounts` + `/page-id?fields=instagram_business_account` |
| `Error #4 Application request limit reached` | Rate limit do App (BUC = 200 calls/hora/user) | Throttling + retry exponencial |
| `Error #803 Object does not exist` | Conta IG não conectada à Page | Conectar no Business Suite primeiro |
| `Error #506 Duplicate post` | Mesmo texto publicado recentemente | Aguardar 24h ou variar texto |

Detalhamento em `rate-limits-troubleshooting.md`.
