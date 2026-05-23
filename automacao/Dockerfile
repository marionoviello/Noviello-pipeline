# Dockerfile pro pipeline Noviello
#
# Base: imagem oficial do Playwright (Python) que ja vem com Chromium headless
# instalado — evita rodar `playwright install` toda vez que builda.
#
# Estrategia: 1 imagem, varios containers (1 por servico) via docker-compose.
# Cada container executa um comando diferente (watcher, poller, producer,
# cadencia, backup, painel).

FROM mcr.microsoft.com/playwright/python:v1.50.0-jammy

# Sem buffer no stdout pra logs aparecerem imediatamente no docker logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Diretorio padrao das volumes (apontaveis via env)
ENV NOVIELLO_STATE_DIR=/var/lib/noviello/state \
    NOVIELLO_LOGS_DIR=/var/log/noviello \
    NOVIELLO_PRODUCAO_DIR=/var/lib/noviello/producao \
    NOVIELLO_BACKUP_DIR=/var/lib/noviello/backups

WORKDIR /app

# Deps Python — copiar requirements primeiro pra cache de layer
COPY automacao/requirements.txt .
RUN pip install -r requirements.txt

# Codigo
COPY automacao/ /app/

# Cria diretorios de volume (serao montados em runtime)
RUN mkdir -p /var/lib/noviello/state \
             /var/lib/noviello/producao \
             /var/lib/noviello/backups \
             /var/log/noviello

EXPOSE 8765

# Default: painel (override pelo docker-compose por servico)
CMD ["python", "-m", "src.painel"]
