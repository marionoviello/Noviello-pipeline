"""Consentimento OAuth do Google — roda UMA vez.

Pre-requisito (Mario faz no Google Cloud Console):
  1. Criar um projeto.
  2. Habilitar "Gmail API" e "Google Calendar API".
  3. Tela de consentimento OAuth: tipo "Externo", adicionar mario@noviello.adv.br
     como usuario de teste.
  4. Criar credencial OAuth Client ID do tipo "App para computador" (Desktop).
  5. Baixar o JSON e salvar como:
        C:\\Users\\mario\\Documents\\Noviello-Produtividade\\client_secret.json

Como rodar (a partir da pasta automacao/, com o venv):
    .venv\\Scripts\\python.exe setup\\gmail_auth.py

O script abre o navegador, voce autoriza, e ele imprime as 3 linhas para colar
no arquivo .env: GMAIL_OAUTH_CLIENT_ID, GMAIL_OAUTH_CLIENT_SECRET,
GMAIL_OAUTH_REFRESH_TOKEN.
"""

from __future__ import annotations

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/calendar",
]

# setup/gmail_auth.py -> automacao -> Noviello-Produtividade
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    if len(sys.argv) > 1:
        client_secret = Path(sys.argv[1])
    else:
        client_secret = PROJECT_ROOT / "client_secret.json"

    if not client_secret.exists():
        print(f"ERRO: nao encontrei o arquivo de credencial: {client_secret}")
        print("Baixe o JSON do OAuth Client (tipo Desktop) do Google Cloud Console")
        print(f"e salve nesse caminho, ou passe o caminho como argumento.")
        return 1

    print("Abrindo o navegador para o consentimento Google...")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    if not creds.refresh_token:
        print("ERRO: o Google nao devolveu um refresh_token.")
        print("Revogue o acesso em https://myaccount.google.com/permissions e tente de novo.")
        return 1

    print()
    print("=" * 64)
    print("  SUCESSO. Cole estas 3 linhas no arquivo .env:")
    print("  (C:\\Users\\mario\\Documents\\Noviello-Produtividade\\.env)")
    print("=" * 64)
    print()
    print(f"GMAIL_OAUTH_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_OAUTH_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print()
    print("Depois de colar, rode: .venv\\Scripts\\python.exe setup\\setup_labels.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
