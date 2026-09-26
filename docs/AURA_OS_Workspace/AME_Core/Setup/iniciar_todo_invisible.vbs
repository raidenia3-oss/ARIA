Set WshShell = CreateObject("WScript.Shell")
' Ejecuta start_services.bat de forma totalmente oculta (0 = hidden)
WshShell.Run chr(34) & "c:\Users\User\Downloads\AURA\Setup\start_services.bat" & chr(34), 0
Set WshShell = Nothing