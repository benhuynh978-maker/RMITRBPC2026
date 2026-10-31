# Chay uvicorn va TU DONG KHOI DONG LAI neu tien trinh sap (vd 1 anh loi lam crash o
# tang native OpenCV/PyTorch, vuot qua duoc try/except trong Python). Dung script nay
# thay vi goi uvicorn truc tiep khi can service song lau cho giam khao test khong ai
# truc man hinh.
#
# Chay (ban v2, cong 8110):
#   cd C:\Users\ASUS\Desktop\SSC\ssc-v2\test-WebUI-modelAI\server
#   powershell -ExecutionPolicy Bypass -File run_resilient.ps1
#
# Dung: Ctrl+C (co the can bam 2 lan vi dang trong vong lap).

$python = Join-Path $PSScriptRoot "..\..\..\.venv\Scripts\python.exe"
$lanThu = 0

while ($true) {
    $lanThu++
    $gio = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$gio] (lan $lanThu) Khoi dong uvicorn..." -ForegroundColor Cyan

    & $python -B -m uvicorn app:app --host 0.0.0.0 --port 8110

    $gio = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$gio] uvicorn da thoat (exit code $LASTEXITCODE). Khoi dong lai sau 3 giay..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}
