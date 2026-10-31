# Backend demo SSC — JSON, ESP32 và AI

Backend tiếp tục dùng Node.js tích hợp sẵn (`node:http`), không có database hoặc dependency server mới. Frontend hiện có tiếp tục đọc hai API cũ.

## Chạy thử nhanh nhất

Trong thư mục project, chạy `npm run backend:watch` ở terminal thứ nhất, `npm run dev` ở terminal thứ hai. Nếu cổng 8000 đã có backend phiên cũ, dừng tiến trình đó trước khi chạy bản mới. Kiểm tra GET `http://127.0.0.1:8000/api/health` trả `version: 2`.

Chưa có ESP32 / AI? Ở terminal thứ ba chạy:

```powershell
npm run demo:seed
```

Lệnh này gọi API để **thêm** một tuyến, một camera và một kết quả mô phỏng có ID mới; không xóa hay thay dữ liệu cũ. Chạy nhiều lần sẽ thêm nhiều bộ dữ liệu. Trên frontend chọn **Máy chủ**, bấm **Cập nhật dữ liệu**; tuyến mới sẽ được tô màu. Chế độ “Mô phỏng minh họa” của frontend là bộ dữ liệu tĩnh khác, không đọc backend.

Xem các request sẵn trong `docs/api.http` bằng REST Client, hoặc nhập method, URL, headers, body tương ứng vào Postman/curl. Không cần cài REST Client để server hoạt động.

## Hai file dữ liệu

| File | Nội dung |
|---|---|
| `server/data/cameras.json` | `{"cameras": [...]}`: vị trí camera, road_id, trạng thái liên lạc, hàng đợi/lịch sử `observations`, kết quả được chấp nhận gần nhất `latest_analysis` |
| `server/data/road-alerts.json` | `{"roads": [...]}`: ID, tên, LineString tuyến, cảnh báo thủ công có hạn và bản tin mưa |

Hai file hiện có được tái sử dụng. Khi chưa có file, bộ sưu tập được coi là rỗng và tạo khi có lần ghi đầu. Không tự chèn mẫu vào dữ liệu thật. JPEG upload nằm riêng trong `server/data/images/`, không nhúng base64 vào JSON. `/api/images/<uuid>.jpg` phục vụ ảnh để client và worker đọc.

API GET camera ẩn hàng đợi nội bộ, trả `monitoring` và `images` mà frontend cần. GET road tính tổng hợp từ các camera liên kết ở thời điểm request, không cần ghi lại file tuyến khi AI cập nhật. Vì vậy mỗi thao tác chỉ commit một file; không có hai bản chỉ số tổng hợp dễ lệch nhau. Trạng thái tác vụ tồn tại sau khi khởi động lại.

Store xếp hàng các thao tác ghi trong một tiến trình, ghi file tạm → flush → rename thay thế file đích. JSON đang lỗi trả 500, không tự reset mất dữ liệu. Chỉ chạy **một tiến trình backend ghi trên cùng thư mục**; không dùng cluster / nhiều server và không sửa bằng editor trong lúc API đang ghi. Đây không phải cơ chế transaction của database. Sao lưu cả hai file và thư mục ảnh khi server đã dừng.

## Luồng ESP32 → AI → frontend

1. Người quản trị tạo tuyến LineString, rồi camera Point có `road_id`. Tọa độ là WGS84 `[kinh độ, vĩ độ]`. Camera cố định không cần gửi tọa độ lại với mỗi ảnh.
2. ESP32 chụp JPEG, tạo `observation_id` duy nhất và `captured_at` ISO 8601 UTC. Gửi JPEG nhị phân tới `/api/esp32/cameras/:id/capture`, hoặc gateway gửi JSON chứa `image_url` tới `/api/esp32/observations`.
3. Backend kiểm tra camera/tuyến, lưu ảnh và tác vụ `pending`, trả 202. Gửi lại đúng ID + timestamp + ảnh/URL cũ trả 200 `duplicate: true`; cùng ID nhưng đổi nội dung trả 409. ID quan sát chỉ cần duy nhất trong từng camera.
4. AI worker lấy `/api/ai/jobs?status=pending`, đọc ảnh, chạy mô hình và trả `camera_id`, `observation_id`, tỷ lệ rác, tỷ lệ che cống, confidence và URL ảnh phân tích nếu có.
5. Backend nhận `/api/ai/results`, kiểm tra kết quả, cập nhật camera rồi tổng hợp tuyến khi frontend GET. Phân loại mức độ được tính trên server, không tin severity tùy ý do ESP32 gửi.
6. Frontend nhận các đoạn đường và ảnh qua API cũ; tự cập nhật mỗi 30 giây hoặc bấm nút cập nhật.

### Gửi JPEG từ ESP32

```http
POST /api/esp32/cameras/CAM-001/capture
Content-Type: image/jpeg
X-API-Key: <DEVICE_API_KEY>
X-Observation-Id: <mã ảnh duy nhất>
X-Captured-At: 2026-09-09T13:00:00Z

<bytes JPEG>
```

Ví dụ curl khi đã tạo CAM-001 và có ảnh:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/esp32/cameras/CAM-001/capture `
  -H "Content-Type: image/jpeg" `
  -H "X-Observation-Id: FRAME-001" `
  -H "X-Captured-At: 2026-09-09T13:00:00Z" `
  --data-binary "@capture.jpg"
```

Thay timestamp ví dụ bằng thời gian chụp hiện tại; ảnh quá 15 phút vẫn được ghi nhận nhưng kết quả không áp dụng vào hiện trạng tuyến. Với ESP32 dùng `HTTPClient.POST(fb->buf, fb->len)` sau khi thêm các header. Khởi tạo `esp_camera`, Wi-Fi/SIM7080 và đồng bộ giờ SNTP là phần firmware của nhóm. `127.0.0.1` trên ESP32 là chính thiết bị, nên phải dùng địa chỉ LAN của máy chạy server. Giữ nguyên ID, timestamp và bytes khi retry; nếu khởi động lại cần boot ID/random đủ khác biệt để không tái sử dụng mã ảnh cũ.

Giới hạn ảnh 5 MiB, chỉ nhận Content-Type JPEG và kiểm tra dấu đầu/cuối JPEG; đây không thay thế bộ giải mã ảnh thật. Model/adapter phải xử lý ảnh hỏng. Không hỗ trợ multipart/form-data hoặc base64 trong endpoint nhị phân. JSON giới hạn 64 KiB.

### Worker AI thật

Đã có runner `server/ai-worker.js`, nhưng **chưa có model nhận diện rác được huấn luyện**. Nhóm cung cấp module Node export:

```javascript
export async function analyze(jpegBuffer, job) {
  // Gọi model của nhóm (ví dụ service Python), dùng vùng quan tâm của camera.
  // Trả kết quả thực tế của model, không phải các số hằng minh họa.
  return {
    waste_coverage_pct: result.wasteCoveragePct,
    drain_blockage_pct: result.drainBlockagePct,
    confidence: result.confidence,
    analyzed_url: result.annotatedImageUrl
  };
}
```

`result` trên là đầu ra model của bạn; ví dụ này mô tả contract, không phải module chạy độc lập. Nếu chạy Python, có thể bỏ runner Node và cho Python gọi trực tiếp các API job/result.

```powershell
$env:AI_ADAPTER_MODULE="C:\duong-dan\model-adapter.mjs"
$env:AI_API_KEY="khoa-ai-da-cau-hinh"
npm run ai:worker
# Chạy một lượt:
npm run ai:worker -- --once
```

Runner xử lý tuần tự, mặc định kiểm tra mỗi 3 giây, chỉ tải ảnh `/api/images/<uuid>.jpg` cùng SSC server, không tự truy cập URL bất kỳ do thiết bị gửi. Nguồn ảnh bên ngoài cần adapter/worker có allowlist riêng. Server chỉ lưu URL, không tự fetch. Chạy một worker demo; chưa có claim/lease, nên nhiều worker có thể chạy trùng một ảnh (callback trùng giống nhau vẫn idempotent). Adapter/model nên có timeout xử lý riêng.

## Các API

| Method | Endpoint | Chức năng / khóa |
|---|---|---|
| GET | `/api/health`, `/api/policy` | Sức khỏe và cấu hình đánh giá |
| GET | `/api/cameras`, `/api/cameras/:id` | Camera cho client |
| POST | `/api/cameras` | Tạo camera / admin |
| PATCH | `/api/cameras/:id` | Đổi tên, Point, road_id, trạng thái ban đầu / admin |
| DELETE | `/api/cameras/:id` | Xóa camera và metadata lịch sử trong file / admin |
| GET | `/api/road-alerts`, `/api/road-alerts/:id` | LineString + monitoring tổng hợp |
| POST | `/api/road-alerts` | Tạo tuyến / admin |
| PATCH | `/api/road-alerts/:id` | Sửa tên, mô tả, geometry, severity nền / admin |
| DELETE | `/api/road-alerts/:id` | Xóa tuyến không còn camera / admin |
| POST | `/api/esp32/observations` | Tạo tác vụ bằng image_url / device |
| POST | `/api/esp32/cameras/:id/capture` | Upload JPEG + tạo tác vụ / device |
| GET | `/api/ai/jobs` | Xem pending/processed/needs_review/failed/all; lọc camera_id, limit 1–200 / AI |
| POST | `/api/ai/results` | Trả kết quả theo mã ảnh / AI |
| POST | `/api/ai/jobs/fail` | Đánh dấu lỗi tác vụ pending / AI |
| POST | `/api/ai/jobs/retry` | Đưa failed/needs_review về pending / AI |
| POST | `/api/road-alerts/:id/alert` | Tạo/thay cảnh báo thủ công có TTL / admin |
| DELETE | `/api/road-alerts/:id/alert` | Gỡ riêng cảnh báo thủ công / admin |
| PUT | `/api/road-alerts/:id/weather` | Nhận dự báo mưa, observed_at / admin |
| POST | `/api/test/simulate` | Tạo quan sát và áp kết quả giả lập trong một lần gọi / admin |
| GET | `/api/images/:filename` | Đọc JPEG upload, tên UUID do server cấp |

API tạo/sửa chỉ nhận các trường đã định nghĩa, không cho client ghi trực tiếp hàng đợi, latest_analysis hay incident ID. Không đổi ID qua PATCH. Camera phải liên kết tới tuyến tồn tại trước khi nhận ảnh. Không chuyển camera đang có job pending; khi đổi tuyến, phân tích cũ của camera bị bỏ khỏi hiện trạng để tránh áp chỉ số cho tuyến khác. Xóa tuyến có camera trả 409, không tự xóa dây chuyền.

### Body tạo tuyến/camera

```json
{"road_id":"R1","road_name":"Tuyến thử","geometry":{"type":"LineString","coordinates":[[106.7,10.77],[106.71,10.78]]}}
```

```json
{"camera_id":"C1","road_id":"R1","name":"Cửa cống 01","geometry":{"type":"Point","coordinates":[106.7,10.77]}}
```

Body callback AI:

```json
{"camera_id":"C1","observation_id":"FRAME-001","waste_coverage_pct":82,"drain_blockage_pct":75,"confidence":0.96}
```

Body test không cần ảnh (thay timestamp hiện tại, đổi observation_id cho mỗi lần):

```json
{"camera_id":"C1","observation_id":"SIM-001","captured_at":"2026-09-09T13:00:00Z","waste_coverage_pct":92,"drain_blockage_pct":85,"confidence":0.99}
```

## Quy tắc đánh giá và dữ liệu cũ

File `server/config.js` chứa policy đề xuất cho demo. Với mỗi camera lấy `max(waste_coverage_pct, drain_blockage_pct)`; trên một tuyến lấy giá trị lớn nhất trong từng chỉ số của các camera còn dữ liệu mới, nhằm không làm mất một cửa cống rủi ro cao do tính trung bình.

| Điểm | Severity nền |
|---|---|
| <20 | normal |
| 20–<50 | low |
| 50–<70 | medium |
| 70–<90 | high |
| ≥90 | critical |

Nếu có tín hiệu mưa mới, mức từ medium trở lên tăng một bậc, tối đa critical. Mưa đơn lẻ tạo ít nhất medium. Cảnh báo thủ công có TTL 1–86400 giây (mặc định 3600) chỉ nâng mức ưu tiên, không làm giảm nguy cơ AI cao hơn. Xóa cảnh báo thủ công không xóa cảnh báo tự động. `flood_risk` là chỉ báo rủi ro demo theo các tín hiệu này, **không phải kết quả đo nước hay dự báo thủy văn**. Cần hiệu chỉnh ngưỡng bằng dữ liệu gán nhãn trước ứng dụng thực tế.

Kết quả confidence <0.5 chuyển `needs_review`, không ghi đè phân tích tin cậy trước đó. Kết quả cũ hơn hoặc cùng thời điểm kết quả hiện tại, khác tuyến, hoặc ảnh đã quá 15 phút được lưu `processed` nhưng `applied:false`. Timestamp tương lai quá 5 phút bị từ chối. Cập nhật thấp hơn sau một ảnh **mới hơn** là hợp lệ (ví dụ vừa thu gom rác).

Chỉ số camera và bản tin mưa quá 15 phút không dùng trong tổng hợp hiện tại. Tuyến trả `data_quality: fresh | partial | unknown | unconfigured`; thiếu chỉ số không được thay bằng số 0. `severity: normal` với `data_quality: unknown` chỉ có nghĩa chưa tính được cảnh báo, không khẳng định an toàn; UI có thông báo thiếu phân tích. Camera còn giữ ảnh/giá trị gần nhất và nhãn stale để đối chiếu. `status` online/offline được suy ra từ lần liên lạc gần nhất khi đã nhận ảnh; không phụ thuộc model chạy thành công hay không.

`alert_id` giữ ổn định trong một đợt camera có rủi ro liên tục; đợt sau khi trở lại normal hoặc hết hạn sinh ID mới. Thay tập camera đang rủi ro/thời tiết/ghi đè thủ công có thể đổi ID tổng hợp tuyến. Frontend tiếp tục chống thông báo lặp theo ID và nhóm điều kiện.

## LAN, khóa và giới hạn demo

Mặc định server bind 127.0.0.1, không khóa nhưng chỉ cho ghi từ loopback với Host hợp lệ. Nhận ESP32 trên LAN cần chủ động cấu hình:

```powershell
$env:HOST="0.0.0.0"
$env:ADMIN_API_KEY="thay-bang-khoa-quan-tri-rieng"
$env:DEVICE_API_KEY="thay-bang-khoa-thiet-bi-rieng"
$env:AI_API_KEY="thay-bang-khoa-worker-rieng"
$env:ENABLE_TEST_API="false"
npm run backend
```

Thêm `X-API-Key` theo vai trò trong các request. Khi không khai DEVICE_API_KEY/AI_API_KEY, hai vai trò dùng ADMIN_API_KEY nếu có. Giao diện chỉ GET dữ liệu, không nhúng khóa quản trị vào VITE. Nếu thử `demo:seed` khi đã đặt khóa, terminal chạy lệnh seed cũng cần ADMIN_API_KEY. Muốn dùng API test, để ENABLE_TEST_API=true (mặc định); tắt khi không cần.

Các biến server đọc từ môi trường tiến trình, không tự đọc `.env` của Vite. CORS qua FRONTEND_ORIGIN, mặc định http://localhost:5173. Cổng qua PORT=8000. Chỉ cấu hình máy và firewall trong mạng tin cậy cho demo. API GET camera/tuyến/ảnh hiện không có đăng nhập; khóa device là khóa chung, chưa định danh riêng từng ESP32. Muốn triển khai thật cần TLS, quyền thiết bị theo camera, kiểm soát đọc ảnh, rate limiting, lưu trữ/queue lâu dài và xác thực người vận hành.

Lưu tối đa 100 observations mỗi camera. Khi đầy, loại metadata terminal cũ nhất; nếu toàn bộ pending, trả 429 để thiết bị retry sau. Idempotency chỉ đảm bảo với ID còn lưu trong lịch sử này. Ảnh không tự xóa khi metadata bị loại hoặc camera bị xóa, nên có thể phục hồi/đối chiếu nhưng dung lượng sẽ tăng. Demo chưa có tác vụ dọn ảnh; quản lý và sao lưu thư mục ảnh riêng. Nếu lưu JSON thất bại sau khi ghi JPEG có thể còn ảnh mồ côi, không tạo tác vụ giả thành công.

Mã lỗi: 400 dữ liệu sai; 401 sai/thiếu khóa; 403 origin/host sai; 404 không tìm thấy; 409 trùng ID/xung đột liên kết/trạng thái; 413 body quá lớn; 415 MIME sai; 429 hàng đợi đầy; 500 lỗi lưu trữ. `duplicate:true`, `status` và `applied` trong response phải được kiểm tra, không chỉ HTTP 200.

## Kiểm tra

`npm test` chạy HTTP server trên cổng tạm, file JSON trong thư mục tạm; không sửa dữ liệu thật. Test bao gồm CRUD, liên kết, restart, concurrency, ảnh JPEG, role key, dữ liệu lỗi, callback trùng, kết quả đến sai thứ tự, confidence thấp, TTL, thời tiết và mô phỏng. `npm run build` kiểm tra tương thích frontend.

File cấu trúc: `app.js` routing/auth/body, `service.js` nghiệp vụ, `store.js` JSON, `aggregation.js` tổng hợp, `config.js` ngưỡng, `ai-worker.js` tích hợp model, `seed-demo.js` dữ liệu thử. Trạng thái xác nhận/lập phiếu của người vận hành vẫn là localStorage từ frontend; backend mới này tập trung dữ liệu camera/AI/cảnh báo, chưa đồng bộ điều phối đa người dùng.
