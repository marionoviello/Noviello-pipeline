# Setup Meta Graph API — Noviello Advocacia
# Gera Long-Lived Page Access Token e salva em variaveis de ambiente do usuario.
#
# Como executar:
#   1. Abra PowerShell (NAO precisa ser admin)
#   2. Cole o caminho deste arquivo precedido de & (e-comercial):
#      & "C:\Users\mario\Documents\Noviello-Produtividade\scripts\setup-meta-token.ps1"
#   3. Quando pedir, cole o App Secret e o User Token (curta duracao) — entrada nao mostra na tela
#
# Tudo roda LOCAL. O script faz 3 chamadas para a Graph API e salva resultado em env vars.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup Meta Graph API - Noviello"           -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# App ID publico (Claude Ads)
$appId = "3132578936953088"

# Pedir inputs sensiveis (entrada nao aparece na tela)
$appSecretSecure = Read-Host -Prompt "Cole o App Secret (entrada oculta)" -AsSecureString
$shortTokenSecure = Read-Host -Prompt "Cole o User Token curta duracao (oculto)" -AsSecureString

# Converter SecureString para texto plano (necessario para HTTP request)
$appSecret = [System.Net.NetworkCredential]::new("", $appSecretSecure).Password
$shortToken = [System.Net.NetworkCredential]::new("", $shortTokenSecure).Password

# ---- Etapa 1: trocar por Long-Lived User Token ----
Write-Host ""
Write-Host "[1/3] Trocando por Long-Lived User Token (60 dias)..." -ForegroundColor Yellow

$exchangeUrl = "https://graph.facebook.com/v21.0/oauth/access_token" + `
    "?grant_type=fb_exchange_token" + `
    "&client_id=$appId" + `
    "&client_secret=$appSecret" + `
    "&fb_exchange_token=$shortToken"

try {
    $exchange = Invoke-RestMethod -Uri $exchangeUrl -Method Get
    $longUserToken = $exchange.access_token
    Write-Host "  OK - Long-Lived User Token obtido." -ForegroundColor Green
} catch {
    Write-Host "  ERRO: $_" -ForegroundColor Red
    Write-Host "  Provavelmente o App Secret ou o User Token estao errados/colados parcialmente." -ForegroundColor Red
    exit 1
}

# ---- Etapa 2: listar Pages e pegar Page Access Token ----
Write-Host ""
Write-Host "[2/3] Buscando Page 'Noviello Advocacia' e Page Token..." -ForegroundColor Yellow

$pagesUrl = "https://graph.facebook.com/v21.0/me/accounts?access_token=$longUserToken"

try {
    $pagesResp = Invoke-RestMethod -Uri $pagesUrl -Method Get
} catch {
    Write-Host "  ERRO ao listar Pages: $_" -ForegroundColor Red
    exit 1
}

$novielloPage = $pagesResp.data | Where-Object { $_.name -like "*Noviello*" } | Select-Object -First 1

if (-not $novielloPage) {
    Write-Host "  ERRO: Page Noviello nao encontrada na sua lista de Pages." -ForegroundColor Red
    Write-Host "  Pages disponiveis:"
    $pagesResp.data | ForEach-Object {
        Write-Host "    - $($_.name) (ID: $($_.id))"
    }
    exit 1
}

$pageId = $novielloPage.id
$pageToken = $novielloPage.access_token
$pageName = $novielloPage.name

Write-Host "  OK - $pageName (ID: $pageId)" -ForegroundColor Green

# ---- Etapa 3: confirmar IG Business Account ID ----
Write-Host ""
Write-Host "[3/3] Confirmando vinculacao Instagram..." -ForegroundColor Yellow

$igUrl = "https://graph.facebook.com/v21.0/${pageId}?fields=instagram_business_account&access_token=$pageToken"

try {
    $igResp = Invoke-RestMethod -Uri $igUrl -Method Get
    $igUserId = $igResp.instagram_business_account.id
    Write-Host "  OK - IG Business Account ID: $igUserId" -ForegroundColor Green
} catch {
    Write-Host "  ATENCAO: nao consegui pegar o IG user ID via API. Usando o ID conhecido." -ForegroundColor Yellow
    $igUserId = "17841404431069191"
}

# ---- Salvar em variaveis de ambiente USER ----
Write-Host ""
Write-Host "Salvando em variaveis de ambiente do usuario..." -ForegroundColor Yellow

[Environment]::SetEnvironmentVariable("META_PAGE_TOKEN", $pageToken, "User")
[Environment]::SetEnvironmentVariable("META_PAGE_ID", $pageId, "User")
[Environment]::SetEnvironmentVariable("IG_USER_ID_NOVIELLOADV", $igUserId, "User")
[Environment]::SetEnvironmentVariable("META_APP_ID", $appId, "User")

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  SUCESSO. Variaveis de ambiente criadas:"   -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  META_PAGE_TOKEN          (Page Access Token, 60 dias)"
Write-Host "  META_PAGE_ID             $pageId"
Write-Host "  IG_USER_ID_NOVIELLOADV   $igUserId"
Write-Host "  META_APP_ID              $appId"
Write-Host ""
Write-Host "PROXIMOS PASSOS:" -ForegroundColor Cyan
Write-Host "  1. Feche e abra o Cowork para que ele 'enxergue' as variaveis."
Write-Host "  2. Tambem salve o META_PAGE_TOKEN no seu gerenciador de senhas (backup)."
Write-Host "  3. Renovacao automatica: agendar lembrete em 50 dias (calendar)."
Write-Host ""
Write-Host "Token expira em 60 dias (modo Development). Para nao expirar, App precisa" -ForegroundColor Yellow
Write-Host "passar por App Review da Meta (1-4 semanas). Para uso solo do Mario," -ForegroundColor Yellow
Write-Host "renovar a cada 50 dias e' o caminho." -ForegroundColor Yellow
Write-Host ""

# Limpar variaveis sensiveis da sessao
Remove-Variable appSecret -ErrorAction SilentlyContinue
Remove-Variable shortToken -ErrorAction SilentlyContinue
Remove-Variable longUserToken -ErrorAction SilentlyContinue
Remove-Variable pageToken -ErrorAction SilentlyContinue
[GC]::Collect()
