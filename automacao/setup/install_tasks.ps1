# Registra as tarefas agendadas do pipeline no Agendador de Tarefas do Windows.
#
# 3 tarefas de trabalho (watcher/poller/producer) rodam periodicamente e terminam
# em segundos. 1 tarefa persistente (painel) sobe um servidor web que fica ligado.
# Politica IgnoreNew: nao inicia nova instancia se uma ja estiver rodando — isso
# elimina concorrencia e, no caso do painel, faz a tarefa reinicia-lo se cair.
#
# Rodar (PowerShell, NAO precisa ser admin):
#   & "C:\Users\mario\Documents\Noviello-Produtividade\automacao\setup\install_tasks.ps1"

$ErrorActionPreference = "Stop"

# setup/ -> automacao/
$automacao = Split-Path $PSScriptRoot -Parent
# pythonw.exe = Python SEM janela de console (nao abre terminal a cada execucao)
$python = Join-Path $automacao ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $python)) {
    Write-Host "ERRO: nao encontrei o pythonw.exe do venv em $python" -ForegroundColor Red
    exit 1
}

$tarefas = @(
    @{ Nome = "Noviello-Watcher";  Modulo = "src.watcher";  Min = 1;   Persistente = $false; Desc = "Detecta pecas prontas e avisa" },
    @{ Nome = "Noviello-Poller";   Modulo = "src.poller";   Min = 1;   Persistente = $false; Desc = "Le a decisao do painel e publica" },
    @{ Nome = "Noviello-Producer"; Modulo = "src.producer"; Min = 2;   Persistente = $false; Desc = "Produz pecas a partir da Fila Social" },
    @{ Nome = "Noviello-Cadencia"; Modulo = "src.cadencia"; Min = 240;  Persistente = $false; Desc = "Cadencia semanal: promove backlog -> Fila Social conforme Google Calendar" },
    @{ Nome = "Noviello-Backup";   Modulo = "src.backup";   Min = 1440; Persistente = $false; Desc = "Backup diario de state/ + producao/ em ~/.noviello-backups (mantem 30 ultimos)" },
    @{ Nome = "Noviello-Painel";   Modulo = "src.painel";   Min = 5;    Persistente = $true;  Desc = "Servidor do painel de aprovacao (localhost:8765)" }
)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# tarefas de trabalho: limite de 10 min (terminam em segundos)
$settingsTrabalho = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew -StartWhenAvailable -Hidden `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# tarefa persistente (painel): sem limite de tempo — o servidor fica ligado
$settingsPersistente = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew -StartWhenAvailable -Hidden `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

foreach ($t in $tarefas) {
    $nome = $t.Nome

    if (Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue) {
        Write-Host "Removendo tarefa existente: $nome" -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $nome -Confirm:$false
    }

    $action = New-ScheduledTaskAction `
        -Execute $python -Argument "-m $($t.Modulo)" -WorkingDirectory $automacao

    # Repeticao periodica. Sem -RepetitionDuration => Duration vazia => indefinido.
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes $t.Min)

    $settings = if ($t.Persistente) { $settingsPersistente } else { $settingsTrabalho }

    try {
        Register-ScheduledTask `
            -TaskName $nome -Description $t.Desc `
            -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
            -ErrorAction Stop | Out-Null
        $obs = if ($t.Persistente) { "servidor, reinicia se cair" } else { "a cada $($t.Min) min" }
        Write-Host "OK - tarefa registrada: $nome ($obs)" -ForegroundColor Green
    } catch {
        Write-Host "FALHOU ao registrar $nome : $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Tarefas instaladas. O painel fica em http://localhost:8765" -ForegroundColor Cyan
Write-Host "Desativar uma tarefa:  Disable-ScheduledTask -TaskName Noviello-Painel"
Write-Host "Remover uma tarefa:    Unregister-ScheduledTask -TaskName Noviello-Painel -Confirm:`$false"
