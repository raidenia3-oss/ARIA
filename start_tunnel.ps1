while ($true) {
    & "C:\Program Files\nodejs\node.exe" "C:\Users\User\AppData\Roaming\npm\node_modules\localtunnel\bin\lt.js" --port 8001 --subdomain aria-backend
    Start-Sleep -Seconds 2
}