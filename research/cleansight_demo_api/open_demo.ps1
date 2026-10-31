# MO demo CleanSight cho ban giam khao: khoi dong dich vu, cho model nap xong, roi bat Tailscale Funnel.
#
# Chay (PowerShell, tu thu muc nay):
#   powershell -ExecutionPolicy Bypass -File open_demo.ps1 -Origin https://ten-site.netlify.app
#
# -Origin la dia chi trang web tren Netlify (khong co dau / o cuoi). Day la nguon DUY NHAT duoc phep goi dich vu.
# Moi ngay: chay script nay luc ~17:45, va close_demo.ps1 luc 23:00.
param(
    [Parameter(Mandatory = $true)][string]$Origin,
    [string]$Python = "C:\Users\ASUS\Desktop\SSC\.venv\Scripts\python.exe",
    [int]$Port = 8140,
    [int]$FunnelPort = 443
)

$ErrorActionPreference = "Stop"
$pidFile = Join-Path $PSScriptRoot "demo.pid"
$runner = Join-Path $PSScriptRoot "run_service.ps1"

if (-not (Test-Path $Python)) { throw "Khong thay python: $Python  (dung -Python de chi duong dan python.exe cua .venv)" }
if ($Origin -notmatch '^https?://[^/\s]+$') { throw "Origin phai co dang https://ten-site.netlify.app (khong co dau / o cuoi)." }
if ($FunnelPort -in 8443, 8444) { throw "Cong $FunnelPort dang dung cho he thong khac. Dung 443 hoac 10000." }

if (Test-Path $pidFile) {
    $old = [int](Get-Content $pidFile)
    if (Get-Process -Id $old -ErrorAction SilentlyContinue) { throw "Demo co ve dang chay (pid $old). Chay close_demo.ps1 truoc." }
    Remove-Item $pidFile
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Cong $Port dang co chuong trinh khac dung. Dung -Port de doi, hoac chay close_demo.ps1."
}

# 1) Khoi dong dich vu trong mot cua so rieng (tu khoi dong lai neu sap)
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Origin `"$Origin`" -Python `"$Python`" -Port $Port"
$proc = Start-Process powershell -ArgumentList $arguments -PassThru -WindowStyle Minimized
$proc.Id | Set-Content $pidFile
Write-Host "Da khoi dong dich vu (pid $($proc.Id)). Dang cho model nap xong..." -ForegroundColor Cyan

# 2) Cho den khi /api/health bao ready
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 2
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($h.ready) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Write-Host "Dich vu KHONG san sang sau 3 phut. Khong bat Funnel. Dang dong lai..." -ForegroundColor Red
    & (Join-Path $PSScriptRoot "close_demo.ps1") -Port $Port -FunnelPort $FunnelPort
    throw "Khong khoi dong duoc dich vu. Xem cua so dich vu (da dong) hoac chay run_service.ps1 truc tiep de xem loi."
}

# 3) Bat Funnel dung cong da chon
tailscale funnel --bg --https=$FunnelPort "http://127.0.0.1:$Port"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bat Funnel that bai (exit $LASTEXITCODE). Dang dong lai..." -ForegroundColor Red
    & (Join-Path $PSScriptRoot "close_demo.ps1") -Port $Port -FunnelPort $FunnelPort
    throw "Khong bat duoc Tailscale Funnel tren cong $FunnelPort."
}

Write-Host ""
Write-Host "DEMO DANG MO. Trang thai Funnel:" -ForegroundColor Green
tailscale funnel status
Write-Host ""
Write-Host "Viec can lam:" -ForegroundColor Yellow
Write-Host "  - Kiem tra tu dien thoai dung 4G (khong dung Wi-Fi nha): mo trang web, muc 'Live demo: online'."
Write-Host "  - Luc 23:00 chay close_demo.ps1."
Write-Host "  - Cong 8444 (demo cu, co LUU anh) van dang mo neu ban chua tat: tailscale funnel --https=8444 off"
