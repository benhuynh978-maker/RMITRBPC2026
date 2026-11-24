# DONG dashboard demo: tat Funnel DUNG cong, dung may chu tinh. An toan khi chay nhieu lan.
#
# Chay (PowerShell, tu thu muc nay):
#   powershell -ExecutionPolicy Bypass -File close_dashboard_demo.ps1
#
# KHONG dung 'tailscale funnel reset': lenh do xoa ca cau hinh Funnel cua cong 8443 (ESP32), 8444 va 443.
param(
    [int]$Port = 5175,
    [int]$FunnelPort = 10000
)

$ErrorActionPreference = "Continue"
$pidFile = Join-Path $PSScriptRoot "dashboard_demo.pid"

if ($FunnelPort -in 443, 8443, 8444) { throw "Khong duoc tat cong $FunnelPort bang script nay (dang dung cho he thong khac)." }

tailscale funnel --https=$FunnelPort off

if (Test-Path $pidFile) {
    Stop-Process -Id ([int](Get-Content $pidFile)) -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1
Write-Host ""
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "CANH BAO: cong $Port van con chuong trinh dang nghe. Hay dong thu cong." -ForegroundColor Red
} else {
    Write-Host "Da dong may chu o cong $Port." -ForegroundColor Green
}
Write-Host "Trang thai Funnel hien tai (cong $FunnelPort khong duoc con o day):" -ForegroundColor Yellow
tailscale funnel status
