# Chay dich vu CleanSight live demo va TU DONG KHOI DONG LAI neu tien trinh sap.
# Thuong KHONG chay truc tiep: open_demo.ps1 goi script nay trong mot cua so rieng (thu nho).
#
# Dich vu chi nghe 127.0.0.1 (Tailscale Funnel chuyen tiep vao day), tat access log de khong ghi dia chi IP.
param(
    [Parameter(Mandatory = $true)][string]$Origin,   # vd https://ten-site.netlify.app (CORS chi cho dung origin nay)
    [Parameter(Mandatory = $true)][string]$Python,   # duong dan python.exe cua .venv
    [int]$Port = 8140
)

Set-Location $PSScriptRoot
$env:CLEANSIGHT_ALLOWED_ORIGINS = $Origin
$env:YOLO_AUTOINSTALL = "False"   # khong de Ultralytics tu cai goi qua mang luc khoi dong
$env:PYTHONUTF8 = "1"

# Camera lab (tuy chon): neu co file cam.env cung thu muc (moi dong KEY=VALUE; dong bat dau bang # la ghi chu) thi nap vao moi truong.
# cam.env KHONG nam trong Git. Khong in gia tri ra man hinh.
$camEnv = Join-Path $PSScriptRoot "cam.env"
if (Test-Path $camEnv) {
    foreach ($dong in (Get-Content -LiteralPath $camEnv -Encoding UTF8)) {
        if ($dong -match '^\s*#') { continue }
        if ($dong -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            $giaTri = $Matches[2].Trim().Trim('"')
            Set-Item -Path ("Env:" + $Matches[1]) -Value $giaTri
        }
    }
    if ($env:CLEANSIGHT_CAM_ACCESS_CODE -and $env:CLEANSIGHT_CAM_INGEST_KEY) { Write-Host "Da nap cam.env: Camera lab BAT." -ForegroundColor Cyan }
    else { Write-Host "cam.env thieu CLEANSIGHT_CAM_ACCESS_CODE hoac CLEANSIGHT_CAM_INGEST_KEY: dich vu se tu choi khoi dong neu chi co mot trong hai." -ForegroundColor Yellow }
} else {
    Write-Host "Khong co cam.env: Camera lab TAT." -ForegroundColor DarkGray
}

$lanThu = 0
while ($true) {
    $lanThu++
    $gio = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$gio] (lan $lanThu) Khoi dong CleanSight live demo tai 127.0.0.1:$Port ..." -ForegroundColor Cyan

    & $Python -B -m uvicorn server:app --host 127.0.0.1 --port $Port --no-access-log

    $gio = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$gio] Dich vu da thoat (exit code $LASTEXITCODE). Khoi dong lai sau 3 giay..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}
