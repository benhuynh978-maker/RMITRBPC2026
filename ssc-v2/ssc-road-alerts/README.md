# CleanSight Road Monitor — Giám sát rác và nguy cơ ngập

Frontend React 19 + TypeScript + Vite + React-Leaflet, tích hợp phần Web Application của hệ thống.

Luồng: camera / IoT → backend / AI → chỉ số tổng hợp tuyến → bản đồ, thông báo → người vận hành xác nhận và lập phiếu thu gom.

## Backend v2: ESP32 / AI và API test

Đã thêm API tạo/sửa/xóa camera và tuyến, upload JPEG, hàng đợi AI lưu JSON, callback kết quả, cảnh báo thủ công có hạn và bản tin mưa. Xem [hướng dẫn backend](docs/BACKEND.md) và [request mẫu](docs/api.http).

Sau khi chạy backend, dùng `npm run demo:seed` để thêm một bộ dữ liệu mô phỏng qua API, rồi chọn nguồn **Máy chủ** trên frontend. Lệnh này thêm ID mới và không xóa dữ liệu đã có. Ngưỡng đánh giá server nằm ở `server/config.js`.

## Chạy tại máy

Node.js >=22. Mở terminal tại `C:\Users\yanas\Music\SCC-frontend\ssc-road-alerts`:

```powershell
npm ci
npm run backend
```

Mở terminal thứ hai trong cùng thư mục:

```powershell
npm run dev
```

Mở URL do Vite in ra (bản v2: http://localhost:5174, strictPort). Không mở trực tiếp `index.html`. API mặc định http://127.0.0.1:8010; Vite proxy `/api` về cổng 8010. Không cần cài lại nếu `node_modules` đã đủ.

Để chạy thử giao diện ngay cả khi chưa có backend: chọn **Nguồn dữ liệu → Mô phỏng minh họa**. Dữ liệu mẫu cố định trong `src/mocks/monitoring.ts`, có nhãn mô phỏng rõ ràng, không được ghi vào file dữ liệu thật. Chế độ máy chủ không tự chèn mock khi lỗi.

## Các tính năng đã tích hợp

- Bản đồ zoom theo tuyến và từng camera; liên kết camera với tuyến qua `road_id`.
- Vẽ đúng GeoJSON LineString bằng polyline, màu theo mức ưu tiên, thêm marker đại diện tại nửa chiều dài tuyến. Mặc định bật hai lớp, có thể tắt độc lập.
- Danh sách tuyến, tìm theo tên/mã, lọc tuyến cần chú ý; thống kê tuyến, camera online, tín hiệu mưa.
- Chọn tuyến: chỉ số tổng hợp mật độ rác, mức che miệng cống, nguy cơ ngập, tín hiệu mưa và danh sách camera.
- Chọn camera: trạng thái vận hành, chỉ số quan sát, ảnh chụp gốc, ảnh kết quả AI; ảnh thiếu/lỗi có trạng thái rõ ràng. Nhấn ảnh mở kích thước đầy đủ. Ảnh demo không có sẵn, không dùng ảnh giả làm kết quả AI.
- Thông báo trong trang khi có cảnh báo mới hoặc thay đổi mức/điều kiện. Sắp xếp khẩn cấp trước. Không lặp lại thông báo chỉ vì timestamp polling đổi hoặc chỉ số dao động trong cùng nhóm điều kiện.
- Xác nhận đã xem, nhập đơn vị/ghi chú và tải phiếu `.txt` chứa vị trí, thời điểm quan sát, lý do, camera và mức ưu tiên.
- Giữ công cụ lấy tọa độ, nguồn nền dự phòng và hai API đọc hiện có. API tuyến cần đọc dữ liệu camera để tổng hợp; nếu file camera lỗi, API tuyến cũng báo lỗi thay vì kết luận an toàn.

**Ranh giới điều phối:** backend đã có API camera/AI/cảnh báo; chưa có API đồng bộ việc tiếp nhận/lập phiếu của người vận hành. Xác nhận và thông tin lập phiếu được lưu bằng localStorage tại trình duyệt, tách biệt giữa API và demo; chưa đồng bộ nhiều người. Xuất phiếu không gửi tới đội vệ sinh, không có trạng thái “đã tiếp nhận/hoàn tất”. Người vận hành gửi phiếu qua kênh của đơn vị. Khi API tuyến lỗi, giữ số liệu cũ với thông báo và khóa xác nhận/xuất phiếu đến khi kết nối lại. Lỗi lưu localStorage được báo, vẫn giữ thao tác trong phiên.

Để chuyển giao trực tiếp đúng quy trình sản phẩm cần backend có xác thực, lưu lịch sử cảnh báo, API phân công và kênh tiếp nhận của đơn vị. Frontend hiện không chạy mô hình AI, không điều khiển ESP32, không tự dự báo thời tiết, không tự tổng hợp số liệu camera thành chỉ số tuyến. Backend chịu trách nhiệm các phần này.

## Quy tắc cảnh báo

Tài liệu chưa chốt các ngưỡng định lượng. Các ngưỡng **đề xuất để thử nghiệm**, không phải kết luận của báo cáo, nằm ở `src/config/monitoring.ts`:

- Mật độ rác ≥70%; hoặc mức che miệng cống ≥70%.
- Có `rain_expected: true` từ backend.
- `flood_risk` từ cao trở lên; hoặc `severity` tuyến khác `normal`.

Mức ưu tiên hiển thị lấy mức cao nhất giữa severity tuyến, flood_risk và mức tối thiểu `medium` khi có điều kiện bất lợi bổ sung. Chỉ dùng flood_risk do máy chủ cung cấp, không suy ra ngập thực tế từ lượng rác. Bản đồ/danh sách/queue dùng cùng mức ưu tiên; mục “Nguy cơ ngập” trong chi tiết hiển thị giá trị gốc. Cấu hình màu/nhãn ở `src/config/severity.ts`.

Chỉ số thiếu hiển thị **Chưa có**, không thay bằng 0 hoặc an toàn. Thời điểm nhận HTTP và thời điểm quan sát được hiển thị riêng; số liệu cũ vẫn giữ timestamp thực của nó. Polling mỗi 30 giây khi tab hiện, timeout request 10 giây, hủy request khi rời nguồn; chưa có WebSocket/SSE hay push khi đóng trang. Ngưỡng nghiệp vụ và hạn sử dụng dữ liệu cần được nhóm vận hành hiệu chỉnh trước triển khai.

## API và mẫu dữ liệu

| Endpoint | File dữ liệu | Response |
|---|---|---|
| GET `/api/health` | trạng thái server | `{"status":"ok"}` |
| GET `/api/cameras` | `server/data/cameras.json` | `{"cameras":[...],"fetched_at":"..."}` |
| GET `/api/road-alerts` | `server/data/road-alerts.json` | `{"roads":[...],"fetched_at":"..."}` |

Server đọc và validate file mỗi request. Dữ liệu JSON hiện có được giữ nguyên. Schema cũ vẫn dùng được; các trường bổ sung đều tùy chọn.

Tuyến đường:

```json
{
  "roads": [{
    "road_id": "SSC-R001",
    "alert_id": "SSC-INCIDENT-001",
    "road_name": "Tuyến thử nghiệm",
    "severity": "high",
    "description": "Thu gom rác và kiểm tra cửa cống trước mưa.",
    "updated_at": "2026-09-09T17:00:00+07:00",
    "geometry": {
      "type": "LineString",
      "coordinates": [[106.7112,10.7874],[106.7132,10.7886],[106.7162,10.7901]]
    },
    "monitoring": {
      "waste_coverage_pct": 86,
      "drain_blockage_pct": 82,
      "flood_risk": "high",
      "rain_expected": true,
      "observed_at": "2026-09-09T17:00:00+07:00"
    }
  }]
}
```

Camera:

```json
{
  "cameras": [{
    "camera_id": "SSC-C001",
    "road_id": "SSC-R001",
    "name": "Camera cửa cống 01",
    "status": "online",
    "geometry": {"type":"Point","coordinates":[106.7132,10.7886]},
    "monitoring": {
      "waste_coverage_pct": 86,
      "drain_blockage_pct": 82,
      "observed_at": "2026-09-09T17:00:00+07:00"
    },
    "images": {
      "original_url": "https://example.com/ssc/camera-original.jpg",
      "analyzed_url": "https://example.com/ssc/camera-analyzed.jpg",
      "captured_at": "2026-09-09T17:00:00+07:00"
    }
  }]
}
```

Các tọa độ và URL trên chỉ minh họa. Bản mẫu có tại `server/examples/monitoring-roads.json` và `monitoring-cameras.json`; thay URL `example.com` bằng ảnh truy cập được. Đường dẫn ảnh phải là HTTP(S) hoặc đường dẫn cùng origin bắt đầu `/`; ví dụ đặt ảnh trong `public/images/` để thử bằng `/images/original.jpg`. Backend phục vụ JPEG upload qua `/api/images/<uuid>.jpg`; các ảnh phân tích bên ngoài dùng URL truy cập được do worker cung cấp. Ở bản triển khai HTTPS, ảnh cũng cần HTTPS. Máy chủ ảnh cần cho phép truy cập từ trình duyệt, hoặc URL có thời hạn phù hợp; không đưa khóa bí mật vào biến VITE.

Quy ước:

- Backend yêu cầu ID chuỗi không rỗng, không trùng trong từng tập dữ liệu. Mỗi road_id biểu diễn một đoạn; chia đoạn có ID riêng nếu mức độ khác nhau.
- `alert_id`: định danh **đợt sự cố**, giữ ổn định khi polling, thay khi phát sinh sự cố mới. Nếu thiếu, frontend dùng ID tuyến + mức/nhóm điều kiện, nên không phân biệt được hai sự cố cùng điều kiện để đặt lại trạng thái đã xem.
- `severity`, `flood_risk`: `normal | low | medium | high | critical`.
- Phần trăm: số hữu hạn 0–100. `rain_expected`: boolean, không phải chuỗi; `false` nghĩa là nguồn chưa báo mưa, không khẳng định trời sẽ không mưa.
- `observed_at`, `captured_at`, `updated_at`: timestamp hợp lệ, nên dùng ISO 8601 với múi giờ.
- Camera `status`: `online | offline | unknown`; trạng thái do backend cung cấp. Camera không có road_id vẫn hiện trên bản đồ, nhưng không thuộc danh sách một tuyến.
- WGS84/EPSG:4326, GeoJSON `[longitude, latitude]`; backend dùng 2D, LineString cần ít nhất hai điểm khác nhau. Frontend chuyển sang `[latitude, longitude]` đúng một lần. Không tự bám đường.
- Adapter frontend còn hỗ trợ array, `{data: [...]}` và GeoJSON FeatureCollection; monitoring nằm trong properties đối với Feature. Backend dùng envelope chuẩn như ví dụ.

## Công cụ lấy tọa độ hiện có

Mở “Lấy tọa độ để thử nghiệm”, chọn camera hoặc đoạn đường. Phóng to và bấm điểm; tuyến cần các điểm liên tiếp dọc đường, thêm tại khúc cua. Có bỏ điểm cuối, xóa bản nháp và sao chép JSON. Đóng hoặc đổi chế độ xóa bản nháp. Thêm phần tử vào file tương ứng trong `server/data/`, giữ các phần tử đã có rồi cập nhật dữ liệu. Bấm trên bản đồ chỉ có độ chính xác gần đúng; cần GPS/khảo sát hoặc dữ liệu GIS cho vị trí chính thức.

## Cấu trúc mở rộng

```text
src/
  App.tsx                         Ghép giao diện, chọn nguồn, bộ lọc / selection
  models/                         Camera, RoadAlert, Monitoring, CameraImages
  config/monitoring.ts             Ngưỡng nghiệp vụ đề xuất và chu kỳ polling
  config/severity.ts               Nhãn / màu mức độ
  config/basemaps.ts               Nguồn nền / attribution
  services/normalizeMonitoring.ts  Validate chỉ số, timestamp, URL ảnh
  services/normalizeAlerts.ts      Adapter road / GeoJSON
  services/mapService.ts           Fetch + timeout + camera adapter
  services/monitoringService.ts    Tạo cảnh báo, ưu tiên, phiếu xử lý
  hooks/useMapData.ts              Poll dữ liệu / hủy request / giữ dữ liệu cũ
  hooks/useAlertHandling.ts        Thông báo và trạng thái localStorage
  mocks/monitoring.ts              Mô phỏng tách biệt dữ liệu API
  components/map/                  Map, polyline, marker, lấy tọa độ, nền
  components/monitoring/           Metrics, ảnh, queue, phiếu, công cụ tọa độ
server/
  app.js, index.js                 HTTP API đọc/ghi, ESP32 và AI
  service.js, store.js             Nghiệp vụ và lưu JSON tuần tự / atomic
  aggregation.js, config.js        Tổng hợp chỉ số và ngưỡng đánh giá
  ai-worker.js, seed-demo.js       Runner nối model và lệnh thử API
  validation.js                   Validate schema cũ và schema mở rộng
  data/                           Dữ liệu thực (không tự thêm demo)
  examples/                       JSON minh họa tích hợp
tests/                            Contract, logic cảnh báo và HTTP backend
```

## Kiểm tra và triển khai

```powershell
npm test
npm run build
```

Các bài kiểm tra bao gồm API đọc file thật, schema cũ/mới, phần trăm/URL lỗi, thứ tự kinh/vĩ độ, ngưỡng cảnh báo, chống lặp theo timestamp, mức ưu tiên và phiếu minh bạch trạng thái. Thử trên UI: đổi nguồn demo, chọn tuyến/camera, tắt lớp, tìm tuyến, xác nhận, điền đơn vị và xuất phiếu; đổi lại máy chủ để không dùng demo trong vận hành.

`dist` chỉ có frontend. `npm run preview` không tự chạy backend/proxy production. Khi triển khai cần Node API và reverse proxy `/api`, hoặc đặt `VITE_CAMERAS_API_URL`/`VITE_ROADS_API_URL` thành API HTTPS và CORS đúng origin. Server mặc định bind `127.0.0.1:8010` (bản v2; HTTPS 8453 nếu có `server/certs/`); biến môi trường tiến trình `PORT`, `HOST`, `FRONTEND_ORIGIN` được hỗ trợ, không tự đọc `.env`. Mặc định CORS `http://localhost:5173`. Giữ giới hạn truy cập dữ liệu camera phù hợp khi đưa lên mạng.

Nguồn nền và font cần Internet. Giữ attribution và tuân thủ [chính sách OSM](https://operations.osmfoundation.org/policies/tiles/) / [OpenMaps](https://openmaps.fr/tile-usage-policy.html). Nguồn dự phòng hiện có không đảm bảo khả dụng trên mọi mạng; nếu tile lỗi, các đối tượng cảnh báo vẫn vẽ và giao diện cho phép đổi nguồn. Không tải hàng loạt tile offline.
