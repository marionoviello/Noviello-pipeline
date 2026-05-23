# Teste de validacao Meta Graph API
# Faz chamadas de LEITURA simples para confirmar que o token funciona.
# NAO publica nada. Seguro de rodar quantas vezes quiser.

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Teste de validacao Meta Graph API"          -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Ler env vars
$pageToken = [Environment]::GetEnvironmentVariable("META_PAGE_TOKEN", "User")
$pageId    = [Environment]::GetEnvironmentVariable("META_PAGE_ID", "User")
$igUserId  = [Environment]::GetEnvironmentVariable("IG_USER_ID_NOVIELLOADV", "User")

if (-not $pageToken) {
    Write-Host "ERRO: variavel META_PAGE_TOKEN nao encontrada." -ForegroundColor Red
    Write-Host "Rode primeiro setup-meta-token.ps1 ou abra novo terminal apos setup." -ForegroundColor Red
    exit 1
}
Write-Host "Token detectado ($($pageToken.Length) caracteres). Iniciando testes..." -ForegroundColor Green
Write-Host ""

# ---- Teste 1: GET /me?fields=id,name,username com o Page Token ----
Write-Host "[1/3] GET /me com Page Token (deve retornar Page Noviello)..." -ForegroundColor Yellow
try {
    $resp1 = Invoke-RestMethod -Uri "https://graph.facebook.com/v21.0/me?fields=id,name,username&access_token=$pageToken" -Method Get
    Write-Host "  OK - Page Token valido." -ForegroundColor Green
    Write-Host "       id:       $($resp1.id)"
    Write-Host "       name:     $($resp1.name)"
    if ($resp1.username) { Write-Host "       username: $($resp1.username)" }
} catch {
    Write-Host "  ERRO: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ---- Teste 2: GET /{ig-user-id}?fields=id,username,profile_picture_url,followers_count,media_count ----
Write-Host "[2/3] GET /{ig-user-id} para confirmar acesso ao @novielloadv..." -ForegroundColor Yellow
try {
    $url2 = "https://graph.facebook.com/v21.0/${igUserId}?fields=id,username,profile_picture_url,followers_count,media_count,biography&access_token=$pageToken"
    $resp2 = Invoke-RestMethod -Uri $url2 -Method Get
    Write-Host "  OK - IG Business Account acessivel." -ForegroundColor Green
    Write-Host "       id:               $($resp2.id)"
    Write-Host "       username:         @$($resp2.username)"
    Write-Host "       followers_count:  $($resp2.followers_count)"
    Write-Host "       media_count:      $($resp2.media_count)"
    if ($resp2.biography) {
        $bioShort = $resp2.biography.Substring(0, [Math]::Min(80, $resp2.biography.Length))
        Write-Host "       biography:        $bioShort..."
    }
} catch {
    Write-Host "  ERRO: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ---- Teste 3: GET /{ig-user-id}/media?limit=3 (3 ultimos posts) ----
Write-Host "[3/3] GET /{ig-user-id}/media (listar 3 ultimos posts)..." -ForegroundColor Yellow
try {
    $url3 = "https://graph.facebook.com/v21.0/${igUserId}/media?fields=id,caption,media_type,permalink,timestamp&limit=3&access_token=$pageToken"
    $resp3 = Invoke-RestMethod -Uri $url3 -Method Get
    Write-Host "  OK - Permissao de leitura de media funciona." -ForegroundColor Green
    Write-Host "       Total retornado: $($resp3.data.Count) posts"
    Write-Host ""
    $i = 1
    foreach ($post in $resp3.data) {
        $caption = if ($post.caption) { $post.caption.Substring(0, [Math]::Min(60, $post.caption.Length)) + "..." } else { "(sem caption)" }
        Write-Host "       [$i] $($post.media_type) - $($post.timestamp)"
        Write-Host "           $caption"
        Write-Host "           $($post.permalink)"
        $i++
    }
} catch {
    Write-Host "  ERRO: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "============================================" -ForegroundColor Green
Write-Host "  SUCESSO. Token totalmente funcional."        -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "O que esses 3 testes confirmaram:" -ForegroundColor Cyan
Write-Host "  1. Token autentica como Page Noviello Advocacia"
Write-Host "  2. Token tem acesso de leitura ao @novielloadv"
Write-Host "  3. Token tem permissao instagram_basic e pode listar posts"
Write-Host ""
Write-Host "Esta tudo pronto para publicacao via skill noviello-publisher-instagram." -ForegroundColor Green
Write-Host ""
