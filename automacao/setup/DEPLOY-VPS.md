# Deploy do pipeline em VPS Linux com Docker

> **Quando ler isso:** quando for migrar o pipeline do Windows local pra
> rodar 24/7 numa VPS. Setup estimado: 3-4h.

## Provider recomendado

**Hetzner CX22** (€4,15/mês, Alemanha, 2 vCPU, 2 GB RAM, 40 GB SSD, 20 TB
tráfego). Alternativas equivalentes: Contabo VPS S (~US$ 6, 4 GB RAM),
DigitalOcean Basic ($6, 1 GB), Linode Nanode ($5, 1 GB).

Especificacao minima testada: 2 GB RAM, 2 GB swap, 10 GB livres no /. O
Playwright Chromium e o consumidor pesado.

## Pre-requisitos no VPS

```bash
# Ubuntu 24.04 LTS recem-instalado
apt update && apt upgrade -y
apt install -y docker.io docker-compose-plugin git
systemctl enable --now docker
usermod -aG docker $USER  # logout/login pra valer
```

## Clone + setup

```bash
mkdir -p /opt && cd /opt
git clone <repo-url> noviello
cd noviello

# Copia .env do seu local (NUNCA committar)
# Pode ser via scp do PC: scp .env vps:/opt/noviello/.env
# Ou criar manualmente — veja seção "Variáveis sensíveis" abaixo.

# Build da imagem
docker compose build

# Sobe tudo em background
docker compose up -d

# Confirma que tudo subiu
docker compose ps
```

## Verificacao

```bash
# Logs ao vivo
docker compose logs -f painel

# Health (de dentro da VPS)
curl http://localhost:8765/health.json | python3 -m json.tool

# Health dashboard (precisa do tunnel ou ssh -L 8765:localhost:8765)
ssh -L 8765:localhost:8765 user@vps
# Abre http://localhost:8765/health.html no seu navegador
```

## Cloudflare Tunnel (acesso remoto)

Pra expor o painel sem abrir porta publica:

```bash
# 1. Crie um tunnel no dashboard Cloudflare Zero Trust
# 2. Copie o TUNNEL_TOKEN
# 3. Adicione ao .env:
echo 'CLOUDFLARED_TUNNEL_TOKEN=eyJ...' >> .env
# 4. Descomente o servico `tunnel` no docker-compose.yml
docker compose up -d tunnel
```

## Variaveis sensiveis no .env (resumo)

```ini
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# Google (OAuth Workspace)
GMAIL_OAUTH_CLIENT_ID=...
GMAIL_OAUTH_CLIENT_SECRET=...
GMAIL_OAUTH_REFRESH_TOKEN=...
GOOGLE_AI_API_KEY=AIzaSy...

# WordPress
WP_USER=mario@noviello.adv.br
WP_APP_PASSWORD_NOVIELLO=xxxx xxxx xxxx xxxx

# Meta (Instagram via Graph API)
META_PAGE_TOKEN=EAA...
META_IG_BUSINESS_ID=...
META_PAGE_ID=...

# LinkedIn (REST API v202506)
LI_ACCESS_TOKEN=...
LI_PERSON_URN=urn:li:person:...

# Pipeline
DRY_RUN=false
ENABLED_CHANNELS=instagram,linkedin,wordpress
CADENCIA_ATIVA=true
AUTO_GERAR_HERO=true
```

## Backup remoto (recomendado)

O backup local em `/var/lib/noviello/backups` te salva de falha de
aplicacao, mas nao de falha do disco da VPS. Adicione rsync diario pra
B2/S3:

```bash
# /etc/cron.daily/sync-backups
#!/bin/bash
rclone sync /opt/noviello/.docker-volumes/noviello-backups \
            b2:noviello-backups \
            --max-age 31d
```

(setup do `rclone` separado — veja docs do rclone)

## Operacao do dia-a-dia

```bash
# Pausar tudo
docker compose down

# Atualizar codigo
git pull && docker compose build && docker compose up -d

# Logs de um servico especifico
docker compose logs -f producer

# Reiniciar so o painel
docker compose restart painel

# Snapshot agora (sem esperar 24h)
docker compose exec backup python -m src.backup
```

## Troubleshooting

| Sintoma | Causa provavel | Fix |
|---|---|---|
| `painel` em restart loop | `.env` ausente ou WP_USER vazio | `docker compose logs painel` |
| `producer` nao processa | sem credencial Anthropic / sem Skills dir | check `.env` + healthcheck |
| Healthcheck 503 | algum componente "parado" (heartbeat antigo) | `/health.html` mostra qual |
| Cloudflared offline | TUNNEL_TOKEN errado ou tunnel deletado | recriar tunnel no dashboard |
| Memoria estourando | Playwright headless leak | `docker compose restart producer` semanal |
