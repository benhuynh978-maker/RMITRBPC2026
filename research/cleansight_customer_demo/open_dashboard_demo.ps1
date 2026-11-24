# MO dashboard demo (ssc-v2, che do "Demo simulation": thanh pho mo phong 100 camera) tren laptop va bat Tailscale Funnel cong rieng.
#
# Chay (PowerShell, tu thu muc nay):
#   powershell -ExecutionPolicy Bypass -File open_dashboard_demo.ps1
#
# Cac buoc: build dashboard (mo san o che do Demo simulation), chay may chu tinh o 127.0.0.1:5175, bat Funnel cong 10000.
# Khong can backend Node: du lieu demo nam trong ban build. Laptop tat thi khong xem duoc.
# KHONG dung cong 443 (dich vu CleanSight), 8443 (ESP32), 8444 (demo cu). KHONG chay 'tailscale funnel reset'.
param(
    [string]$Python = "C:\Users\ASUS\Desktop\SSC\.venv\Scripts\python.exe",
    [int]$Port = 5175,
    [int]$FunnelPort = 10000
)

$ErrorActionPreference = "Stop"
$app = Join-Path $PSScriptRoot "..\..\ssc-v2\ssc-road-alerts"
$pidFile = Join-Path $PSScriptRoot "dashboard_demo.pid"

if (-not (Test-Path $Python)) { throw "Khong thay python: $Python  (dung -Python de chi duong dan python.exe)" }
if (-not (Test-Path (Join-Path $app "package.json"))) { throw "Khong thay ssc-v2\ssc-road-alerts (da git pull chua?)" }
if ($FunnelPort -in 443, 8443, 8444) { throw "Cong $FunnelPort dang dung cho he thong khac. Dung 10000." }
if (Test-Path $pidFile) {
    $old = [int](Get-Content $pidFile)
    if (Get-Process -Id $old -ErrorAction SilentlyContinue) { throw "Dashboard demo co ve dang chay (pid $old). Chay close_dashboard_demo.ps1 truoc." }
    Remove-Item $pidFile
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Cong $Port dang co chuong trinh khac dung. Dung -Port de doi, hoac chay close_dashboard_demo.ps1." }

# 1) Build: mo san o che do Demo simulation (khong anh huong cach chay binh thuong cua ssc-v2)
Push-Location $app
try {
    if (-not (Test-Path "node_modules")) { npm install; if ($LASTEXITCODE -ne 0) { throw "npm install that bai" } }
    $env:VITE_DEFAULT_SOURCE = "demo"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build that bai" }
} finally {
    Remove-Item Env:VITE_DEFAULT_SOURCE -ErrorAction SilentlyContinue
    Pop-Location
}
$dist = (Resolve-Path (Join-Path $app "dist")).Path

# 2) May chu tinh chi nghe 127.0.0.1
$proc = Start-Process $Python -ArgumentList "-m", "http.server", "$Port", "--bind", "127.0.0.1", "--directory", "`"$dist`"" -PassThru -WindowStyle Minimized
$proc.Id | Set-Content $pidFile
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 3 | Out-Null; $ready = $true; break } catch { }
}
if (-not $ready) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    throw "May chu tinh khong tra loi o cong $Port."
}

# 3) Funnel cong rieng
tailscale funnel --bg --https=$FunnelPort "http://127.0.0.1:$Port"
if ($LASTEXITCODE -ne 0) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    throw "Khong bat duoc Tailscale Funnel tren cong $FunnelPort."
}

Write-Host ""
Write-Host "DASHBOARD DEMO DANG MO. Trang thai Funnel:" -ForegroundColor Green
tailscale funnel status
Write-Host ""
Write-Host "Viec can lam:" -ForegroundColor Yellow
Write-Host "  - Mo dia chi https://<ten-may>.ts.net:$FunnelPort/ (xem dong cong $FunnelPort o tren) bang dien thoai 4G de kiem tra."
Write-Host "  - Du lieu la MO PHONG (trang co banner SIMULATION). Khi khong can nua chay close_dashboard_demo.ps1."
