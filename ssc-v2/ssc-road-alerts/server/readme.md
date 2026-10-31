API | Chức năng
--- | ---
POST /api/cameras | Thêm camera và tọa độ
POST /api/road-alerts | Thêm tuyến LineString
PATCH/DELETE /api/cameras/:id | Sửa/xóa camera
PATCH/DELETE /api/road-alerts/:id | Sửa/xóa tuyến
POST /api/esp32/cameras/:id/capture | Nhận ảnh JPEG
GET /api/ai/jobs | Lấy ảnh chờ AI
POST /api/ai/results | Nhận kết quả AI
POST /api/test/simulate | Test cảnh báo không cần ảnh
POST /api/road-alerts/:id/alert |

## API AI và dự báo mưa mới

- `POST /api/ai/reports`: nhận `waste_level`, `flood_percentage`, `image_url`, `camera_id`.
- `GET /api/weather/cameras`: dự báo 12 giờ tới tại tọa độ camera đã lưu.

Xem [hướng dẫn header/body và checkbox vùng mưa](../docs/AI-WEATHER.md), hoặc chạy các request trong [ai-weather.http](../docs/ai-weather.http).

---

## Quy tắc chung

- Base URL demo local: `http://127.0.0.1:8000`.
- Ghi dữ liệu (`POST`/`PATCH`/`DELETE`) cần header `X-API-Key` khớp `ADMIN_API_KEY` (admin), `DEVICE_API_KEY` (thiết bị ESP32), hoặc `AI_API_KEY` (AI worker) — mặc định cả 3 dùng chung `ADMIN_API_KEY` nếu không set riêng.
- CORS mở cho mọi origin (`Access-Control-Allow-Origin` phản chiếu `Origin` gửi lên) — không còn giới hạn theo `FRONTEND_ORIGIN`, chỉ còn `X-API-Key` là lớp xác thực duy nhất cho request ghi dữ liệu.
- Mọi response đều là JSON (`Content-Type: application/json`), trừ `/api/images/:file` (trả JPEG nhị phân).
- Lỗi trả về dạng `{"error": "..."}` kèm status code tương ứng.

---

## 1. Camera & tuyến đường (CRUD)

### `GET /api/cameras` — danh sách camera (public, không cần key)

**Trả về:**
```json
{
  "cameras": [
    {
      "camera_id": "CAM-01", "name": "Camera Ngã 4", "road_id": "ROAD-01",
      "status": "online", "geometry": { "type": "Point", "coordinates": [106.7132, 10.7886] },
      "pending_count": 0,
      "monitoring": { "waste_coverage_pct": 12, "drain_blockage_pct": 5, "observed_at": "2026-09-16T04:00:00.000Z" },
      "images": { "original_url": "/api/images/xxx.jpg", "analyzed_url": "/api/images/yyy.jpg" },
      "analysis_source": "ai", "analysis_status": "fresh"
    }
  ],
  "fetched_at": "2026-09-16T04:05:00.000Z"
}
```
`monitoring`/`images`/`analysis_*` chỉ xuất hiện nếu camera đã có kết quả phân tích.

```js
const res = await fetch('http://127.0.0.1:8000/api/cameras');
const { cameras } = await res.json();
console.log(cameras);
```

### `GET /api/cameras/:id` — chi tiết 1 camera (public)

```js
const res = await fetch('http://127.0.0.1:8000/api/cameras/CAM-01');
console.log(await res.json()); // 404 nếu không tồn tại
```

### `POST /api/cameras` — tạo camera mới (cần key admin)

**Body (JSON), chỉ nhận đúng các field sau:**
| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `camera_id` | có | chuỗi 1–80 ký tự `A-Za-z0-9_-`, không trùng |
| `road_id` | không | phải trỏ tới `road_id` đã tồn tại nếu có |
| `name` | không | chuỗi |
| `status` | không | `online`/`offline`/`unknown` |
| `geometry` | có | `{ type: "Point", coordinates: [lng, lat] }`, lng ∈ [-180,180], lat ∈ [-90,90] |

```js
const res = await fetch('http://127.0.0.1:8000/api/cameras', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'abc' },
  body: JSON.stringify({
    camera_id: 'CAM-01',
    road_id: 'ROAD-01',
    name: 'Camera Ngã 4',
    geometry: { type: 'Point', coordinates: [106.7132, 10.7886] },
  }),
});
console.log(res.status, await res.json()); // 201 khi tạo mới, 409 nếu camera_id đã tồn tại
```

### `PATCH /api/cameras/:id` — sửa camera (cần key admin)

Body giống `POST` nhưng chỉ cần field muốn đổi (merge vào bản ghi cũ); **không được đổi `camera_id`**.

```js
await fetch('http://127.0.0.1:8000/api/cameras/CAM-01', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'abc' },
  body: JSON.stringify({ name: 'Camera Ngã 4 (đã dời vị trí)' }),
});
```

### `DELETE /api/cameras/:id` — xóa camera (cần key admin)

```js
await fetch('http://127.0.0.1:8000/api/cameras/CAM-01', {
  method: 'DELETE',
  headers: { 'X-API-Key': 'abc' },
});
```

### `GET /api/road-alerts` / `GET /api/road-alerts/:id` — danh sách/chi tiết tuyến (public)

**Trả về (mỗi tuyến):**
```json
{
  "road_id": "ROAD-01", "road_name": "Tuyến Ngã 4", "severity": "medium",
  "monitoring": { "waste_coverage_pct": 40, "flood_risk": "medium", "observed_at": "..." },
  "data_quality": "fresh", "camera_count": 2, "analyzed_camera_count": 2,
  "alert_id": "uuid-hoặc-ghép-nhiều-id",
  "description": "Tổng hợp mức rủi ro theo camera.",
  "manual_alert": { "severity": "high", "description": "...", "alert_id": "...", "expires_at": "..." },
  "weather": { "rain_expected": true, "observed_at": "...", "event_id": "..." }
}
```
`severity` được backend **tự tính** từ dữ liệu camera + cảnh báo thủ công + thời tiết, không set trực tiếp qua API thường.

```js
const roads = (await (await fetch('http://127.0.0.1:8000/api/road-alerts')).json()).roads;
```

### `POST /api/road-alerts` — tạo tuyến mới (cần key admin)

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `road_id` | có | chuỗi 1–80 ký tự, không trùng |
| `road_name` | không | chuỗi |
| `description` | không | chuỗi |
| `geometry` | có | `{ type: "LineString", coordinates: [[lng,lat], ...] }`, ≥ 2 điểm, không được là 1 điểm lặp lại |
| `severity` | không | mặc định `normal` khi tạo mới |

```js
await fetch('http://127.0.0.1:8000/api/road-alerts', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'abc' },
  body: JSON.stringify({
    road_id: 'ROAD-01',
    road_name: 'Tuyến Ngã 4',
    geometry: { type: 'LineString', coordinates: [[106.7112, 10.7874], [106.7132, 10.7886]] },
  }),
});
```

### `PATCH /api/road-alerts/:id` / `DELETE /api/road-alerts/:id` — sửa/xóa tuyến (cần key admin)

Xóa tuyến sẽ báo lỗi `409` nếu còn camera nào gắn `road_id` này.

```js
await fetch('http://127.0.0.1:8000/api/road-alerts/ROAD-01', {
  method: 'DELETE', headers: { 'X-API-Key': 'abc' },
});
```

---

## 2. ESP32 gửi dữ liệu quan sát

### `POST /api/esp32/observations` — báo quan sát mới, ảnh **đã có URL sẵn** (cần key device)

Dùng khi ảnh đã được lưu ở nơi khác (vd CDN riêng) và thiết bị chỉ cần báo link ảnh, KHÔNG upload ảnh qua request này.

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `camera_id` | có | phải là camera đã tồn tại và đã gắn `road_id` |
| `observation_id` | có | chuỗi 1–80 ký tự, dùng để chống trùng (gửi lại cùng ID + cùng nội dung → coi là idempotent) |
| `captured_at` | có | ISO 8601 có múi giờ, không được ở tương lai quá 5 phút |
| `image_url` | có (trừ khi mô phỏng) | URL `http(s)://...` hoặc path bắt đầu bằng `/` |

**Trả về:** `202` `{ observation: {...}, duplicate: false }` (mới) hoặc `200` `{ ..., duplicate: true }` (gửi trùng y hệt).

```js
const res = await fetch('http://127.0.0.1:8000/api/esp32/observations', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': '123' },
  body: JSON.stringify({
    camera_id: 'CAM-01',
    observation_id: 'OBS-' + Date.now(),
    captured_at: new Date().toISOString(),
    image_url: 'https://cdn.example.com/anh-camera.jpg',
  }),
});
console.log(res.status, await res.json());
```

### `POST /api/esp32/cameras/:camera_id/capture` — upload ảnh JPEG thật (cần key device)

Đây là API **nhận ảnh trực tiếp từ camera** (ESP32-CAM...) — body là **byte ảnh thô**, không phải JSON.

**Headers bắt buộc:**
| Header | Ý nghĩa |
|---|---|
| `Content-Type: image/jpeg` | bắt buộc đúng giá trị này |
| `X-API-Key` | key device |
| `X-Observation-Id` | chuỗi 1–80 ký tự, định danh duy nhất cho lần chụp |
| `X-Captured-At` | ISO 8601 có múi giờ, thời điểm chụp thật |

**Body:** buffer ảnh JPEG (bắt đầu bằng `FF D8`, kết thúc `FF D9`), tối đa 5MB.

**Trả về:** giống `/api/esp32/observations` (`202`/`200`), `image_url` trong response sẽ là `/api/images/<uuid>.jpg` do backend tự lưu.

```js
// Node.js: đọc 1 file JPEG có sẵn trên máy và gửi lên như thể là ảnh vừa chụp
import { readFile } from 'node:fs/promises';

const jpegBytes = await readFile('./anh-mau.jpg');
const res = await fetch('http://127.0.0.1:8000/api/esp32/cameras/CAM-01/capture', {
  method: 'POST',
  headers: {
    'Content-Type': 'image/jpeg',
    'X-API-Key': '123',
    'X-Observation-Id': 'OBS-' + Date.now(),
    'X-Captured-At': new Date().toISOString(),
  },
  body: jpegBytes,
});
console.log(res.status, await res.json());
```

```js
// Trình duyệt: gửi ảnh chụp từ <input type="file">
async function uploadCapture(file, cameraId) {
  const bytes = await file.arrayBuffer();
  const res = await fetch(`/api/esp32/cameras/${cameraId}/capture`, {
    method: 'POST',
    headers: {
      'Content-Type': 'image/jpeg',
      'X-API-Key': '123',
      'X-Observation-Id': 'OBS-' + Date.now(),
      'X-Captured-At': new Date().toISOString(),
    },
    body: bytes,
  });
  return res.json();
}
```

---

## 3. AI worker xử lý ảnh

### `GET /api/ai/jobs` — lấy danh sách quan sát cần xử lý (cần key AI)

**Query params:** `status` (`pending` mặc định, hoặc `processed`/`needs_review`/`failed`/`all`), `camera_id` (lọc theo camera), `limit` (1–200, mặc định 50).

```js
const url = new URL('http://127.0.0.1:8000/api/ai/jobs');
url.searchParams.set('status', 'pending');
url.searchParams.set('limit', '20');
const { jobs } = await (await fetch(url, { headers: { 'X-API-Key': 'ai-key' } })).json();
```

### `POST /api/ai/results` — trả kết quả phân tích cho 1 quan sát (cần key AI)

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `camera_id` | có | camera đã tồn tại |
| `observation_id` | có | observation đang ở trạng thái `pending` |
| `waste_coverage_pct` | có | số 0–100 |
| `drain_blockage_pct` | có | số 0–100 |
| `confidence` | có | số 0–1 (v2: không còn chặn kết quả, mọi kết quả đều `processed`; trường mới `usable`, `certainty`, `roi_version`... xem `ssc-v2/README-V2.md` mục "Thay đổi logic v2") |
| `analyzed_url` | không | URL ảnh đã qua xử lý (nếu có) |

```js
const res = await fetch('http://127.0.0.1:8000/api/ai/results', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'ai-key' },
  body: JSON.stringify({
    camera_id: 'CAM-01',
    observation_id: 'OBS-123',
    waste_coverage_pct: 72,
    drain_blockage_pct: 65,
    confidence: 0.93,
    analyzed_url: '/api/images/analyzed-OBS-123.jpg',
  }),
});
```

### `POST /api/ai/jobs/fail` / `POST /api/ai/jobs/retry` — đánh dấu lỗi / thử lại (cần key AI)

`fail` cần thêm field `error` (chuỗi 1–1000 ký tự); `retry` chỉ cần `camera_id` + `observation_id`, và observation phải đang ở trạng thái `failed`/`needs_review`.

```js
// Đánh dấu 1 job lỗi
await fetch('http://127.0.0.1:8000/api/ai/jobs/fail', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'ai-key' },
  body: JSON.stringify({ camera_id: 'CAM-01', observation_id: 'OBS-123', error: 'Model timeout' }),
});

// Đưa job trở lại hàng đợi pending để thử lại
await fetch('http://127.0.0.1:8000/api/ai/jobs/retry', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'ai-key' },
  body: JSON.stringify({ camera_id: 'CAM-01', observation_id: 'OBS-123' }),
});
```

### `POST /api/ai/reports` — báo cáo tổng hợp trực tiếp (không qua hàng đợi job, cần key AI)

Dùng khi AI worker muốn ghi thẳng 1 kết quả hoàn chỉnh (không cần có observation `pending` từ trước).

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `camera_id` | có | camera đã tồn tại và đã gắn tuyến |
| `waste_level` | có | `normal`/`low`/`medium`/`high`/`critical` |
| `flood_percentage` | có | số 0–100 |
| `image_url` | có | URL/path ảnh |
| `observation_id` | không | tự sinh UUID nếu bỏ trống |
| `captured_at` | không | mặc định thời điểm hiện tại |

```js
await fetch('http://127.0.0.1:8000/api/ai/reports', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'ai-key' },
  body: JSON.stringify({
    camera_id: 'CAM-01',
    waste_level: 'high',
    flood_percentage: 55,
    image_url: '/api/images/report-1.jpg',
  }),
});
```

---

## 4. Cảnh báo thủ công & thời tiết cho tuyến (cần key admin)

### `POST /api/road-alerts/:road_id/alert` — tạo cảnh báo thủ công

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `severity` | có | `low`/`medium`/`high`/`critical` |
| `description` | có | chuỗi 1–2000 ký tự |
| `ttl_seconds` | không | 1–86400, mặc định 3600 (thời gian cảnh báo tự hết hạn) |

```js
await fetch('http://127.0.0.1:8000/api/road-alerts/ROAD-01/alert', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'abc' },
  body: JSON.stringify({ severity: 'high', description: 'Ngập sâu, cấm xe máy', ttl_seconds: 7200 }),
});
```

### `DELETE /api/road-alerts/:road_id/alert` — xóa cảnh báo thủ công đang hiệu lực

```js
await fetch('http://127.0.0.1:8000/api/road-alerts/ROAD-01/alert', {
  method: 'DELETE', headers: { 'X-API-Key': 'abc' },
});
```

### `PUT /api/road-alerts/:road_id/weather` — cập nhật dự báo mưa cho tuyến

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `rain_expected` | có | boolean |
| `observed_at` | có | ISO 8601, phải **mới hơn** bản ghi thời tiết hiện có (nếu không sẽ `409`) |

```js
await fetch('http://127.0.0.1:8000/api/road-alerts/ROAD-01/weather', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'abc' },
  body: JSON.stringify({ rain_expected: true, observed_at: new Date().toISOString() }),
});
```

---

## 5. Tiện ích khác

### `GET /api/health` — kiểm tra server sống (public)
```js
console.log(await (await fetch('http://127.0.0.1:8000/api/health')).json());
// { status: "ok", version: 2, storage: "json", test_api: true }
```

### `GET /api/policy` — đọc ngưỡng cảnh báo hiện tại (public)
```js
console.log(await (await fetch('http://127.0.0.1:8000/api/policy')).json());
```

### `GET /api/weather/cameras` — dự báo mưa 12h tới cho từng camera (public)
```js
console.log(await (await fetch('http://127.0.0.1:8000/api/weather/cameras')).json());
```

### `GET /api/images/:file.jpg` — tải ảnh đã lưu (public, trả JPEG nhị phân)
```js
const res = await fetch('http://127.0.0.1:8000/api/images/xxxxxxxx-xxxx.jpg');
const blob = await res.blob(); // dùng cho <img src={URL.createObjectURL(blob)}>
```

### `POST /api/test/simulate` — mô phỏng cảnh báo không cần ảnh thật (cần key admin, chỉ hoạt động khi `ENABLE_TEST_API` khác `"false"`)

Tạo 1 observation "giả lập" (`simulated: true`) và áp kết quả AI ngay lập tức, tiện để demo giao diện mà không cần thiết bị/AI thật.

| Field | Bắt buộc | Ràng buộc |
|---|---|---|
| `camera_id` | có | camera đã tồn tại, đã gắn tuyến |
| `observation_id` | có | chuỗi 1–80 ký tự |
| `captured_at` | có | ISO 8601 |
| `waste_coverage_pct` | có | số 0–100 |
| `drain_blockage_pct` | có | số 0–100 |
| `confidence` | không | mặc định 0.99 |
| `image_url` | không | ảnh minh họa (tùy chọn) |
| `analyzed_url` | không | ảnh đã "phân tích" minh họa |

```js
await fetch('http://127.0.0.1:8000/api/test/simulate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': 'abc' },
  body: JSON.stringify({
    camera_id: 'CAM-01',
    observation_id: 'DEMO-' + Date.now(),
    captured_at: new Date().toISOString(),
    waste_coverage_pct: 86,
    drain_blockage_pct: 82,
  }),
});
```
