' Sobe o cloudflared SEM janela de console.
' WindowStyle 0 = oculto. O terceiro parametro True faz o wscript ESPERAR o
' cloudflared terminar - assim a tarefa agendada continua "em execucao" e a
' politica IgnoreNew nao deixa subir uma segunda instancia.
Set sh = CreateObject("WScript.Shell")
exe = "C:\Users\mario\Documents\Noviello-Produtividade\automacao\setup\cloudflared.exe"
cfg = "C:\Users\mario\.cloudflared\config.yml"
sh.Run """" & exe & """ tunnel --config """ & cfg & """ run noviello-painel", 0, True
