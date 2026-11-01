<#
  import-kali-aria.ps1   (Windows PowerShell 5.1, NO requiere admin)

  Descarga la VM preconstruida de Kali para VirtualBox, verifica el SHA-256,
  la extrae, la registra, la aisla (NAT, sin portapapeles ni arrastrar) y
  toma un snapshot limpio.

  Uso:
    powershell -ExecutionPolicy Bypass -File .\import-kali-aria.ps1
    powershell -ExecutionPolicy Bypass -File .\import-kali-aria.ps1 -Dir "$env:USERPROFILE\ARIA-Kali" -MemMB 4096 -Cpus 4

  Requisito previo: VirtualBox YA instalado (instalarlo si requiere admin).
#>
param(
    [string]$Dir  = (Join-Path $env:USERPROFILE "ARIA-Kali"),
    [int]$MemMB   = 4096,
    [int]$Cpus    = 4
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Vbm {
    # Ejecuta VBoxManage sin que stderr corte el script; devuelve la salida como texto.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & $script:vbm @args 2>&1 | Out-String
    $ErrorActionPreference = $prev
    return $out
}

# ---------- 1) VirtualBox y virtualizacion ----------
$vbm = Join-Path $env:ProgramFiles "Oracle\VirtualBox\VBoxManage.exe"
if (-not (Test-Path $vbm)) {
    throw "VirtualBox no esta instalado en '$vbm'. Instalarlo requiere admin (drivers del kernel). Pidele a quien administre el PC que lo instale una sola vez."
}
"VirtualBox: " + (Vbm --version).Trim()
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
if (-not $cpu.VirtualizationFirmwareEnabled) {
    Write-Warning "Virtualizacion (SVM / VT-x) aparece desactivada en BIOS/UEFI. Si la VM no arranca, activala en la BIOS."
}

# ---------- 2) Descubrir y descargar la imagen mas reciente ----------
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$base = "https://cdimage.kali.org/current/"
$idx  = (Invoke-WebRequest -Uri $base -UseBasicParsing).Content
if ($idx -is [byte[]]) { $idx = [Text.Encoding]::UTF8.GetString($idx) }
$name = [regex]::Matches($idx, 'kali-linux-[0-9.]+-virtualbox-amd64\.7z') |
        ForEach-Object { $_.Value } | Sort-Object -Unique | Select-Object -Last 1
if (-not $name) { throw "No encontre la imagen VirtualBox en $base (revisa https://www.kali.org/get-kali/#kali-virtual-machines)" }
"Imagen: $name"

$file = Join-Path $Dir $name
if (-not (Test-Path $file)) {
    $part = "$file.part"
    "Descargando (~3 GB, reanuda si se corta) ..."
    & curl.exe -L --fail -C - -o $part ($base + $name)
    if ($LASTEXITCODE -ne 0) { throw "Descarga fallida (curl $LASTEXITCODE). Vuelve a ejecutar el script: reanuda." }
    Move-Item -LiteralPath $part -Destination $file
}

# ---------- 3) Verificar SHA-256 contra SHA256SUMS ----------
$sums = (Invoke-WebRequest -Uri ($base + "SHA256SUMS") -UseBasicParsing).Content
if ($sums -is [byte[]]) { $sums = [Text.Encoding]::ASCII.GetString($sums) }
$line = ($sums -split "`n" | Where-Object { $_ -match [regex]::Escape($name) } | Select-Object -First 1)
if (-not $line) { throw "SHA256SUMS no lista $name" }
$want = ($line.Trim() -split '\s+')[0].ToLower()
$got  = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower()
"SHA-256 publicado = $want"
"SHA-256 calculado = $got"
if ($want -ne $got) { throw "SHA-256 NO COINCIDE. Borra '$file' y vuelve a ejecutar." }

# ---------- 4) Extraer (tar de Windows 11; si falla, 7zr.exe oficial) ----------
$vbox = Get-ChildItem -Path $Dir -Recurse -Filter *.vbox -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $vbox) {
    Push-Location $Dir
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & tar.exe -xf $name 2>$null
    $tarOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev
    $vbox = Get-ChildItem -Path $Dir -Recurse -Filter *.vbox -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $tarOk -or -not $vbox) {
        "tar no pudo extraer; usando 7zr.exe oficial ..."
        & curl.exe -L --fail -o 7zr.exe https://www.7-zip.org/a/7zr.exe
        if ($LASTEXITCODE -ne 0) { throw "No pude bajar 7zr.exe" }
        $sig = Get-AuthenticodeSignature .\7zr.exe
        "Firma de 7zr.exe: $($sig.Status) / $($sig.SignerCertificate.Subject)"
        if ($sig.Status -ne "Valid") { throw "7zr.exe sin firma valida; abortando" }
        & .\7zr.exe x $name -y
    }
    Pop-Location
    $vbox = Get-ChildItem -Path $Dir -Recurse -Filter *.vbox | Select-Object -First 1
}
if (-not $vbox) { throw "No aparecio ningun .vbox tras extraer" }

# ---------- 5) Registrar la VM ----------
$vmName = ([xml](Get-Content -LiteralPath $vbox.FullName -Raw)).VirtualBox.Machine.name
"VM: $vmName"
$known = Vbm list vms
if ($known -notmatch [regex]::Escape('"' + $vmName + '"')) {
    $r = Vbm registervm $vbox.FullName
    if ($LASTEXITCODE -ne 0) { throw "registervm fallo: $r" }
}

# ---------- 6) Dimensionar y aislar ----------
$r = Vbm modifyvm $vmName --memory $MemMB --cpus $Cpus --nic1 nat
if ($LASTEXITCODE -ne 0) { throw "modifyvm fallo: $r" }
$help = Vbm modifyvm
$clip = if ($help -match '--clipboard-mode') { '--clipboard-mode' } else { '--clipboard' }
$dnd  = if ($help -match '--drag-and-drop')  { '--drag-and-drop' }  else { '--draganddrop' }
Vbm modifyvm $vmName $clip disabled | Out-Null
Vbm modifyvm $vmName $dnd  disabled | Out-Null

"--- Configuracion resultante ---"
(Vbm showvminfo $vmName --machinereadable) -split "`r?`n" |
    Select-String -Pattern '^(memory|cpus|nic1|clipboard|draganddrop|SharedFolder)' |
    ForEach-Object { $_.Line }

# ---------- 7) Snapshot limpio ----------
if ((Vbm snapshot $vmName list) -notmatch 'base-limpia') {
    Vbm snapshot $vmName take base-limpia | Out-Null
    "Snapshot 'base-limpia' creado."
}

""
"LISTO. Arranca la VM con:"
"  & `"$vbm`" startvm `"$vmName`" --type gui"
"Login inicial: kali / kali  (cambialo con 'passwd' en el primer arranque)"
"Nombre de VM para los siguientes comandos: $vmName"
