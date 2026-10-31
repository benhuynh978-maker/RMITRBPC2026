# webtest: trang thử nghiệm "up ảnh có rác -> hiện lên bản đồ"

Trang web một file (`web/index.html`, HTML + CSS + JS thuần, bản đồ Leaflet 1.9.4 tải từ CDN unpkg) cộng với
máy chủ FastAPI (`server.py`) chạy trên máy cá nhân. Mục đích: người dùng tự thử xem thuật toán
(hiệu chỉnh bằng bảng ArUco -> chiếu vùng rác lên bản đồ) có khả thi và đúng như kỳ vọng không.
Đây là bản thử nghiệm, không thay thế hệ thống chính.

## Cách chạy (PowerShell)

```powershell
cd C:\Users\ASUS\Desktop\SSC\research\exp02_ve_rac_len_ban_do\webtest
C:\Users\ASUS\Desktop\SSC\.venv\Scripts\python.exe -B -m uvicorn server:app --host 127.0.0.1 --port 8120
```

Sau đó mở trình duyệt tại http://127.0.0.1:8120/ . Muốn dừng: bấm `Ctrl+C` trong cửa sổ PowerShell.
Trang cần Internet để tải bản đồ nền OpenStreetMap và thư viện Leaflet (CDN).

Thanh trên cùng của trang cho biết: máy chủ có chạy không, đã hiệu chỉnh chưa, model AI đã nạp chưa.
Nếu hiện "không kết nối được máy chủ" nghĩa là chưa chạy lệnh trên.

## Dùng với điện thoại (Tailscale) và mã truy cập

Cài Tailscale trên laptop và điện thoại, đăng nhập CÙNG một tài khoản, rồi chạy trên laptop:

```powershell
cd C:\Users\ASUS\Desktop\SSC\research\exp02_ve_rac_len_ban_do\webtest
.\run_tailscale.ps1
```

Script lấy IPv4 Tailscale (`tailscale ip -4`), chỉ nghe đúng địa chỉ đó (KHÔNG nghe `0.0.0.0`, Wi-Fi nhà không thấy được),
rồi in hai dòng: `Laptop: http://<ip>:8120/#<mã>` và `Điện thoại: http://<ip>:8120/phone#<mã>`. Mở đúng đường dẫn đó
(phần `#<mã>` tự điền mã truy cập). Không có Tailscale thì script báo lỗi và thoát.

- **Mã truy cập**: 6 chữ số, tự sinh một lần và lưu ở `data/access_code.txt` (các lần chạy lại giữ nguyên mã; xoá file để đổi mã, rồi chạy lại server). Nhập sai quá 10 lần trong 60 giây từ một địa chỉ thì địa chỉ đó bị chặn 60 giây (HTTP 429).
  Mã cũng được in ra console khi máy chủ khởi động. Đặt biến môi trường `WEBTEST_ACCESS_CODE` để dùng mã riêng (dùng cho test).
- Mọi `/api/*` phải kèm header `X-Access-Code: <mã>`, thiếu hoặc sai thì máy chủ trả 401
  `{"ok": false, "error": "Missing or wrong access code."}`. Không cần mã: `GET /`, `GET /phone`, `GET /web/*`, `GET /api/health`.
- Chạy cục bộ không qua Tailscale: lệnh `uvicorn` ở trên vẫn dùng được (mặc định 127.0.0.1); khi chạy `python server.py`
  thì host/port lấy từ `WEBTEST_HOST` (mặc định 127.0.0.1) và `WEBTEST_PORT` (mặc định 8120).

Endpoint mới / đổi (mọi lỗi dạng `{"ok": false, "error": "..."}`):

| Endpoint | Tác dụng |
|---|---|
| `GET /phone` | trang chụp ảnh cho điện thoại (`web/phone.html`) |
| `GET /api/status` | `calibrated`, `observation_count`, `latest_observation_id`, `inbox_count`, `latest_inbox_id`; rẻ, trang gọi mỗi 3 giây |
| `POST /api/inbox` (multipart `photo`) | điện thoại gửi ảnh có bảng; lưu NGUYÊN bytes gốc (giữ EXIF tiêu cự) ở `data/inbox/<id>.bin` + `.json`; trả `inbox_id`, `created_at`, `size_bytes`, `image_size`, `has_focal` |
| `GET /api/inbox` | danh sách ảnh đang chờ (mới nhất trước) kèm ảnh thu nhỏ `thumb_jpg_b64` (cạnh dài 240 px) |
| `POST /api/calibrate` | `photo` nay là tuỳ chọn; thêm field `inbox_id`. Phải có ĐÚNG MỘT trong hai (cả hai hoặc không có -> 422; `inbox_id` không có/hết hạn -> 404) |

`inbox` giữ tối đa 10 ảnh và tự xoá ảnh quá 24 giờ. Các endpoint còn lại giữ nguyên hành vi (chỉ thêm kiểm mã).

## Sơ đồ 4 bước

1. **Hiệu chỉnh bằng bảng**: chọn ảnh có bảng ArUco, nhập cạnh thật của bảng (mm), bấm "Dò bảng". Trang hiện ảnh
   đã dò (mũi tên +Y xanh dương, +X đỏ), số px bảng chiếm (cần >= 50 px), nguồn góc mở ống kính, cảnh báo (nếu có).
2. **Đặt bảng lên bản đồ**: bấm vị trí đặt bảng, kéo đầu mũi tên để chỉ hướng cạnh +Y của bảng
   (góc la bàn, 0° = Bắc, 90° = Đông). Có nút nhích 5 cm (▲▼◀▶) và xoay 1° (⟲ ⟳).
3. **Xem trước & lưu**: vùng xanh = phần mặt đất camera nhìn thấy, điểm xanh dương = bảng, điểm xanh lá = camera.
   Đối chiếu bằng mắt với thực tế, nhích/xoay cho khớp rồi bấm "Lưu hiệu chỉnh".
4. **Gửi ảnh có rác**: chọn ảnh chụp từ CÙNG vị trí cố định, bấm "Gửi và vẽ lên bản đồ". Vùng rác hiện màu đỏ
   (lần mới nhất) hoặc vàng hổ phách `#fcd34d` (các lần cũ); bấm vào vùng để xem diện tích (m²) và độ tin cậy trung bình của ảnh. Có lịch sử các lần gửi
   (ẩn/hiện từng lần) và nút "Xoá tất cả".

Tải lại trang: trạng thái nằm ở máy chủ nên trang tự nhảy tới bước 4 nếu đã có hiệu chỉnh đã lưu, vẽ lại vùng camera nhìn thấy, bảng, camera và lịch sử.
Bấm "Hiệu chỉnh lại" để làm lại từ bước 1.

## Dữ liệu lưu ở đâu, xoá để làm lại từ đầu

- `webtest/data/` : `pending/<id>.json` (kết quả dò bảng chưa lưu), `inbox/` (ảnh điện thoại gửi, tối đa 10), `observations.json` (lịch sử các lần gửi ảnh) và `access_code.txt` (mã truy cập).
- `calibration/WEB-DEMO.json` (trong thư mục `exp02_ve_rac_len_ban_do`): hiệu chỉnh đã lưu.

Giữ lại tối đa: `pending` 20 file và 24 giờ (file cũ hơn tự bị xoá), `observations.json` 50 lần gửi gần nhất.

Biến môi trường (tuỳ chọn, đặt trong PowerShell trước khi chạy máy chủ, ví dụ `$env:WEBTEST_DATA_DIR = "D:\du_lieu_thu"`):

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `WEBTEST_CALIB_DIR` | `exp02_ve_rac_len_ban_do\calibration` | thư mục chứa `WEB-DEMO.json` (hiệu chỉnh đã lưu) |
| `WEBTEST_DATA_DIR` | `webtest\data` | thư mục chứa `pending\`, `inbox\`, `observations.json`, `access_code.txt` |
| `WEBTEST_ACCESS_CODE` | (tự sinh, lưu `access_code.txt`) | ghi đè mã truy cập 6 số |
| `WEBTEST_HOST` / `WEBTEST_PORT` | `127.0.0.1` / `8120` | chỉ dùng khi chạy `python server.py` (`run_tailscale.ps1` tự đặt) |
| `WEBTEST_MIN_AREA_FRAC` | `0.00003` (≥ 20 px) | ngưỡng bỏ vùng nhiễu: vùng nhỏ hơn tỉ lệ này của diện tích ảnh bị bỏ (và được báo). Trước đây 0.0005 làm mất rác nhỏ |
| `WEBTEST_CONF` | `0.25` | ngưỡng tin cậy của model; hạ thấp (ví dụ 0.15) để thấy thêm rác nhỏ, đổi lại dễ khoanh nhầm hơn |
| `WEBTEST_MODEL_PATH` | `<gốc dự án>\runs\segment\runs\train\baseline_v1_rev2\weights\best.pt` | file trọng số model YOLO dùng khi gửi ảnh |

Làm lại từ đầu: tắt máy chủ (`Ctrl+C`), xoá file `calibration\WEB-DEMO.json` và xoá nội dung thư mục `webtest\data\`,
rồi chạy lại máy chủ. (Chỉ xoá lịch sử các lần gửi ảnh thì bấm "Xoá tất cả" trên trang.)
Đừng xoá `calibration\DEMO-CAM.json` — đó là file của demo khác.

## Giới hạn (nhớ khi đọc kết quả)

- Chỉ đúng khi điện thoại/camera **cố định** (không xê dịch giữa ảnh hiệu chỉnh và ảnh có rác) và mặt đất **phẳng**.
- Vật có chiều cao bị vẽ phóng to/lệch ra xa camera (phần mô hình chỉ biết mặt đất).
- Model AI (YOLO) có thể bỏ sót rác hoặc nhận nhầm, nhất là trong nhà.
- Ảnh gửi ở bước 4 phải **cùng tỉ lệ khung hình** với ảnh hiệu chỉnh (lệch tối đa 1%), tức cùng điện thoại, cùng hướng ngang/dọc,
  cùng chế độ chụp; khác thì máy chủ từ chối.
- Ảnh có cạnh dài hơn 2048 px được thu nhỏ trước khi xử lý (tỉ lệ khung giữ nguyên, không ảnh hưởng vị trí).
- Bảng phải chiếm >= 50 px trên ảnh; xa quá thì máy chủ từ chối.
- Chỉ một camera (`WEB-DEMO`) và một hiệu chỉnh tại một thời điểm; chỉ ban ngày/đủ sáng.
- Vị trí bảng trên bản đồ do bạn đặt bằng mắt, nên độ chính xác tuyệt đối trên bản đồ phụ thuộc cách đặt;
  cái đáng đo là khoảng cách tương đối quanh bảng (xem `docs/HUONG_DAN_THU_O_NHA.md`).
- Hướng dẫn thử từng bước cho người không chuyên: `../docs/HUONG_DAN_THU_O_NHA.md`.

## Đo thời gian và đọc số liệu (cho thử nghiệm)

- Mỗi lần gửi ảnh rác (`/api/observe` và `observations.json`) có thêm `received_at`, `processed_at` (UTC, chính xác ms),
  `processing_ms` và `calibration_created_at` (hiệu chỉnh đã dùng). Trang điện thoại hiện tổng thời gian gửi đo bằng đồng hồ
  điện thoại; trang laptop ghi "hiện trên bản đồ sau … s" cho ảnh đến từ điện thoại. Trang laptop tự cập nhật mỗi 3 giây
  **kể cả khi tab bị ẩn/che**.
- `doc_so_lieu.py`: CHỈ ĐỌC `observations.json` + file hiệu chỉnh, in vị trí tâm (Y, X, mét, hệ toạ độ bảng) và diện tích
  từng vùng rác; `--last N`, `--calib`, `--obs`, `--csv`, và `--dan yx|yxa|a [--copy] [--dot]` in khối số (mỗi lần gửi một dòng, cột cách bằng TAB)
  để dán thẳng vào Excel (`--copy` chép sẵn vào clipboard). Test: `test_doc_so_lieu.py`.
  Hướng dẫn dùng trong thử nghiệm: `../docs/HUONG_DAN_THU_NGHIEM_GHI_SO_LIEU.md` mục 8.6.

## Chạy test

```powershell
cd C:\Users\ASUS\Desktop\SSC\research\exp02_ve_rac_len_ban_do\webtest
..\..\..\.venv\Scripts\python.exe -B test_server.py
```

(hoặc `-m pytest test_server.py -q` nếu đã cài pytest), và `..\..\..\.venv\Scripts\python.exe -B test_doc_so_lieu.py`. Test dùng thư mục tạm riêng, mã truy cập `123456`, model giả cho
phần vị trí/diện tích và một ca chạy model thật.
