# diagnostico_aria.ps1  -  Windows PowerShell 5.1  -  ASCII only
# SOLO LECTURA. Unica accion: arranca ARIA 15 s en pantalla virtual y la cierra.
# Uso (PowerShell o Git Bash), desde cualquier carpeta del repo:
#   powershell -NoProfile -ExecutionPolicy Bypass -File reference\diagnostico_aria.ps1
# Copia TODO lo que imprime y pegaselo a Claude.

$ErrorActionPreference = 'Continue'
$top = (git rev-parse --show-toplevel 2>$null)
if (-not $top) { $top = (Get-Location).Path }
$Repo = ($top -replace '/', '\')
Set-Location $Repo
$py = Join-Path $Repo '.venv\Scripts\python.exe'

function T($titulo) { Write-Output ""; Write-Output ("===== " + $titulo + " =====") }
function Corto($s, $n) { $s = $s.Trim(); if ($s.Length -gt $n) { $s.Substring(0, $n) } else { $s } }

T "ENTORNO"
"fecha: " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"repo: " + $Repo
if (Test-Path $py) { "python venv: " + (& $py --version 2>&1) } else { "python venv: NO EXISTE en " + $py }

T "GIT"
"rama: " + (git rev-parse --abbrev-ref HEAD)
git log --format="%h %ad %s" --date=format:"%m-%d %H:%M" -8
"--- estado (ARIA_APP, tests, .kilocode, AGENTS.md):"
git status --porcelain=v1 -- ARIA_APP tests .kilocode AGENTS.md
"--- historial de path_guard (vacio = nunca se commiteo):"
git log --format="%h %s" -3 -- ARIA_APP/path_guard.py tests/test_path_guard.py

T "ARCHIVOS CLAVE (bytes | lineas | SHA-256 corto)"
$claves = @('ARIA_APP\aria_main.py', 'ARIA_APP\desktop_ui.py', 'ARIA_APP\aria_va_core.py',
            'ARIA_APP\desktop_autonomy.py', 'ARIA_APP\path_guard.py', 'ARIA_APP\ui\nucleo_v2.py',
            'ARIA_APP\memory\sqlite_adapter.py', 'tests\test_path_guard.py', 'tests\test_nucleo_v2.py',
            'packages\backend\permissions\engine.py')
foreach ($f in $claves) {
    if (Test-Path $f) {
        $i = Get-Item $f
        $n = @(Get-Content $f).Count
        $h = (Get-FileHash $f -Algorithm SHA256).Hash.Substring(0, 12)
        "{0} | {1} B | {2} lineas | {3}" -f $f, $i.Length, $n, $h
    } else { "$f | NO EXISTE" }
}

T "RESPALDO pre-S1 (hechos por Kilo; comparar con los hashes de arriba)"
$resp = Join-Path $env:LOCALAPPDATA 'Temp\aria-backup\pre-S1'
if (Test-Path $resp) {
    foreach ($f in Get-ChildItem $resp -File) {
        "{0} | {1} B | {2} | modificado {3}" -f $f.Name, $f.Length, (Get-FileHash $f.FullName -Algorithm SHA256).Hash.Substring(0, 12), $f.LastWriteTime.ToString('MM-dd HH:mm')
    }
} else { "no existe la carpeta de respaldo: " + $resp }

T "SINTAXIS PYTHON (sin escribir archivos)"
$chk = Join-Path $env:TEMP 'aria_chk_sintaxis.py'
$cuerpo = @'
import ast, sys
for ruta in sys.argv[1:]:
    try:
        ast.parse(open(ruta, encoding="utf-8-sig").read(), ruta)
        print("OK     " + ruta)
    except SyntaxError as e:
        print("ERROR  %s  linea %s: %s" % (ruta, e.lineno, e.msg))
    except Exception as e:
        print("ERROR  %s  %s" % (ruta, e))
'@
Set-Content -Path $chk -Value $cuerpo -Encoding ASCII
if (Test-Path $py) {
    & $py $chk ARIA_APP\aria_main.py ARIA_APP\desktop_ui.py ARIA_APP\aria_va_core.py ARIA_APP\path_guard.py ARIA_APP\ui\nucleo_v2.py ARIA_APP\memory\sqlite_adapter.py
}

T "PRUEBAS (cuenta real)"
$env:QT_QPA_PLATFORM = 'offscreen'
foreach ($t in @('tests\test_path_guard.py', 'tests\test_nucleo_v2.py')) {
    if (Test-Path $t) {
        "--- $t : funciones test_ definidas = " + @(Select-String -Path $t -Pattern '^\s*def test_').Count
        if (Test-Path $py) { & $py -m pytest -q -p no:cacheprovider $t 2>&1 | Select-Object -Last 6 }
    } else { "--- $t : NO EXISTE" }
}

T "PATH GUARD"
if (Test-Path 'ARIA_APP\path_guard.py') {
    Select-String -Path 'ARIA_APP\path_guard.py' -Pattern '^\s*(def|class) ' | ForEach-Object { "{0}: {1}" -f $_.LineNumber, (Corto $_.Line 100) }
} else { "ARIA_APP\path_guard.py NO EXISTE" }
"referencias a path_guard / resolve_allowed en aria_va_core.py: " + @(Select-String -Path 'ARIA_APP\aria_va_core.py' -Pattern 'path_guard|resolve_allowed').Count

T "RESTOS DE AUTONOMIA en desktop_ui.py (nombres que ya no se importan)"
$pat = '_autonomy_runtime|_start_heartbeat|_stop_heartbeat|_pending_goals|_summarize_perception|_episode_line|_goal_line|_last_episode|_beat_summary|_lesson_line|_autonomy_mode|autonomy_bridge|desktop_autonomy|Heartbeat'
Select-String -Path 'ARIA_APP\desktop_ui.py' -Pattern $pat | Select-Object -First 40 | ForEach-Object { "{0}: {1}" -f $_.LineNumber, (Corto $_.Line 130) }

T "ENGINE DE PERMISOS (lo que realmente hay)"
$eng = 'packages\backend\permissions\engine.py'
if (Test-Path $eng) {
    "lineas: " + @(Get-Content $eng).Count
    Select-String -Path $eng -Pattern '^\s*(class|def|async def) ' | Select-Object -First 25 | ForEach-Object { "{0}: {1}" -f $_.LineNumber, (Corto $_.Line 110) }
} else { "NO EXISTE: $eng" }

T "ARRANQUE (15 s en pantalla virtual; se mide el arbol de procesos completo)"
function Descendientes($id) {
    $hijos = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $id }
    foreach ($x in $hijos) { $x.ProcessId; Descendientes $x.ProcessId }
}
if (Test-Path $py) {
    $o = Join-Path $env:TEMP 'aria_diag_out.txt'
    $e = Join-Path $env:TEMP 'aria_diag_err.txt'
    Remove-Item $o, $e -ErrorAction SilentlyContinue
    $env:QT_QPA_PLATFORM = 'offscreen'
    $p = Start-Process -FilePath $py -ArgumentList 'aria_main.py' -WorkingDirectory (Join-Path $Repo 'ARIA_APP') -RedirectStandardOutput $o -RedirectStandardError $e -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 15
    $ids = @($p.Id) + @(Descendientes $p.Id)
    "NOTA: el python de .venv\Scripts es un lanzador pequeno; la memoria real esta en el proceso hijo."
    foreach ($id in $ids) {
        $pr = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($pr) { "PID {0} {1} | WS pico {2} MB | hilos {3}" -f $id, $pr.ProcessName, [math]::Round($pr.PeakWorkingSet64 / 1MB, 1), $pr.Threads.Count }
        else { "PID $id ya no existe (el programa termino)" }
    }
    $tcp = @(); foreach ($id in $ids) { $tcp += @(Get-NetTCPConnection -OwningProcess $id -ErrorAction SilentlyContinue) }
    $udp = @(); foreach ($id in $ids) { $udp += @(Get-NetUDPEndpoint -OwningProcess $id -ErrorAction SilentlyContinue) }
    "TCP del arbol: " + $tcp.Count + "   UDP del arbol: " + $udp.Count
    foreach ($c in $tcp) { "  TCP {0}:{1} -> {2}:{3} {4}" -f $c.LocalAddress, $c.LocalPort, $c.RemoteAddress, $c.RemotePort, $c.State }
    foreach ($c in $udp) { "  UDP {0}:{1}" -f $c.LocalAddress, $c.LocalPort }
    "--- salida estandar (ultimas 25 lineas):"
    if (Test-Path $o) { Get-Content $o -Tail 25 }
    "--- error estandar (ultimas 25 lineas):"
    if (Test-Path $e) { Get-Content $e -Tail 25 }
    foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
    "procesos de ARIA vivos tras cerrar: " + @($ids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }).Count
} else { "sin .venv, no se puede arrancar" }

T "FIN DEL DIAGNOSTICO"
