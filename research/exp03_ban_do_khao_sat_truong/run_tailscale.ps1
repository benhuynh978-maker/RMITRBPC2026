# Chay cong cu KHAO SAT RAC (exp03) CHI tren dia chi Tailscale cua laptop (khong nghe 0.0.0.0, Wi-Fi truong khong thay duoc).
# Cach dung (PowerShell):  .\run_tailscale.ps1
# Can: da cai va dang nhap Tailscale tren laptop (va tren dien thoai). Chay RIENG, cong 8130, du lieu o thu muc data\ cua exp03.
# Khong dung Funnel, khong dung cong 8120 (webtest), 443, 8443, 8444, 10000.

Set-Location -LiteralPath $PSScriptRoot
$port = 8130

# 1) Tim tailscale.exe
$ts = $null
$cmd = Get-Command tailscale -ErrorAction SilentlyContinue
if ($cmd) { $ts = $cmd.Source }
elseif (Test-Path "C:\Program Files\Tailscale\tailscale.exe") { $ts = "C:\Program Files\Tailscale\tailscale.exe" }
if (-not $ts) {
    Write-Host "LOI: khong tim thay Tailscale. Hay cai Tailscale, dang nhap, roi chay lai." -ForegroundColor Red
    exit 1
}

# 2) Lay IPv4 Tailscale
$ip = $null
try { $ip = (& $ts ip -4 2>$null | Select-Object -First 1) } catch { $ip = $null }
if ($ip) { $ip = "$ip".Trim() }
if (-not $ip -or $ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
    Write-Host "LOI: khong lay duoc dia chi IPv4 Tailscale. Mo Tailscale, dang nhap/bat ket noi roi chay lai." -ForegroundColor Red
    exit 1
}

# 3) Python cua du an (.venv o thu muc goc repo)
$py = Join-Path $PSScriptRoot "..\..\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "LOI: khong thay Python cua du an: $py" -ForegroundColor Red
    exit 1
}

$env:PYTHONUTF8 = "1"
$env:YOLO_AUTOINSTALL = "False"   # khong de Ultralytics tu cai goi qua mang

# 4) Ma truy cap 6 so (tu sinh mot lan, luu data\access_code.txt; KHONG dua vao Git)
$code = (& $py -B -c "import svy_store; print(svy_store.get_access_code())" | Select-Object -Last 1)
if ($code) { $code = "$code".Trim() }
if (-not $code) {
    Write-Host "LOI: khong doc duoc ma truy cap." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Laptop (ra soat, xuat ban trinh bay):  http://${ip}:${port}/#${code}"
Write-Host "Dien thoai (chup diem khao sat):       http://${ip}:${port}/phone#${code}"
Write-Host "Cach 1 (chep file): tha anh goc vao   $PSScriptRoot\thu_muc_anh   roi bam 'Nap anh tu thu muc'"
Write-Host "Dung lai: bam Ctrl+C trong cua so nay."
Write-Host ""

& $py -B -m uvicorn svy_server:app --host $ip --port $port --no-access-log
