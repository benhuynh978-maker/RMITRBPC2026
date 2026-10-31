# SSC v2 — bản sao để nghiên cứu (R&D)

Thư mục `ssc-v2/` là **bản sao của hệ thống chính**, tạo ngày **2026-10-11**, dùng để thử nghiệm mà không ảnh hưởng tới hệ thống đang chạy thật. Bản sao gồm:

- `ssc-road-alerts/` — backend Node (`server/`), frontend React + Vite (`src/`), test (`tests/`)
- `inference/` — AI worker Python (`ai_worker.py`, `analysis.py`)
- `test-WebUI-modelAI/` — site demo FastAPI cho giám khảo

Dữ liệu (`ssc-road-alerts/server/data/`) và ảnh upload là **của riêng bản v2**. Trọng số model vẫn đọc dùng chung từ `C:\Users\ASUS\Desktop\SSC\runs\...\best.pt` (chỉ đọc); Python dùng chung `C:\Users\ASUS\Desktop\SSC\.venv`.

## Bảng cổng

| Thành phần | Hệ thống chính | Bản v2 |
|---|---|---|
| Backend HTTP | 8000 | **8010** |
| Backend HTTPS (cho modem, cần `server/certs/`) | 8443 (Tailscale Funnel trỏ vào đây) | **8453** |
| Frontend Vite dev | 5173 | **5174** (strictPort, proxy `/api` → `http://127.0.0.1:8010`) |
| Site demo FastAPI | 8100 | **8110** |

Biến môi trường `PORT`, `HTTPS_PORT`, `SSC_API_URL`, `AI_MODEL_PATH`, `SSC_IMAGES_DIR` vẫn ghi đè được giá trị mặc định.

## Chạy bản v2

Backend (terminal 1):

```powershell
cd C:\Users\ASUS\Desktop\SSC\ssc-v2\ssc-road-alerts
npm run backend          # http://127.0.0.1:8010/api/health (+ https 8453 nếu có certs/)
```

Frontend (terminal 2):

```powershell
cd C:\Users\ASUS\Desktop\SSC\ssc-v2\ssc-road-alerts
npm run dev              # http://localhost:5174
```

AI worker (terminal 3):

```powershell
cd C:\Users\ASUS\Desktop\SSC\ssc-v2\inference
..\..\.venv\Scripts\python.exe -B ai_worker.py      # mặc định gọi http://127.0.0.1:8010
```

Site demo (tùy chọn):

```powershell
cd C:\Users\ASUS\Desktop\SSC\ssc-v2\test-WebUI-modelAI\server
..\..\..\.venv\Scripts\python.exe -B -m uvicorn app:app --host 0.0.0.0 --port 8110
```

Test: `npm test` trong `ssc-v2\ssc-road-alerts` (vitest tự mở server ở cổng tạm, dữ liệu tạm).

## Lưu ý quan trọng

- **ESP32 thật vẫn gửi ảnh vào hệ thống chính** (Tailscale Funnel → cổng 8443 của bản chính). Firmware `.ino` trong bản sao **không được sửa**, vẫn trỏ 8443. Bản v2 không nhận ảnh thật trừ khi chủ động chuyển.
- Không chạy AI worker của bản chính trỏ vào v2 hay ngược lại — mỗi bản một worker, một backend.

## Chuyển sang dùng v2 sau này

Khi v2 đủ ổn định, chuyển đổi = **trỏ thiết bị, worker và frontend sang v2**:

1. Thiết bị: đổi Tailscale Funnel trỏ vào cổng HTTPS của v2 (ví dụ `tailscale funnel --bg --https=8443 https+insecure://localhost:8453`), hoặc chạy v2 với `HTTPS_PORT=8443` sau khi tắt backend chính.
2. Worker: chạy `inference/ai_worker.py` của v2 (mặc định đã trỏ 8010), tắt worker của bản chính.
3. Frontend: dùng `npm run dev` của v2 (5174) hoặc build v2 và đặt reverse proxy `/api` về 8010.

## Thay đổi logic v2

Thử nghiệm cho thấy: (1) đo độ che cống **bên trong một vùng miệng cống (ROI) cố định theo camera** chính xác hơn hẳn công thức cũ (công thức cũ cần model *nhìn thấy* cống, nên cống bị che kín lại ra "không có giá trị"); (2) trung vị 5 lần đo + trễ (hysteresis) giảm ~90% hiện tượng nhấp nháy trạng thái; (3) `confidence = min(mọi detection)` phản thông tin — ảnh càng nhiều rác càng thấp — nên gần như mọi ảnh có rác bị đẩy vào `needs_review` và bản đồ bị lệch về "sạch". Phạm vi: 1 camera = 1 cống; ban ngày, thời tiết tốt (ảnh tối → `usable:false`).

### 1. `drain_roi` trên camera (admin ghi qua `POST /api/cameras`, `PATCH /api/cameras/:id`)

```json
"drain_roi": { "polygon": [[0.30,0.55],[0.70,0.55],[0.72,0.85],[0.28,0.85]], "source": "manual", "calibrated_at": "2026-10-11T03:00:00.000Z" }
```

- `polygon`: 3–64 điểm `[x,y]`, số hữu hạn trong `[0,1]` (tọa độ ảnh chuẩn hóa, x sang phải, y xuống dưới). `source`: `ai` | `manual` (bắt buộc khi gửi polygon). Không nhận trường lạ khác.
- `calibrated_at` **do server đặt** (bỏ qua giá trị client gửi) mỗi khi polygon đổi, luôn tăng ngặt so với bản trước; đây chính là **phiên bản ROI**. Gửi lại cùng polygon (vd chỉ đổi `source`) thì giữ nguyên phiên bản.
- `"drain_roi": null` gỡ ROI. Đổi hoặc gỡ ROI → **xóa `drain_state`** của camera (số đo bằng ROI khác không so sánh được). Không chặn khi còn job pending: kết quả mang `roi_version` cũ chỉ không được tính.
- Đổi `road_id` của camera cũng xóa `drain_state` (như `latest_analysis`).
- Validate ở cả lúc đọc và lúc ghi file (`validation.js`).

### 2. Hợp đồng job / result với AI worker

`GET /api/ai/jobs` — mỗi job thêm `drain_roi`: `{ "polygon": [[x,y],...], "version": "<calibrated_at>" }` hoặc `null` (camera chưa hiệu chỉnh). Giá trị là ROI hiện tại lúc GET.

`POST /api/ai/results` — các trường cũ giữ nguyên (`camera_id`, `observation_id`, `waste_coverage_pct`, `drain_blockage_pct`, `confidence`, `analyzed_url`), thêm tùy chọn:

| Trường | Kiểu | Mặc định | Ghi chú |
|---|---|---|---|
| `usable` | boolean | `true` | `false` → được bỏ trống cả hai phần trăm |
| `quality_reason` | chuỗi 1–64 ký tự | — | chỉ cho phép khi `usable === false`, vd `thieu_sang` |
| `certainty` | số 0–1 hoặc `null` | `null` | chỉ để gắn nhãn, không chặn |
| `no_trash_in_roi` | boolean | — | |
| `blockage_method` | `roi` \| `legacy` | `legacy` | |
| `roi_version` | chuỗi 1–64 ký tự hoặc `null` | `null` | gửi lại đúng `drain_roi.version` của job |

- `waste_coverage_pct` vẫn bắt buộc khi `usable !== false`; `confidence` vẫn bắt buộc (giữ để tương thích).
- Kết quả được lưu ở dạng chuẩn hóa (luôn có `usable`, `certainty`, `blockage_method`, `roi_version`). Idempotency giữ nguyên: gửi lại phải giống hệt sau chuẩn hóa, khác → 409. Payload kiểu cũ (không có trường mới) chạy như trước; kết quả cũ đã lưu trước v2 được chuẩn hóa khi so sánh nên gửi lại vẫn là `duplicate`.

### 3. Thay đổi gating

- Mọi kết quả đều thành `processed` — **không còn sinh `needs_review` theo confidence** (`POLICY.minConfidence` giữ lại nhưng không dùng để chặn). Trạng thái `needs_review` cũ vẫn hợp lệ trong dữ liệu; `jobs/retry` vẫn dùng được.
- Observation lưu thêm `usable` và `low_certainty = (certainty là số && certainty < 0.5)`.
- `latest_analysis` chỉ cập nhật khi: mới hơn + còn tươi (≤ 15 phút) + cùng tuyến + `usable === true`. Shape giữ nguyên; `monitoring` thêm `blockage_method`, `low_certainty`, và `certainty` / `no_trash_in_roi` khi có. Severity tuyến vẫn tính bằng `evaluateSeverity` trên số thô như cũ.
- `usable:false` không bao giờ cập nhật `latest_analysis` và không tính vào `drain_state`.

### 4. `drain_state` theo camera (lưu trong `cameras.json`)

Tính lại trong cùng transaction mỗi khi lưu một kết quả `usable` cho ảnh **còn hiện hành** (chụp ≤ 15 phút trước và cùng tuyến):

- Cửa sổ = các observation `processed`, `usable !== false`, có `drain_blockage_pct` là số, `roi_version` khớp phiên bản ROI hiện tại (`null === null` cho camera chưa hiệu chỉnh), cùng tuyến hiện tại, chụp trong vòng 15 phút tính từ lần đo mới nhất; lấy tối đa 5 lần mới nhất.
- Dưới 3 lần đo → `state:'unknown'`, `reason:'collecting'`, kèm `window_count` và `needed`.
- Giá trị = **trung vị** (số chẵn lấy trung bình hai giá trị giữa), làm tròn 2 chữ số.
- Ngưỡng + trễ (`POLICY.drainState`: `windowSize 5`, `minReadings 3`, `clean {enter 50, exit 35}`, `watch {enter 20, exit 12}`, `lowCertainty 0.5`):

| Trạng thái trước | → `clean` | → `watch` | → `clear` |
|---|---|---|---|
| không có / `unknown` / `clear` | v ≥ 50 | 20 ≤ v < 50 | v < 20 |
| `watch` | v ≥ 50 | 12 ≤ v < 50 | v < 12 |
| `clean` | v ≥ 35 | 12 ≤ v < 35 | v < 12 |

```json
"drain_state": { "state": "clean", "smoothed_blockage_pct": 55, "window_count": 5, "updated_at": "...",
  "evidence_observation_id": "...", "evidence_captured_at": "...", "roi_calibrated": true, "blockage_method": "roi",
  "flags": { "no_trash_in_roi": false, "low_certainty": false }, "since": "...", "reason": "ok" }
```

`smoothed_blockage_pct` vắng khi `unknown`; `since` = lúc trạng thái đổi lần cuối (giữ nguyên nếu không đổi); `flags.no_trash_in_roi` lấy từ lần đo mới nhất, `flags.low_certainty` = có ít nhất một lần đo certainty thấp trong cửa sổ.

**Lúc đọc** (`GET /api/cameras`): trả thêm `drain_roi` và `drain_state`. Nếu `evidence_captured_at` (hoặc `updated_at` khi chưa có bằng chứng) quá 15 phút, hoặc camera mất kết nối (`last_seen_at` quá hạn) → trình bày `state:'unknown'`, `reason:'stale'` (bỏ `smoothed_blockage_pct`, `since`), **không ghi lại file**. Camera chưa có `drain_state` → `{ state:'unknown', reason:'no_data', window_count:0, roi_calibrated }`.

### 5. `drain_summary` trên tuyến (`GET /api/road-alerts`)

Bổ sung, không đổi các trường/severity cũ:

```json
"drain_summary": { "clear": 1, "watch": 0, "clean": 1, "unknown": 1, "worst_state": "clean", "worst_camera_id": "CAM-02" }
```

Đếm theo trạng thái lúc đọc ở trên. `worst_state` = trạng thái đã biết khẩn nhất (`clean` > `watch` > `clear`; hòa thì lấy `smoothed_blockage_pct` cao hơn); tất cả `unknown` → `worst_state:'unknown'`, `worst_camera_id:null`.

### 6. Đổi tên trên giao diện

Nhãn "Tỉ lệ ngập" (trường `drain_blockage_pct`) đổi thành **"Mức che miệng cống"** ở WebUI (`Metrics.tsx`, lý do cảnh báo trong `monitoringService.ts`, ghi chú ngưỡng ở `App.tsx`), site demo `test-WebUI-modelAI/web/index.html` và README. Tên biến/trường (`flood*`, `drain_blockage_pct`) giữ nguyên. "Nguy cơ ngập" (flood risk) là khái niệm khác, không đổi.
