# CleanSight live demo API

Dịch vụ nhỏ, **tách biệt hoàn toàn** với hệ thống chính, để ban giám khảo tải ảnh của họ lên trang "Try the AI" của website CleanSight và nhận kết quả từ model thật (`baseline_v1_rev2`).

- Nhận **một ảnh** (JPEG/PNG), chạy model, trả ảnh đã khoanh + mức rác + mức che cống (hoặc "không phát hiện").
- **Không lưu ảnh**: ảnh chỉ nằm trong RAM trong lúc xử lý. Không log nội dung ảnh, tên tệp hay IP.
- Chỉ nghe `127.0.0.1:8140`. Ra Internet duy nhất qua **Tailscale Funnel cổng 443**.
- Không đụng tới `ssc-road-alerts/`, `inference/`, `test-WebUI-modelAI/`, cổng 8000/8443/8444/8100.

> Phạm vi trung thực: kết quả là **ước tính của AI** (model còn bỏ sót rác, recall 0,44), công thức một ảnh đơn không có vùng cống cố định. Dịch vụ không phải "thời gian thực" và không dự báo ngập.

## Mỗi ngày (18:00–23:00 giờ Việt Nam, 1–30/11/2026)

Cần: laptop cắm sạc, tắt chế độ ngủ, đã đăng nhập Tailscale.

**Mở (khoảng 17:45)**, trong PowerShell:
```powershell
cd C:\Users\ASUS\Desktop\CleanSight-test\research\cleansight_demo_api
powershell -ExecutionPolicy Bypass -File open_demo.ps1 -Origin https://TEN-SITE-CUA-BAN.netlify.app
```
Script sẽ: khởi động dịch vụ → chờ model nạp xong → bật Funnel cổng 443 → in trạng thái.

**Đóng (23:00):**
```powershell
powershell -ExecutionPolicy Bypass -File close_demo.ps1
```
Script tắt Funnel **đúng cổng 443** (không đụng 8443/8444) rồi dừng dịch vụ. Chạy nhiều lần cũng an toàn.

Sau khi mở và sau khi đóng, hãy mở trang web **bằng điện thoại dùng 4G** (không dùng Wi-Fi nhà) và nhìn dòng trạng thái: phải là *Live demo: online* khi mở, *offline* khi đóng.

> **Không bao giờ chạy `tailscale funnel reset`**: lệnh đó xoá luôn cấu hình Funnel của ESP32 (8443) và demo cũ (8444).

## Demo cũ ở cổng 8444
`test-WebUI-modelAI` (cổng 8100 → Funnel 8444) **lưu ảnh gốc** người dùng gửi vào thư mục `uploads/`, trái với lời hứa "không lưu ảnh" của trang CleanSight. Nếu chưa đưa link đó cho ai, nên tắt trong thời gian demo CleanSight mở:
```powershell
tailscale funnel --https=8444 off
```
(Bật lại: `tailscale funnel --bg --https=8444 http://localhost:8100`.) Dịch vụ này không tự thay đổi gì ở đó.

## Cấu hình
| Biến môi trường | Mặc định | Ý nghĩa |
|---|---|---|
| `CLEANSIGHT_ALLOWED_ORIGINS` | **bắt buộc** | Origin được phép gọi (phân tách bằng dấu phẩy). Thiếu hoặc có `*` → dịch vụ **không khởi động**. `open_demo.ps1` đặt giá trị này từ `-Origin`. |
| `CLEANSIGHT_MAX_BODY_BYTES` | 8 MB | Kích thước ảnh tối đa gửi lên |
| `CLEANSIGHT_MAX_PIXELS` | 40 000 000 | Ảnh nhiều điểm ảnh hơn bị từ chối **trước khi giải mã** |
| `CLEANSIGHT_MAX_SIDE_PX` | 1600 | Cạnh dài tối đa đưa vào model |
| `CLEANSIGHT_RATE_PER_MINUTE` / `_PER_HOUR` | 5 / 50 | Giới hạn theo IP |
| `CLEANSIGHT_RATE_GLOBAL_PER_MINUTE` | 20 | Trần chung toàn dịch vụ |
| `CLEANSIGHT_MAX_WAITING` | 3 | Số yêu cầu được xếp hàng chờ (ngoài 1 yêu cầu đang chạy) |
| `CLEANSIGHT_LAB_LIGHT_PER_MINUTE` / `CLEANSIGHT_LAB_HEAVY_PER_MINUTE` | 90 / 12 | Giới hạn theo IP của phòng thử: mọi lời gọi / lời gọi chạy model (vẽ rác lên bản đồ, đo vùng cống) |

## API
`GET /api/health` → `{"status":"ok","ready":true}`

`POST /api/analyze`: thân yêu cầu là **ảnh thô**, `Content-Type: image/jpeg` hoặc `image/png` (không dùng multipart, vì thư viện web sẽ ghi file > 1 MB ra thư mục tạm).

Thành công (200): `{"waste_pct", "level_index" (-1 = dưới mức Low; 0..3 = Low/Medium/High/Severe), "drain_pct" (null = không phát hiện cống), "annotated_jpg" (data URL)}`.
Lỗi: `{"error", "code"}`. Mã: `invalid_image` 400, `too_big` 413, `unsupported_type` 415, `too_large` / `too_small` / `too_dark` 422, `rate_limited` / `busy_global` 429 (kèm `Retry-After`), `busy` / `not_ready` 503, `server_error` 500.

### Phòng hiệu chỉnh (`lab.py`, đăng ký trong `server.py`)
Chỉ dùng ảnh mẫu nằm trong `lab_samples/` (giám khảo không tải ảnh lên), trạng thái giữ trong RAM theo header `X-Lab-Session` (hết hạn sau 30 phút không dùng, tối đa 40 phiên, không ghi đĩa).

| Đường dẫn | Việc |
|---|---|
| `GET /api/lab/board/samples` | Danh sách ảnh mẫu (bảng ArUco / ảnh có rác) |
| `POST /api/lab/board/detect` | `{sample_id, marker_size_mm, fov_deg?}` → dò bảng, tư thế camera. Bảng nhỏ hơn 50 px → 422 `board_too_small` |
| `GET /api/lab/board/footprint`, `POST …/calibration/save`, `GET …/calibration` | Xem trước vùng nhìn, lưu hiệu chỉnh, đọc lại |
| `POST /api/lab/board/observe` | `{sample_id}` → chạy model, vẽ vùng rác lên bản đồ (m², toạ độ so với tâm bảng) |
| `GET/DELETE /api/lab/board/observations` | Danh sách / xoá các lần gửi |
| `GET /api/lab/drain/samples`, `POST /api/lab/drain/measure` | `{sample_id, polygon}` (3–64 điểm, đa giác hợp lệ) → % rác che vùng cống |

Hai nhóm giới hạn theo IP riêng cho phòng thử (xem bảng cấu hình), dùng chung hàng đợi/khoá model với `/api/analyze`.

## Kiểm thử
```bash
python -B test_demo_api.py        # 45 kiểm tra, có chạy model thật
python -B test_lab_api.py         # 70 kiểm tra phòng hiệu chỉnh: luồng, cô lập phiên, không ghi đĩa, giới hạn, CORS
```
Kiểm: định dạng/kích thước/ảnh hỏng, ảnh "bom" điểm ảnh không bị giải mã, tần suất (kể cả giả mạo `X-Forwarded-For`), CORS, **không ghi gì ra đĩa**, không log IP, khởi động thất bại khi cấu hình CORS sai.

## Xử lý sự cố
| Hiện tượng | Cách xử lý |
|---|---|
| Trang báo *offline* dù đã mở | Mở `http://127.0.0.1:8140/api/health` trên laptop; phải có `"ready":true`. Nếu không, xem cửa sổ PowerShell thu nhỏ của dịch vụ. |
| `open_demo.ps1` báo cổng 8140 đang dùng | Chạy `close_demo.ps1` rồi mở lại. |
| Bật Funnel thất bại | `tailscale status`; kiểm tra Funnel còn được bật cho máy này; thử `-FunnelPort 10000`. Cổng 8443 và 8444 bị script từ chối. |
| Giám khảo gặp lỗi "Too many photos" | Đang bị giới hạn tần suất (5 ảnh/phút/IP); chờ vài chục giây. |
| Trình duyệt báo lỗi CORS | `-Origin` phải đúng từng ký tự địa chỉ trang web (có `https://`, không có `/` ở cuối). |
