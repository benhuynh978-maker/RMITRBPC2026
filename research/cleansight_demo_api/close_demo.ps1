# DONG demo CleanSight: tat Funnel DUNG cong, dung dich vu. An toan khi chay nhieu lan.
#
# Chay (PowerShell, tu thu muc nay):
#   powershell -ExecutionPolicy Bypass -File close_demo.ps1
#
# KHONG dung 'tailscale funnel reset': lenh do xoa ca cau hinh Funnel cua cong 8443 (ESP32) va 8444.
param(
    [int]$Port = 8140,
    [int]$FunnelPort = 443
)

$ErrorActionPreference = "Continue"
$pidFile = Join-Path $PSScriptRoot "demo.pid"

if ($FunnelPort -in 8443, 8444) { throw "Khong duoc tat cong $FunnelPort bang script nay (dang dung cho he thong khac)." }

# 1) Tat Funnel o cong cua demo (khong dong vao cong khac)
tailscale funnel --https=$FunnelPort off

# 2) Dung cua so giam sat truoc (neu khong no se khoi dong lai dich vu), roi dung dich vu theo cong
if (Test-Path $pidFile) {
    $supervisor = [int](Get-Content $pidFile)
    Stop-Process -Id $supervisor -Force -ErrorAction SilentlyContinue
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1
Write-Host ""
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "CANH BAO: cong $Port van con chuong trinh dang nghe. Hay dong thu cong." -ForegroundColor Red
} else {
    Write-Host "Da dong dich vu o cong $Port." -ForegroundColor Green
}
Write-Host "Trang thai Funnel hien tai (cong $FunnelPort khong duoc con o day):" -ForegroundColor Yellow
tailscale funnel status
Write-Host "Kiem tra tu dien thoai 4G: trang web phai bao 'Live demo: offline'."
