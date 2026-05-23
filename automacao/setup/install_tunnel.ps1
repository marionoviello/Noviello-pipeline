# Configura o tunel Cloudflare que expoe o painel (localhost:8765) em
# https://painel.noviello.adv.br - para aprovar pelo celular.
#
# PRE-REQUISITO: rodar antes, UMA vez, o login que autoriza a conta Cloudflare:
#   & "C:\Users\mario\Documents\Noviello-Produtividade\automacao\setup\cloudflared.exe" tunnel login
# O navegador abre -> escolher a zona noviello.adv.br -> autorizar.
#
# Depois rodar este script (NAO precisa ser admin):
#   & "C:\Users\mario\Documents\Noviello-Produtividade\automacao\setup\install_tunnel.ps1"
#
# O painel em si nao muda - continua em localhost:8765. O cloudflared roda na
# mesma maquina, conversa com o painel localmente e publica pra fora pelo tunel.
# SEGURANCA: proteger painel.noviello.adv.br com Cloudflare Access (instrucoes
# no fim deste script) - sem isso, qualquer um com o link poderia aprovar.

$ErrorActionPreference = "Stop"

$cloudflared = Join-Path $PSScriptRoot "cloudflared.exe"
$nomeTunel   = "noviello-painel"
$hostname    = "painel.noviello.adv.br"
$painelLocal = "http://localhost:8765"
$cfDir       = Join-Path $env:USERPROFILE ".cloudflared"
$configPath  = Join-Path $cfDir "config.yml"

if (-not (Test-Path $cloudflared)) {
    Write-Host "ERRO: nao encontrei o cloudflared.exe em $cloudflared" -ForegroundColor Red
    exit 1
}

# O login cria o cert.pem. Sem ele, nao da pra criar o tunel.
$certPath = Join-Path $cfDir "cert.pem"
if (-not (Test-Path $certPath)) {
    Write-Host "ERRO: voce ainda nao fez o login da Cloudflare." -ForegroundColor Red
    Write-Host "Rode primeiro, uma vez:" -ForegroundColor Yellow
    Write-Host ('  & "' + $cloudflared + '" tunnel login') -ForegroundColor Yellow
    exit 1
}

# 1. Cria o tunel (ou reaproveita, se ja existir).
$lista = & $cloudflared tunnel list --output json | ConvertFrom-Json
$tunel = $lista | Where-Object { $_.name -eq $nomeTunel } | Select-Object -First 1

if ($tunel) {
    Write-Host ("Tunel '" + $nomeTunel + "' ja existe (id " + $tunel.id + ") - reaproveitando.") -ForegroundColor Yellow
    $tunelId = $tunel.id
} else {
    Write-Host ("Criando tunel '" + $nomeTunel + "'...") -ForegroundColor Cyan
    & $cloudflared tunnel create $nomeTunel | Out-Null
    $lista = & $cloudflared tunnel list --output json | ConvertFrom-Json
    $tunelId = ($lista | Where-Object { $_.name -eq $nomeTunel } | Select-Object -First 1).id
}

if (-not $tunelId) {
    Write-Host "ERRO: nao consegui obter o id do tunel." -ForegroundColor Red
    exit 1
}

$credFile = Join-Path $cfDir ($tunelId + ".json")

# 2. Escreve o config.yml - mapeia o hostname publico para o painel local.
$config = @"
tunnel: $tunelId
credentials-file: $credFile

ingress:
  - hostname: $hostname
    service: $painelLocal
  - service: http_status:404
"@
# UTF-8 SEM BOM - o parser YAML do cloudflared rejeita o BOM.
[System.IO.File]::WriteAllText($configPath, $config, (New-Object System.Text.UTF8Encoding $false))
Write-Host "config.yml escrito em $configPath" -ForegroundColor Green

# 3. Cria o registro DNS painel.noviello.adv.br -> tunel.
#    Idempotente: se o CNAME ja existir, cloudflared apenas avisa.
Write-Host ("Roteando DNS " + $hostname + " -> tunel...") -ForegroundColor Cyan
try { & $cloudflared tunnel route dns $nomeTunel $hostname | Out-Null }
catch { Write-Host "  (DNS provavelmente ja roteado - seguindo)" -ForegroundColor DarkGray }
Write-Host "DNS roteado." -ForegroundColor Green

# 4. Registra a tarefa agendada que mantem o tunel ligado.
#    A tarefa chama wscript.exe com run_tunnel_hidden.vbs, que sobe o
#    cloudflared SEM janela de console. O wscript espera o cloudflared,
#    entao a tarefa fica "em execucao" e o IgnoreNew evita duplicar.
#    Logon Interactive = NAO precisa de admin (igual as outras tarefas).
$vbs = Join-Path $PSScriptRoot "run_tunnel_hidden.vbs"
if (-not (Test-Path $vbs)) {
    Write-Host "ERRO: nao encontrei o lancador $vbs" -ForegroundColor Red
    exit 1
}

$nomeTarefa = "Noviello-Tunnel"
if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    Write-Host "Removendo tarefa existente: $nomeTarefa" -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false
}

$acao = New-ScheduledTaskAction -Execute "wscript.exe" `
    -Argument ('"' + $vbs + '"') -WorkingDirectory $PSScriptRoot

$gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew -StartWhenAvailable -Hidden `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $nomeTarefa `
    -Description "Tunel Cloudflare: expoe o painel em $hostname" `
    -Action $acao -Trigger $gatilho -Principal $principal -Settings $settings `
    -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName $nomeTarefa
Write-Host "OK - tarefa registrada e iniciada: $nomeTarefa" -ForegroundColor Green
Write-Host ""
Write-Host "Tunel configurado." -ForegroundColor Cyan
Write-Host ("O painel ficara em: https://" + $hostname) -ForegroundColor Cyan
Write-Host ""
Write-Host "FALTA O PASSO DE SEGURANCA (obrigatorio):" -ForegroundColor Yellow
Write-Host ("Proteger " + $hostname + " com Cloudflare Access, senao qualquer um") -ForegroundColor Yellow
Write-Host "com o link poderia aprovar publicacoes. Passo a passo:" -ForegroundColor Yellow
Write-Host "  1. Abra https://one.dash.cloudflare.com (Zero Trust)" -ForegroundColor Yellow
Write-Host "  2. Access -> Applications -> Add an application -> Self-hosted" -ForegroundColor Yellow
Write-Host "  3. Nome: Painel Noviello | Subdominio: painel | Dominio: noviello.adv.br" -ForegroundColor Yellow
Write-Host "  4. Policy: Allow -> Include -> Emails -> mario@noviello.adv.br" -ForegroundColor Yellow
Write-Host "  5. Salvar. O login por codigo de e-mail ja vem ligado." -ForegroundColor Yellow
