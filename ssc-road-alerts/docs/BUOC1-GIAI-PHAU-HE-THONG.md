# Bước 1 — Giải phẫu hệ thống backend `ssc-road-alerts`

*Báo cáo nghiên cứu trước khi di dời model YOLO26s-seg vào hệ thống. Viết ngày 2026-09-20, dựa trên đọc toàn bộ mã nguồn (~5.000 dòng), tài liệu, firmware, dữ liệu thật và trạng thái máy đang chạy.*

---

## 0. Tóm tắt 1 phút

Hệ thống là một **bệnh viện dành cho những con đường**. Mỗi camera ESP32 ngoài đường là một *y tá đi tuần*, cứ 60 giây chụp một tấm "phim X-quang" (ảnh JPEG) của miệng cống rồi gửi về bệnh viện qua mạng 4G. Bệnh viện (backend Node.js) có *quầy tiếp tân* kiểm tra giấy tờ, *kho hồ sơ* lưu phim và bệnh án, một *phòng bác sĩ chẩn đoán hình ảnh* (AI worker) để đọc phim, và một *hội đồng đánh giá* để chốt "con đường này nguy hiểm mức nào". *Giám đốc* (WebUI React) cứ 30 giây lại hỏi hội đồng một lần và vẽ kết quả lên bản đồ.

**Trạng thái thực tế lúc này (đã kiểm tra trên máy):**

| Hạng mục | Tình trạng |
|---|---|
| Backend Node | **Đang chạy** — PID 33628, nghe `127.0.0.1:8000` (HTTP) và `127.0.0.1:8443` (HTTPS tự ký) |
| Tailscale Funnel | **Đang bật** — `https://laptop-p8gad5f2.tailc4a76e.ts.net:8443` → chuyển tiếp vào 8443 local. Trùng khớp với HOST/PORT gắn cứng trong firmware ESP32 |
| Camera thật | `cam0001` (ESP32-CAM AI-Thinker + modem A7670C, SIM 4G, APN `m-wap`) đã gửi được ảnh về nhiều lần, lần cuối 2026-09-19 08:17 UTC |
| Hàng đợi AI | **14 observation đang `pending`** trên 2 camera, **chưa từng có AI nào xử lý** — phòng bác sĩ hiện đang trống |
| Ảnh thật | 640×480 px, JPEG quality 12, chỉ ~11–17 KB/ảnh (một vài ảnh test từ laptop là 960×660, 264 KB) |
| Model AI | Chưa có. `ai-worker.js` tồn tại nhưng yêu cầu một adapter chưa được viết |

Phần model của chúng ta sẽ đóng vai **bác sĩ chẩn đoán hình ảnh** — khu vực duy nhất còn trống trong toàn bộ dây chuyền.

---

## 1. Ẩn dụ xuyên suốt: bệnh viện cho những con đường

Để dễ hình dung, toàn bộ báo cáo dùng một ẩn dụ duy nhất:

| Trong ẩn dụ | Trong hệ thống thật | File |
|---|---|---|
| Y tá đi tuần, chụp X-quang | ESP32-CAM + modem A7670C | `firmware/esp32_a7670c_tailscale_capture/*.ino, protocol.h` |
| Xe cứu thương chạy trên đường cao tốc riêng | Mạng 4G → Tailscale Funnel → cổng 8443 | `server/index.js`, `tailscale funnel` |
| Bảo vệ + quầy tiếp tân | Routing, kiểm tra API key, giới hạn kích thước | `server/app.js`, `input.js`, `errors.js` |
| Văn phòng nghiệp vụ (làm đúng quy trình) | Tạo/cập nhật bệnh án theo quy tắc | `server/service.js` |
| Kho hồ sơ có 1 nhân viên duy nhất | Đọc/ghi 2 file JSON + thư mục ảnh | `server/store.js`, `validation.js`, `data/` |
| Phòng bác sĩ chẩn đoán hình ảnh (**đang trống**) | AI worker + model | `server/ai-worker.js` + adapter (chưa có) |
| Hội đồng đánh giá | Gộp chẩn đoán của nhiều camera thành mức nguy hiểm của tuyến | `server/aggregation.js`, `config.js` |
| Bàn thời tiết | Hỏi Open-Meteo dự báo mưa 12 giờ | `server/weather.js` |
| Phòng giám đốc (màn hình lớn) | WebUI React + bản đồ Leaflet | `src/` |

---

## 2. Bản đồ các khu vực

```
 NGOÀI ĐƯỜNG                    INTERNET                         MÁY LAPTOP CỦA BẠN
┌──────────────┐   4G/TLS   ┌──────────────┐   TLS tự ký   ┌──────────────────────────────────────────┐
│ ESP32-CAM    │──────────▶ │ Tailscale    │─────────────▶ │  :8443 (HTTPS)  ┐                        │
│ + A7670C     │  POST JPEG │ Funnel       │  localhost    │  :8000 (HTTP)   ┴─▶ [3] Tiếp tân app.js  │
│ (y tá)       │            │ (cao tốc)    │               │                        │                 │
└──────────────┘            └──────────────┘               │                        ▼                 │
                                                           │              [4] Nghiệp vụ service.js    │
                                                           │                        │                 │
                                                           │                        ▼                 │
                                                           │  [5] Kho hồ sơ store.js ──▶ data/        │
                                                           │        cameras.json  road-alerts.json    │
                                                           │        images/<uuid>.jpg                 │
                                                           │           ▲                    │         │
                                                           │  poll 3s  │ GET jobs           │ đọc     │
                                                           │  POST kq  │                    ▼         │
                                                           │  [6] Bác sĩ AI ai-worker.js   [7] Hội   │
                                                           │      + model (TRỐNG)          đồng      │
                                                           │                               aggregation│
                                                           │  [8] Bàn thời tiết ◀── Open-Meteo        │
                                                           └──────────────────────┬───────────────────┘
                                                                                  │ GET /api/cameras
                                                                                  │ GET /api/road-alerts
                                                                                  │ (poll 30 s, qua Vite proxy)
                                                                          ┌───────▼────────┐
                                                                          │ [9] WebUI React│
                                                                          │  :5173         │
                                                                          └────────────────┘
```

Lưu ý quan trọng về "hai cửa vào": cổng **8000** là cửa chính cho frontend và AI worker (chạy cùng máy); cổng **8443** là cửa phụ mở riêng cho modem GSM (chấp nhận TLS 1.0, cipher cũ, `SECLEVEL=0`) — cả hai cửa dẫn vào **cùng một quầy tiếp tân** (`server.listeners("request")[0]` được tái sử dụng cho HTTPS server).

---

## 3. Từng khu vực: chức năng, logic cụ thể, cách hoạt động

### 3.1 Khu vực [1] — Y tá đi tuần: ESP32-CAM + A7670C

**Chức năng:** chụp ảnh miệng cống định kỳ, gắn nhãn thời gian chính xác và mã định danh không trùng, gửi về bệnh viện, tự thử lại khi thất bại.

**Logic cụ thể (đọc từ firmware):**

1. **Khởi động modem** (`initModem`): bắt tay AT, kiểm tra SIM READY, đăng ký mạng (`+CEREG` = 1 hoặc 5), mở kết nối IP (`NETOPEN`), **đồng bộ giờ qua NTP bằng chính modem** (`AT+CNTP` với `time.cloudflare.com` rồi `pool.ntp.org`), cài chứng chỉ gốc Let's Encrypt vào modem (`AT+CCERTDOWN`), cấu hình TLS với `authmode=1` (xác thực thật, không bỏ qua).
2. **Chụp ảnh** (`captureImage`): đồng bộ giờ lại → bỏ 2 frame đầu để cảm biến ổn định → đọc giờ modem `AT+CCLK?` → chuyển thành ISO 8601 có múi giờ (`clockToISO`, chú ý múi giờ modem tính theo đơn vị 15 phút) → **tăng bộ đếm lưu trong NVS trước khi chụp** để không bao giờ tái dùng số thứ tự sau khi reset → tạo `observation_id` dạng `cam0001-<MAC hex 12 ký tự>-<số thứ tự>-<chữ số của thời gian>` → chụp VGA 640×480 JPEG quality 12 → kiểm tra byte đầu `FF D8` và byte cuối `FF D9`.
3. **Gửi** (`uploadPending`): mở TLS tới `laptop-p8gad5f2.tailc4a76e.ts.net:8443` → tự tay ghép HTTP request thô (`makeHeaders`) với các header: `Content-Type: image/jpeg`, `X-API-Key`, `X-Observation-Id`, `X-Captured-At`, `Content-Length` → đẩy từng khối 1024 byte qua `AT+CCHSEND` → đọc phản hồi qua `AT+CCHRECV` → tách mã HTTP status.
4. **Xử lý kết quả:**
   - `200`/`202` → xóa ảnh khỏi RAM, chờ 60 giây chụp tiếp.
   - `408/425/429/5xx` hoặc mất kết nối → **giữ nguyên ảnh + ID + thời gian**, thử lại sau 5 s → 10 s → 20 s → tối đa 60 s (backoff mũ). Đây là điểm mấu chốt để idempotency ở backend có tác dụng.
   - `400/401/403/404/409/413/415` → **dừng hẳn** (`failStop`), vì đây là lỗi cấu hình con người phải sửa. Không bao giờ tự sinh ID mới cho cùng một tấm ảnh.

**Ẩn dụ:** y tá không tự ý "sáng tác" thời gian chụp (không có RTC, không có WiFi — thời gian lấy từ mạng di động), luôn đeo thẻ tên duy nhất trên mỗi tấm phim, và nếu xe cứu thương hỏng thì đứng chờ chứ không vứt phim.

**Điểm cần nhớ cho AI:** `camera_id` = `cam0001` gắn cứng trong đường dẫn POST. `DEVICE_API_KEY` trong firmware = `"123"`. Ảnh 640×480 chất lượng thấp là "chuẩn đầu vào thật" mà model phải đối mặt.

### 3.2 Khu vực [2] — Đường cao tốc: Tailscale Funnel + hai lớp TLS

**Chức năng:** cho phép thiết bị trên mạng 4G công cộng chạm được vào laptop ở nhà mà không cần mở port router.

**Logic cụ thể:**

- Lệnh đã chạy trên laptop: `tailscale funnel --bg --https=8443 https+insecure://localhost:8443`. Tailscale cấp một tên miền công cộng `*.ts.net` với **chứng chỉ Let's Encrypt thật**.
- **Lớp TLS 1 (modem ↔ Tailscale):** modem xác thực chứng chỉ Let's Encrypt bằng root CA đã nạp. Đây là lớp bảo mật thật.
- **Lớp TLS 2 (Tailscale ↔ backend local 8443):** backend dùng chứng chỉ tự ký `CN=ssc-road-alerts` (hạn 2036). Chữ `+insecure` nghĩa là Tailscale **không kiểm tra** chứng chỉ này. Chấp nhận được vì chỉ chạy trong nội bộ máy.
- Vì sao cần cổng 8443 HTTPS riêng thay vì cho Funnel trỏ thẳng HTTP 8000? Comment trong `index.js` nói rõ: để có thể **tự quản lý TLS với cipher/phiên bản cũ** khi cần thiết bị cắm trực tiếp qua `ngrok tcp`. Hiện tại với Funnel, lớp này gần như dư — nhưng vẫn hoạt động.

**Ẩn dụ:** Tailscale là đường cao tốc riêng có trạm thu phí kiểm soát danh tính; đoạn cuối từ trạm vào cổng bệnh viện là đường nội bộ không cần kiểm tra lại.

### 3.3 Khu vực [3] — Bảo vệ + Tiếp tân: `app.js`, `input.js`, `errors.js`

**Chức năng:** nhận mọi HTTP request, quyết định ai được vào cửa nào, kiểm tra sơ bộ giấy tờ, rồi chuyển cho văn phòng nghiệp vụ. **Không chứa logic nghiệp vụ.**

**Logic cụ thể:**

- **Ba loại thẻ ra vào** (`authorize(req, role)`): `admin` (ADMIN_API_KEY), `device` (DEVICE_API_KEY), `ai` (AI_API_KEY). Nếu không đặt DEVICE/AI key thì hai vai này dùng chung ADMIN key. So sánh key bằng `timingSafeEqual` (chống đoán key theo thời gian). **Nếu không đặt key nào cả**, chỉ cho phép request từ loopback (`127.0.0.1`) *và* header `Host` phải là `localhost/127.0.0.1`.
  - Suy luận: vì `cam0001` gửi qua Funnel với `Host: laptop-p8gad5f2.tailc4a76e.ts.net` mà vẫn được nhận, backend hiện gần như chắc chắn **đang chạy với `DEVICE_API_KEY=123`**. Cần xác nhận ở Bước 3 (và cần biết `AI_API_KEY` để worker của ta gọi được).
- **Giới hạn cơ thể request:** ảnh ≤ 5 MiB, JSON ≤ 64 KiB (`body()` đếm từng chunk, quá là cắt 413 ngay giữa chừng). JSON bắt buộc `Content-Type: application/json` (415 nếu sai).
- **Kiểm tra JPEG nông:** chỉ nhìn 2 byte đầu `FF D8` và 2 byte cuối `FF D9`. Tài liệu ghi rõ: *"không thay thế bộ giải mã ảnh thật; model phải xử lý ảnh hỏng"* → model của ta phải chịu được ảnh JPEG cụt/hỏng.
- **Bảng routing** (thứ tự quan trọng, khớp cái nào trước dùng cái đó):

| Method | Đường dẫn | Vai | Việc |
|---|---|---|---|
| GET | `/api/health`, `/api/policy` | public | Sức khỏe, ngưỡng |
| GET | `/api/weather/cameras` | public | Dự báo mưa theo camera |
| POST | `/api/ai/reports` | ai | Báo cáo AI trực tiếp (không qua job) |
| GET | `/api/images/<uuid>.jpg` | public | Trả file JPEG từ `data/images/` — **regex bắt buộc tên đúng dạng UUID 36 ký tự** |
| GET/POST/PATCH/DELETE | `/api/cameras[/:id]`, `/api/road-alerts[/:id]` | public đọc / admin ghi | CRUD |
| POST | `/api/esp32/observations` | device | Tạo job bằng `image_url` có sẵn |
| POST | `/api/esp32/cameras/:id/capture` | device | **Upload JPEG nhị phân + tạo job** (đường ESP32 đang dùng) |
| GET | `/api/ai/jobs?status=&camera_id=&limit=` | ai | Lấy danh sách job |
| POST | `/api/ai/results` | ai | **Trả kết quả cho 1 job** (đường worker của ta sẽ dùng) |
| POST | `/api/ai/jobs/fail`, `/api/ai/jobs/retry` | ai | Đánh dấu lỗi / đưa về pending |
| POST/DELETE | `/api/road-alerts/:id/alert` | admin | Cảnh báo thủ công có hạn |
| PUT | `/api/road-alerts/:id/weather` | admin | Nhập tín hiệu mưa thủ công |
| POST | `/api/test/simulate` | admin | Tạo job + kết quả giả trong 1 lần (tắt được bằng `ENABLE_TEST_API=false`) |

- **Xử lý lỗi thống nhất:** mọi lỗi nghiệp vụ là `ApiError(status, message)`; lỗi không lường trước → 500 kèm câu *"dữ liệu cũ được giữ khi ghi thất bại"*. Response luôn `Cache-Control: no-store`.
- **Timeout:** request 30 s, header 15 s.

**Ẩn dụ:** bảo vệ chỉ hỏi "anh có thẻ gì, đi cửa nào, túi có quá to không" — không bao giờ mở hồ sơ ra đọc.

### 3.4 Khu vực [4] — Văn phòng nghiệp vụ: `service.js`

**Chức năng:** nơi duy nhất biết *quy trình* — một tấm phim từ lúc nhận đến lúc thành chẩn đoán đi qua những trạng thái nào, điều kiện gì mới được "áp vào hiện trạng".

**Vòng đời của một observation (máy trạng thái):**

```
                 ┌──────────── POST /api/ai/jobs/retry ────────────┐
                 ▼                                                 │
 [ESP32 upload] ──▶ pending ──┬── confidence ≥ 0.5 ──▶ processed ──┤ (applied: true | false)
                              ├── confidence < 0.5 ──▶ needs_review┤
                              └── worker báo lỗi ────▶ failed ─────┘
```

**Logic cụ thể của từng hàm quan trọng:**

**`enqueue()` — nhận phim, lập bệnh án (ESP32 gọi):**
1. Chỉ cho phép đúng 4 trường: `camera_id, observation_id, captured_at, image_url`. ID phải khớp `^[A-Za-z0-9_-]{1,80}$`. `captured_at` phải ISO 8601 **có múi giờ** và không được ở tương lai quá 5 phút.
2. Camera phải tồn tại và **phải đã gắn `road_id`** tới một tuyến tồn tại (409 nếu chưa). Không có tuyến thì không nhận phim.
3. Tính **vân tay** `fingerprint = [captured_at, sha256(bytes ảnh)]`. Nếu `observation_id` đã có trong lịch sử camera:
   - vân tay giống → trả `duplicate: true`, HTTP 200, **không tạo gì thêm** (đây là nhờ firmware giữ nguyên ảnh khi retry).
   - vân tay khác → 409 "observation_id đã dùng với nội dung khác".
4. Hàng đợi mỗi camera tối đa **100 observation**. Đầy thì xóa metadata của observation **không-pending** cũ nhất; nếu tất cả 100 đều pending → 429 (báo ESP32 thử lại sau). Ảnh file không bị xóa theo.
5. Lưu ảnh: `data/images/<randomUUID>.jpg` với cờ `wx` (chỉ tạo mới, không ghi đè). Ghi observation `status: pending`, `received_at = bây giờ`, cập nhật `camera.last_seen_at`.
6. Trả 202 (mới) hoặc 200 (trùng).

**`applyResult()` — bác sĩ trả chẩn đoán (worker AI gọi):**
1. Chỉ cho phép: `camera_id, observation_id, waste_coverage_pct, drain_blockage_pct, confidence, analyzed_url`. Hai phần trăm là số 0–100; `confidence` số 0–1; `analyzed_url` phải là `http(s)://...` hoặc đường dẫn bắt đầu bằng `/`.
2. Nếu observation **đã có result**: kết quả gửi lại phải **giống hệt** (so sánh JSON) → `duplicate: true`; khác → 409. Nếu không phải `pending` → 409 "dùng API retry".
3. Ghi `result`, `processed_at`, `applied = false`.
4. `confidence < 0.5` → `status = needs_review`, **không** đụng vào `latest_analysis` (chẩn đoán cũ đáng tin hơn vẫn giữ nguyên).
5. Ngược lại `status = processed` và kết quả **chỉ được áp vào hiện trạng** (`applied = true`) khi thỏa **cả ba**:
   - **mới hơn** chẩn đoán đang dùng (`captured_at` > `latest_analysis.captured_at`), và
   - **còn tươi**: `now − captured_at ≤ 15 phút`, và
   - camera **chưa bị đổi tuyến** kể từ lúc chụp (`observation.road_id === camera.road_id`).
6. Khi áp: tính `severity = evaluateSeverity(waste, blockage)`; quyết định **mã đợt sự cố** `incident_id`: nếu chẩn đoán trước cũng bất thường và còn trong 15 phút → giữ mã cũ (cùng một đợt), nếu không → cấp UUID mới; `severity = normal` → không có mã. Ghi `camera.latest_analysis = {monitoring, images{original_url, analyzed_url, captured_at}, severity, incident_id, simulated}`.

**Hệ quả thực tế ngay lập tức:** 14 job đang chờ đều đã chụp từ ngày 16–19/09 → khi worker của ta xử lý, chúng sẽ thành `processed` nhưng **`applied: false`** (quá 15 phút) → **không hiện lên bản đồ**. Muốn thấy kết quả trên WebUI phải dùng ảnh mới chụp trong vòng 15 phút, hoặc worker phải chạy gần như real-time.

**`aiReport()` — đường tắt không qua hàng đợi:** nhận `waste_level` (chữ) + `flood_percentage` + `image_url`, tự tạo observation `processed` ngay. Không có `confidence`. Đây là đường cho nguồn AI đã tin cậy sẵn; **không phù hợp** cho luồng ESP32 của ta vì bỏ qua ảnh đã upload.

**`save()/remove()` — quản trị camera/tuyến:** không được đổi ID; xóa tuyến còn camera → 409; đổi `road_id` của camera đang có job pending → 409; đổi tuyến thành công thì **xóa `latest_analysis`** (tránh áp chỉ số của tuyến cũ sang tuyến mới).

**Ẩn dụ:** văn phòng nghiệp vụ không tin bất kỳ ai nói "tình trạng đường này là *nguy hiểm*" — họ chỉ nhận số liệu đo (phần trăm) rồi **tự tính** mức độ theo bảng quy định. Chẩn đoán muộn (quá 15 phút) vẫn được lưu vào bệnh án để tham khảo, nhưng không được treo lên bảng hiện trạng.

### 3.5 Khu vực [5] — Kho hồ sơ: `store.js`, `validation.js`, `data/`

**Chức năng:** lưu trữ bền vững toàn bộ trạng thái mà không cần database.

**Ba "ngăn tủ":**

| Ngăn | Nội dung | Ai ghi |
|---|---|---|
| `data/cameras.json` | Camera, **toàn bộ hàng đợi `observations`** (tối đa 100/camera), `latest_analysis`, `last_seen_at` | service.js qua store |
| `data/road-alerts.json` | Tuyến (LineString), cảnh báo thủ công `manual_alert`, mưa thủ công `weather` | service.js qua store |
| `data/images/<uuid>.jpg` | File JPEG gốc | app.js (endpoint capture) |

**Logic chống hỏng dữ liệu (`store.js`, chỉ 39 dòng nhưng là xương sống):**

1. **Một hàng chờ ghi duy nhất trong tiến trình** (`tail` promise chain): mọi `transaction(fn)` xếp hàng nối đuôi nhau, cái sau chỉ chạy khi cái trước xong (kể cả lỗi). Hai request đến cùng lúc **không bao giờ** đọc–sửa–ghi chồng lên nhau.
2. **Ghi nguyên tử:** ghi vào file tạm `.<uuid>.tmp` (cờ `wx`) → `fsync` → `rename` đè lên file đích. Mất điện giữa chừng thì file cũ vẫn nguyên vẹn.
3. **Validate hai chiều:** mỗi lần *đọc* và mỗi lần *ghi* đều chạy `validateDataset` (kiểm tra ID không trùng, tọa độ hợp lệ, trạng thái observation hợp lệ, `latest_analysis` đúng dạng...). File JSON hỏng → trả 500 và **từ chối ghi đè** ("sửa dữ liệu lỗi; server không ghi đè file này").
4. File chưa tồn tại → coi như mảng rỗng.

**Giới hạn thiết kế (tài liệu tự khai):** chỉ được chạy **một tiến trình backend** ghi trên cùng thư mục. Không có transaction giữa 2 file: ví dụ lưu JPEG thành công nhưng ghi JSON thất bại → ảnh mồ côi (không tạo job giả).

**Ẩn dụ:** kho hồ sơ chỉ có **một nhân viên**, ai đến cũng phải xếp hàng; nhân viên viết bản nháp ra giấy riêng, kiểm tra kỹ rồi mới thay vào tủ — không bao giờ tẩy xóa trực tiếp trên bản gốc.

**Điểm cần nhớ cho AI:** worker của ta **tuyệt đối không được sửa trực tiếp `cameras.json`** — phải đi qua API. Riêng thư mục `images/` thì backend chỉ ghi file mới bằng tên UUID ngẫu nhiên với cờ `wx`, nên một tiến trình khác ghi thêm file UUID vào đó **không xung đột** (điểm này quan trọng cho việc lưu ảnh kết quả AI — xem mục 6).

### 3.6 Khu vực [6] — Phòng bác sĩ chẩn đoán hình ảnh: `ai-worker.js` (ĐANG TRỐNG)

**Chức năng:** định kỳ lấy phim chưa đọc, chạy model, trả kết quả.

**Logic cụ thể của runner có sẵn (42 dòng):**

1. Bắt buộc biến môi trường `AI_ADAPTER_MODULE` trỏ tới một **module Node ESM** export `async function analyze(jpegBuffer, job)`. Không có → dừng ngay với thông báo "Dùng /api/test/simulate nếu chưa có model".
2. Vòng lặp mỗi **3 giây** (hoặc một lượt với `--once`): `GET /api/ai/jobs?status=pending&limit=20` (sắp theo `received_at` tăng dần — cũ trước).
3. Với mỗi job:
   - `image_url` phải cùng origin với server **và** khớp `^/api/images/[a-f0-9-]{36}\.jpg$` (allowlist — không bao giờ fetch URL lạ do thiết bị gửi).
   - Tải ảnh qua HTTP (timeout 15 s), gọi `analyze()`.
   - Lỗi bất kỳ → `POST /api/ai/jobs/fail` với thông báo lỗi.
   - Thành công → `POST /api/ai/results` với `{...result, camera_id, observation_id}`. In ra `status` và `applied`.
4. Không có cơ chế **claim/lease**: nếu chạy 2 worker, cả hai có thể đọc cùng một job. An toàn vì callback trùng là idempotent, nhưng tốn công gấp đôi → **chỉ chạy một worker**.

**Hợp đồng đầu ra mà model phải đáp ứng:**

```json
{ "waste_coverage_pct": 0..100, "drain_blockage_pct": 0..100, "confidence": 0..1, "analyzed_url": "/api/images/<uuid>.jpg (tùy chọn)" }
```

**Ẩn dụ:** phòng đã có bàn, có quy trình lấy phim–trả kết quả in sẵn trên tường, chỉ thiếu bác sĩ. Bác sĩ có thể là người Node (adapter) hoặc người Python tự đi lấy phim (gọi thẳng API) — tài liệu cho phép cả hai.

**Phát hiện đáng chú ý:** observation `LIGHTTEST-11931` của `cam0001` có `image_url = /api/images/light-test.jpg` (không phải UUID) → worker sẽ **luôn đánh `failed`** cho job này (không khớp allowlist), và endpoint ảnh cũng không phục vụ được. Vô hại nhưng gây nhiễu log.

### 3.7 Khu vực [7] — Hội đồng đánh giá: `aggregation.js`, `config.js`

**Chức năng:** biến chẩn đoán từng camera thành *một mức ưu tiên cho cả tuyến đường*, và quyết định camera nào đang "online".

**Ngưỡng (`config.js`, tự nhận là heuristic demo):**

| Điểm = max(rác %, che cống %) | Mức |
|---|---|
| < 20 | normal |
| 20–49 | low |
| 50–69 | medium |
| 70–89 | high |
| ≥ 90 | critical |

Các hằng khác: `minConfidence 0.5`, `readingMaxAge 15 phút`, `maxFutureSkew 5 phút`, `max 100 observation/camera`, ảnh ≤ 5 MiB, JSON ≤ 64 KiB.

**Logic `aggregateRoad()` — tính ngay tại thời điểm GET, không lưu lại:**

1. Lấy các camera có `road_id` trùng tuyến. Chỉ giữ `latest_analysis` **còn tươi** (≤ 15 phút, không ở tương lai > 5 phút) làm "readings".
2. **Lấy MAX chứ không lấy trung bình** cho từng chỉ số (rác, che cống, ngập) — để một miệng cống nguy hiểm không bị "pha loãng" bởi các camera khác đang sạch.
3. `severity = max( evaluateSeverity(max(rác, ngập), che cống), waste_level nếu có )`.
4. Có tín hiệu **mưa thủ công còn tươi** → mức từ medium trở lên **tăng một bậc** (tối đa critical); mưa mà chưa có gì → ít nhất medium.
5. **Cảnh báo thủ công** (còn hạn TTL) chỉ được **nâng** mức, không hạ.
6. `alert_id` của tuyến = ghép tất cả `incident_id` camera + `alert_id` thủ công + `event_id` mưa (đã sắp xếp) → ổn định khi polling, đổi khi có đợt mới. `normal` → không có `alert_id`.
7. `data_quality`: `fresh` (mọi camera có reading tươi) / `partial` / `unknown` (không camera nào tươi) / `unconfigured` (tuyến không có camera). **`normal + unknown` nghĩa là "chưa biết", không phải "an toàn".**
8. Nếu có reading mô phỏng → tự chèn tiền tố mô tả "[Dữ liệu mô phỏng qua API test]".

**Logic `publicCamera()` — bộ mặt camera cho frontend:** giấu `observations` và `latest_analysis` thô; `status = online` nếu `last_seen_at` trong 15 phút, `offline` nếu quá, `unknown` nếu chưa từng gửi; phơi ra `monitoring`, `images`, `analysis_source` (`ai`|`simulation`), `analysis_status` (`fresh`|`stale`), `pending_count`.

**Ẩn dụ:** hội đồng không đọc lại từng tấm phim; họ chỉ nhìn chẩn đoán **mới nhất còn hiệu lực** của từng y tá, lấy ca **nặng nhất** làm mức của cả con đường, rồi cộng thêm "trời sắp mưa" và "sếp bảo ưu tiên" nếu có.

### 3.8 Khu vực [8] — Bàn thời tiết: `weather.js`

**Chức năng:** hỏi Open-Meteo dự báo 12 giờ tới cho từng vị trí camera, cache trong RAM.

**Logic:** gom camera theo tọa độ trùng nhau (tối đa 100 vị trí, 4 request song song, timeout 8 s); cache 15 phút; lỗi thì giữ cache cũ gắn nhãn `stale` và chờ 1 phút mới thử lại; "có mưa" = xác suất ≥ 50 % **hoặc** rain+showers ≥ 0.2 mm/giờ. **Không ghi vào file JSON**; frontend tự ghép (`mergeWeather`) vào tín hiệu mưa hiển thị. Không liên quan trực tiếp tới model AI.

### 3.9 Khu vực [9] — Phòng giám đốc: WebUI React (`src/`)

**Chức năng:** hiển thị bản đồ, danh sách tuyến, chi tiết camera (kèm **ảnh gốc** và **ảnh kết quả AI**), hàng đợi cảnh báo, xuất phiếu thu gom.

**Logic cụ thể:**

- `useMapData`: khi ở nguồn "Máy chủ", gọi song song `GET /api/cameras` và `GET /api/road-alerts` mỗi **30 giây** khi tab đang mở (timeout 10 s, hủy request cũ khi có request mới, giữ dữ liệu cũ khi lỗi). Vite dev server proxy `/api` → `127.0.0.1:8000`.
- `mapService.normalizeCameras` / `normalizeMonitoring`: **validate lại lần nữa** ở phía client (ID, tọa độ, phần trăm 0–100, URL ảnh phải `http(s)://` hoặc `/...`). Dữ liệu sai → ném lỗi, **không** âm thầm hiển thị.
- `buildMonitoringAlerts`: tuyến vào hàng đợi cảnh báo khi: `severity ≠ normal`, hoặc rác ≥ 70 %, hoặc che cống ≥ 70 %, hoặc có mưa, hoặc `flood_risk ≥ high`. Mức hiển thị = max(severity tuyến, flood_risk, `medium` nếu có điều kiện phụ). Khóa chống lặp thông báo = `[road_id, alert_id, severity, mức hiển thị, các trigger]` — polling đổi timestamp không tạo thông báo mới.
- `ObservationDetail`: khi chọn camera, render hai thẻ `<img>`: `images.original_url` ("Ảnh chụp gốc") và `images.analyzed_url` ("Ảnh kết quả phân tích AI"). Ảnh lỗi tải → hiện "Không tải được ảnh"; chưa có → "Chưa có ảnh". Có nhãn "Chỉ số từ API mô phỏng" nếu `analysis_source = simulation`, và "Phân tích đã quá thời hạn" nếu `stale`.
- Trạng thái "đã xem / lập phiếu" lưu **localStorage** trình duyệt, không đồng bộ về backend.

**Ẩn dụ:** giám đốc không bao giờ tự đọc phim hay tự tính toán; chỉ nhận báo cáo tổng hợp, và cũng không tin mù quáng — kiểm tra lại định dạng trước khi treo lên tường.

---

## 4. Cách các khu vực liên kết mà không giẫm chân nhau

Đây là phần "keo dán" — bảy cơ chế giúp cả dây chuyền chạy song song mà không xung đột:

| # | Cơ chế | Ở đâu | Chống lại tình huống nào |
|---|---|---|---|
| 1 | **Một nhân viên kho duy nhất** (promise chain `tail`) + ghi file nguyên tử (tmp → fsync → rename) | `store.js` | ESP32 upload đúng lúc worker trả kết quả và frontend đang GET — ba việc được xếp hàng, không bao giờ ghi đè nhau |
| 2 | **Idempotency theo `observation_id` + vân tay** | `enqueue`, `applyResult` | ESP32 retry gửi lại cùng ảnh (mạng 4G chập chờn); worker gửi lại cùng kết quả (mất kết nối sau khi server đã lưu) → cả hai đều nhận "duplicate: true", không tạo bản ghi đôi |
| 3 | **Máy trạng thái chặt** (`pending → processed / needs_review / failed → retry`) | `applyResult`, `jobAction` | Kết quả đến cho job không còn pending → 409, không có "kết quả ma" |
| 4 | **Cửa sổ tươi 15 phút + cờ `applied`** | `applyResult`, `aggregateRoad`, `publicCamera` | Worker chậm, kết quả về sai thứ tự, ảnh cũ → vẫn lưu để đối chiếu nhưng **không** làm sai hiện trạng; tuyến tự "nhạt" về `unknown` khi không còn dữ liệu mới |
| 5 | **Tổng hợp tuyến tính lúc đọc, không lưu** | `aggregateRoad` | Chỉ có **một** nguồn sự thật (camera); không có bản sao chỉ số tuyến bị lệch |
| 6 | **Thẻ theo vai (admin/device/ai) + allowlist URL ảnh ở worker** | `authorize`, `ai-worker` | Thiết bị không sửa được cấu hình; worker không bị dụ fetch URL nội bộ lạ |
| 7 | **Mã đợt sự cố `incident_id` ổn định + khóa chống lặp ở frontend** | `applyResult`, `aggregateRoad`, `buildMonitoringAlerts` | Poll 30 s không làm "ting ting" thông báo lại cùng một sự cố |

Điểm mấu chốt: **mọi khu vực chỉ nói chuyện với nhau qua HTTP API và qua đúng một cửa kho** — không ai đọc/ghi file của người khác. Đó là lý do model của ta cũng phải đi đúng cửa đó.

---

## 5. Hành trình của một tấm ảnh: từ miệng cống đến màn hình

Lấy một observation **có thật** trong `cameras.json` làm ví dụ: `cam0001-94c1d2842178-34-202609190817000000`.

| Thời điểm (UTC) | Khu vực | Việc xảy ra |
|---|---|---|
| 08:17:00 | [1] ESP32 | Đồng bộ giờ qua modem → tăng bộ đếm NVS lên 34 → tạo ID `cam0001-94c1d2842178-34-202609190817000000` → chụp VGA 640×480, ~11 KB |
| 08:17:00 → 08:17:17 | [2] Đường truyền | Mở TLS tới `laptop-p8gad5f2.tailc4a76e.ts.net:8443` (xác thực Let's Encrypt), đẩy header + JPEG từng khối 1 KB qua 4G. **Mất ~17 giây** (`received_at` − `captured_at`) |
| 08:17:17.579 | [3] Tiếp tân | Kiểm tra `X-API-Key`, `Content-Type: image/jpeg`, ≤ 5 MiB, byte đầu/cuối JPEG → tính sha256 → chuyển cho nghiệp vụ |
| 08:17:17.58 | [4]+[5] Nghiệp vụ + Kho | Camera `cam0001` tồn tại, đã gắn `ROAD-CAM0001`, tuyến tồn tại → ID chưa dùng → hàng đợi chưa đầy → lưu `data/images/bd439a5f-2ddd-...jpg` (cờ `wx`) → thêm observation `pending` vào `cameras.json` → cập nhật `last_seen_at` → ghi nguyên tử → trả **202** |
| 08:17:18 | [1] ESP32 | Nhận 202 → in "[OK] Anh da vao hang doi AI." → giải phóng RAM → hẹn 60 s sau chụp tiếp |
| *(chưa xảy ra)* | [6] Bác sĩ AI | Đáng lẽ trong vòng 3 giây worker đã `GET /api/ai/jobs?status=pending`, tải `/api/images/bd439a5f-...jpg`, chạy model, `POST /api/ai/results` với hai phần trăm + confidence + `analyzed_url`. **Hiện tại không có ai làm việc này** → job đứng ở `pending` từ 19/09 tới nay |
| *(nếu có AI, trong 15 phút)* | [4] Nghiệp vụ | `confidence ≥ 0.5`, mới hơn phân tích trước, còn tươi, đúng tuyến → `applied: true`, ghi `latest_analysis` với `severity` tính từ bảng ngưỡng và `incident_id` |
| Mỗi 30 s | [9] WebUI | `GET /api/cameras` → `publicCamera` cho `status: online` (last_seen trong 15 phút), `monitoring`, `images{original_url, analyzed_url}`; `GET /api/road-alerts` → `aggregateRoad` tính `severity` tuyến từ MAX các camera tươi |
| Ngay sau đó | [9] WebUI | Tuyến `ROAD-CAM0001` đổi màu theo `severity`; chọn camera → thấy ảnh gốc (từ `/api/images/bd43...jpg` qua proxy) và ảnh AI; nếu ≥ 70 % hoặc severity ≠ normal → vào hàng đợi cảnh báo, hiện thông báo một lần |
| Sau 15 phút không có ảnh mới | [7] Hội đồng | Reading hết tươi → camera `analysis_status: stale`, tuyến `data_quality: unknown`, `severity: normal` — nghĩa là "không biết", không phải "sạch" |

**Rút ra:** dây chuyền hiện đã chạy **đến hết bước lưu vào hàng đợi** và **từ bước tổng hợp trở đi** — chỉ thiếu đúng mắt xích ở giữa.

---

## 6. Những điều cần lưu ý trước khi di dời model (chuẩn bị cho Bước 2)

Đây là các phát hiện có ảnh hưởng trực tiếp đến thiết kế tích hợp, sắp theo mức quan trọng:

### 6.1 Phải quyết định: model Python nói chuyện với backend bằng cách nào

Runner có sẵn là Node và cần adapter Node. Ta có hai lựa chọn hợp lệ theo tài liệu:

- **(A) Worker Python độc lập**, tự gọi `GET /api/ai/jobs` → tải ảnh → chạy YOLO → `POST /api/ai/results` / `jobs/fail`. Bỏ qua `ai-worker.js`. Đơn giản nhất, không phải bắc cầu Node↔Python, tận dụng thẳng `.venv` đã có model.
- **(B) Giữ `ai-worker.js`**, viết adapter Node gọi sang một service Python (HTTP nội bộ hoặc child process). Thêm một tầng, thêm điểm hỏng.

Khuyến nghị sơ bộ: **(A)**, nhưng phải tái hiện đúng các hành vi của runner mẫu: allowlist URL ảnh, timeout, gọi `fail` khi lỗi, chỉ chạy một tiến trình, sắp job cũ trước.

### 6.2 Phải định nghĩa phép chuyển từ mask sang hai con số phần trăm

Backend chỉ hiểu `waste_coverage_pct` và `drain_blockage_pct` (0–100). Model của ta trả ra **mask từng vật thể** cho hai lớp Trash/Drain. Cần chốt công thức, ví dụ:

- `waste_coverage_pct` = tổng diện tích mask Trash / diện tích ảnh × 100.
- `drain_blockage_pct` = diện tích (Trash ∩ Drain) / diện tích Drain × 100; không phát hiện Drain → cần quy ước (0? hay bỏ trống?). Đây là quyết định nghiệp vụ, không phải kỹ thuật thuần.
- `confidence`: model cho confidence **từng vật thể**; backend cần **một** số cho cả ảnh và dùng ngưỡng 0.5 để đẩy sang `needs_review`. Cần quy ước (trung bình? min? hay 1.0 khi ảnh sạch không có vật thể?). Chọn sai → hoặc mọi thứ vào `needs_review`, hoặc không bao giờ.

### 6.3 Ảnh kết quả AI: backend không có chỗ để upload

`/api/ai/results` chỉ nhận **chuỗi URL** `analyzed_url`; không có endpoint nào nhận file ảnh phân tích. Endpoint `GET /api/images/<uuid>.jpg` chỉ phục vụ file trong `data/images/` có tên đúng dạng UUID. Hai cách:

- **(A) Ghi thẳng file** `server/data/images/<uuid4>.jpg` từ worker Python (cùng máy) rồi trả `analyzed_url = /api/images/<uuid4>.jpg`. Không xung đột với backend vì backend cũng chỉ tạo file UUID mới với cờ `wx`. Không đụng JSON. Nhanh, không sửa backend.
- **(B) Thêm endpoint upload ảnh phân tích** vào `app.js`. Sạch hơn về kiến trúc, nhưng phải sửa backend + test.

### 6.4 Khoảng cách giữa ảnh train và ảnh thật — rủi ro lớn nhất về chất lượng

Model học trên ảnh điện thoại 2.000–4.000 px, letterbox 1024. ESP32 gửi **640×480, JPEG quality 12, ~11 KB** (nhiễu khối rõ rệt). Kỳ vọng độ chính xác thật **thấp hơn đáng kể** so với mAP đã đo. Bước 3 phải thử trực tiếp trên chính 14 ảnh thật đang có trong `data/images/` trước khi kết luận gì.

### 6.5 Cửa sổ 15 phút quyết định "có thấy trên bản đồ hay không"

- Worker phải xử lý xong **trong vòng 15 phút kể từ `captured_at`** (không phải kể từ lúc nhận). Với inference ~30 ms/ảnh trên GPU và poll 3 s thì dư, **miễn là worker đang chạy**.
- 14 job cũ đang chờ sẽ được xử lý thành `processed` nhưng `applied: false` → dùng để **kiểm tra worker hoạt động**, không dùng để thấy kết quả trên UI. Muốn thấy UI đổi màu ở Bước 3 phải gửi ảnh mới (curl từ terminal) rồi để worker chạy ngay.

### 6.6 Khóa API — cần biết giá trị đang dùng

Firmware dùng `DEVICE_API_KEY = "123"`; backend gần như chắc chắn đang chạy với key này (nếu không, request qua Funnel đã bị 403 vì `Host` không phải localhost). Worker của ta cần `AI_API_KEY` (hoặc `ADMIN_API_KEY` nếu không đặt riêng). Phải xem tiến trình backend (PID 33628) được khởi động với biến môi trường nào, hoặc khởi động lại có kiểm soát ở Bước 3.

### 6.7 Các ràng buộc vận hành phải tôn trọng

- **Chỉ một tiến trình backend ghi** trên `server/data/`. Worker không sửa JSON; chỉ gọi API.
- **Chỉ một worker** (không có claim/lease).
- Model phải **chịu được ảnh hỏng** (backend chỉ kiểm tra 4 byte); ảnh lỗi → gọi `jobs/fail`, không được crash cả worker.
- Kết quả gửi lại khi retry phải **giống hệt** (cùng số, cùng URL) — vậy worker không nên tính lại với random seed khác; tốt nhất lưu kết quả cục bộ trước khi gửi.
- Job `LIGHTTEST-11931` có `image_url` không hợp lệ → sẽ `failed`; chấp nhận hoặc dọn bằng API.

### 6.8 Điểm phụ về bảo mật (ghi nhận, không cần sửa cho demo)

Cổng 8443 chấp nhận TLS 1.0 và `SECLEVEL=0` — cố ý cho modem cũ, chỉ dùng nội bộ sau Funnel. API GET (camera, tuyến, **ảnh**) hiện **public không cần key** — ai có link Funnel là xem được ảnh. Khóa thiết bị `"123"` là khóa chung, chưa định danh từng camera. Tài liệu đã tự nhận các điểm này.

---

## 6.9 Minh chứng sống: 1 tuyến có nhiều camera thực sự trả về gì (chưa kết luận, chỉ quan sát)

Mục 3.7 mô tả logic gộp nhiều camera trên 1 tuyến bằng lời. Để có bằng chứng cụ thể — không suy diễn — tôi viết `docs/demo-aggregation.mjs`: tự tạo 1 thư mục dữ liệu **tạm** (không đụng `server/data/` thật), dựng 1 tuyến + 3 camera, rồi lần lượt gọi API thật và in nguyên văn kết quả. Chạy bằng `node docs/demo-aggregation.mjs` từ thư mục `ssc-road-alerts`. Test chính thức `tests/backend.test.js` cũng có 1 ca tên **`'uses the worst fresh camera'`** xác nhận đây là hành vi **thiết kế có chủ đích**, không phải hiệu ứng phụ tình cờ.

**Kịch bản:** tuyến `DEMO-R1` có 3 camera — `SACH` (đầu tuyến), `BAN` (giữa tuyến, sẽ báo rác nặng), `XA` (cuối tuyến, không bao giờ gửi ảnh trong suốt kịch bản).

| Bước | Hành động | `severity` tuyến | `waste_coverage_pct` tuyến | `data_quality` | Quan sát |
|---|---|---|---|---|---|
| 0 | Vừa tạo xong, chưa camera nào có ảnh | `normal` | *(không có field)* | `unknown` | 3 camera link vào tuyến nhưng 0 camera có dữ liệu → "chưa biết", không phải "an toàn" |
| 1 | `SACH` báo 8% rác | `normal` | **8** | `partial` (1/3) | Tuyến phản ánh đúng camera duy nhất có dữ liệu |
| 2 | `BAN` báo 92% rác, 88% che cống | **`critical`** | **92** | `partial` (2/3) | **Tuyến nhảy thẳng lên `critical` — không phải trung bình (92+8)/2=50, mà lấy nguyên số của camera tệ nhất.** `SACH` vẫn 8% nhưng không còn xuất hiện ở đâu trong dữ liệu tuyến |
| 3 | (quan sát `XA`) | — | — | vẫn `partial` | `XA` chưa từng gửi ảnh **không** bị tính là "thiếu dữ liệu gây lỗi" — nó đơn giản không đóng góp gì, không kéo `data_quality` xuống thêm |
| 4 | +15 phút, không ai gửi thêm | `normal` | *(mất field)* | `unknown` | Toàn bộ dữ liệu vừa có (kể cả `BAN` đang critical) "bốc hơi" khỏi tuyến vì hết hạn tươi — tuyến trông y hệt bước 0 |
| 5 | `BAN` gửi lại (vẫn nặng), `SACH`/`XA` im lặng | **`critical`** trở lại | **95** | `partial` (1/3) | Chỉ 1/3 camera "sống" cũng đủ kéo cả tuyến lên `critical` ngay lập tức |
| 6 | `GET /api/cameras` sau bước 5 | — | — | — | `SACH: offline, 8%` · `BAN: online, 95%` · `XA: unknown, chưa có` — **dữ liệu riêng từng camera vẫn còn nguyên**, chỉ là *tầng tổng hợp tuyến* không dùng đến nó nữa |

**Ba điểm rút ra (dữ kiện, không phải đề xuất sửa):**

1. **Tuyến chỉ có 1 con số duy nhất đại diện cho N camera** — luôn là camera *tệ nhất còn tươi*, không phải trung bình, không phải theo vị trí. WebUI hiện tại (mục 3.9) tô màu bản đồ và badge tuyến bằng đúng con số này.
2. **Dữ liệu từng camera không mất** — vẫn đọc được qua `GET /api/cameras`. "Mất" chỉ xảy ra ở lớp tổng hợp `aggregateRoad()`, không phải ở lưu trữ.
3. **`severity: normal` xuất hiện trong 2 tình huống hoàn toàn khác nhau** — "camera vừa báo sạch thật" (bước 1) và "không ai báo gì cả" (bước 0, 4) — chỉ phân biệt được nếu nhìn thêm `data_quality`. Nếu WebUI/người vận hành chỉ nhìn màu severity mà bỏ qua `data_quality`, hai tình huống này trông giống hệt nhau.

Đây chính là ba chỗ nhiều khả năng liên quan đến điều bạn thấy "chưa đúng với suy nghĩ" — giữ lại làm tài liệu tham chiếu cho buổi bàn sau, chưa đề xuất hướng sửa nào ở đây.

## 7. Phụ lục

### 7.1 Lệnh vận hành

```powershell
# Trong C:\Users\ASUS\Desktop\SSC\ssc-road-alerts
npm run backend          # hoặc backend:watch — cổng 8000 (+8443 nếu có certs/)
npm run dev              # frontend Vite :5173, proxy /api -> :8000
npm run ai:worker        # runner Node, cần AI_ADAPTER_MODULE (chưa có)
npm run demo:seed        # tạo tuyến/camera/kết quả giả để thử UI
npm test                 # vitest, chạy server trên cổng tạm, không đụng data thật
node docs/demo-aggregation.mjs   # Mô phỏng 1 tuyến/3 camera (mục 6.9), thư mục tạm, không đụng data thật

# Biến môi trường backend đọc (không tự đọc .env):
#   PORT=8000  HOST=127.0.0.1  HTTPS_PORT=8443  FRONTEND_ORIGIN=http://localhost:5173
#   ADMIN_API_KEY  DEVICE_API_KEY  AI_API_KEY  ENABLE_TEST_API=true|false
```

### 7.2 Gửi ảnh thử từ terminal (dùng ở Bước 3)

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/esp32/cameras/cam0001/capture `
  -H "Content-Type: image/jpeg" `
  -H "X-API-Key: 123" `
  -H "X-Observation-Id: TEST-<mã duy nhất>" `
  -H "X-Captured-At: <ISO 8601 UTC hiện tại, vd 2026-09-20T03:00:00Z>" `
  --data-binary "@anh.jpg"
```

### 7.3 Trạng thái observation

| Trạng thái | Nghĩa | Ai đặt |
|---|---|---|
| `pending` | Đã có ảnh, chờ AI | enqueue |
| `processed` | AI đã trả, confidence ≥ 0.5; xem thêm `applied` | applyResult |
| `needs_review` | AI đã trả nhưng confidence < 0.5; không áp | applyResult |
| `failed` | Worker báo lỗi | jobs/fail |
| `applied: true/false` | Có/không được đưa vào `latest_analysis` (mới hơn + ≤ 15 phút + đúng tuyến) | applyResult |

### 7.4 Kích thước và giới hạn

| Hạng mục | Giá trị |
|---|---|
| Ảnh upload | ≤ 5 MiB, `image/jpeg`, có `FF D8 … FF D9` |
| JSON | ≤ 64 KiB |
| Observation / camera | ≤ 100 (xóa non-pending cũ nhất khi đầy; toàn pending → 429) |
| Tươi | 15 phút; tương lai ≤ 5 phút |
| Poll worker mẫu | 3 s, 20 job/lượt |
| Poll frontend | 30 s, timeout 10 s |
| Chu kỳ chụp ESP32 | 60 s, VGA 640×480, JPEG q12 |
