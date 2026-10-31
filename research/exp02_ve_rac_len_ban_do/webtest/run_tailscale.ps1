# Chạy máy chủ webtest CHỈ trên địa chỉ Tailscale (không nghe 0.0.0.0, không mở ra Wi-Fi nhà).
# Cách dùng (PowerShell):  .\run_tailscale.ps1
# Cần: đã cài và đăng nhập Tailscale trên laptop (và trên điện thoại).

Set-Location -LiteralPath $PSScriptRoot

$port = 8120

# 1) Tìm tailscale.exe: PATH trước, rồi thư mục cài mặc định
$ts = $null
$cmd = Get-Command tailscale -ErrorAction SilentlyContinue
if ($cmd) { $ts = $cmd.Source }
elseif (Test-Path "C:\Program Files\Tailscale\tailscale.exe") { $ts = "C:\Program Files\Tailscale\tailscale.exe" }
if (-not $ts) {
    Write-Host "LỖI: không tìm thấy Tailscale (không có trong PATH và không có C:\Program Files\Tailscale\tailscale.exe)." -ForegroundColor Red
    Write-Host "Hãy cài Tailscale (https://tailscale.com/download), đăng nhập, rồi chạy lại." -ForegroundColor Red
    exit 1
}

# 2) Lấy IPv4 Tailscale
$ip = $null
try { $ip = (& $ts ip -4 2>$null | Select-Object -First 1) } catch { $ip = $null }
if ($ip) { $ip = "$ip".Trim() }
if (-not $ip -or $ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
    Write-Host "LỖI: không lấy được địa chỉ IPv4 Tailscale (lệnh 'tailscale ip -4' không trả về IP)." -ForegroundColor Red
    Write-Host "Hãy mở Tailscale, đăng nhập/bật kết nối rồi chạy lại." -ForegroundColor Red
    exit 1
}

$py = Join-Path $PSScriptRoot "..\..\..\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "LỖI: không thấy Python của dự án: $py" -ForegroundColor Red
    exit 1
}

# 3) Mã truy cập (tự sinh một lần, lưu data\access_code.txt, hoặc lấy từ WEBTEST_ACCESS_CODE nếu đã đặt)
$code = (& $py -B -c "import server; print(server.store.get_access_code())" | Select-Object -Last 1)
if ($code) { $code = "$code".Trim() }
if (-not $code) {
    Write-Host "LỖI: không đọc được mã truy cập." -ForegroundColor Red
    exit 1
}

$env:WEBTEST_HOST = $ip
$env:WEBTEST_PORT = "$port"

Write-Host "Laptop: http://${ip}:${port}/#${code}"
Write-Host "Điện thoại: http://${ip}:${port}/phone#${code}"

& $py -B -m uvicorn server:app --host $ip --port $port
