# API AI đơn giản và dự báo mưa 12 giờ

## AI gửi báo cáo trực tiếp

`POST http://localhost:8000/api/ai/reports`

Headers:

```http
Content-Type: application/json
X-API-Key: <AI_API_KEY nếu đã cấu hình>
```

Chạy localhost chưa đặt khóa thì bỏ X-API-Key. Body bốn trường:

```json
{
  "waste_level": "high",
  "flood_percentage": 65,
  "image_url": "https://example.com/anh-ket-qua-ai.jpg",
  "camera_id": "CAM-001"
}
```

- `waste_level`: `normal`, `low`, `medium`, `high`, `critical`. Đây là mức phân loại rác, không phải phần trăm rác. Không tự biến `high` thành một tỷ lệ phần trăm giả.
- `flood_percentage`: số 0–100 do AI báo cáo. Lưu riêng, không gán vào tỷ lệ che cống. Đây không phải xác suất mưa từ dịch vụ thời tiết; nhóm AI cần chốt định nghĩa tỷ lệ ngập (ví dụ phần trăm vùng quan tâm bị ngập) và giữ nhất quán khi huấn luyện/gửi dữ liệu.
- `image_url`: URL HTTP(S) hoặc đường dẫn cùng origin `/...` đến ảnh kết quả AI. Frontend hiện ở mục ảnh phân tích, không giả định đó là ảnh gốc. Server không tự tải URL. Không gửi bytes hoặc base64 trong trường này.
- `camera_id`: mã camera đã tạo và gắn `road_id`; backend lấy tuyến và vị trí từ dữ liệu đã lưu.

Không cần tạo job ESP32 trước khi dùng endpoint này. Server tạo quan sát `processed`, lưu vào cameras.json và tổng hợp tuyến khi GET. Bốn trường không có độ tin cậy: backend không tự thêm confidence giả; chỉ dùng cho nguồn AI đã được xác thực. Luồng cũ `/api/ai/results` vẫn có confidence và yêu cầu job pending, không thay đổi.

Tùy chọn thêm `observation_id` và `captured_at` ISO 8601 có múi giờ. Nếu thiếu, server tự cấp ID và dùng thời điểm nhận. Khi retry, gửi cùng observation_id và nội dung để tránh tạo bản ghi mới; cùng ID nhưng nội dung khác trả 409. Ảnh cũ hơn phân tích đang dùng hoặc quá 15 phút không áp vào hiện trạng, trả `applied:false`. Mỗi phản hồi cần kiểm tra `observation.applied`, không chỉ HTTP 200.

Mức ưu tiên demo lấy mức cao hơn giữa waste_level và phân loại flood_percentage theo ngưỡng server hiện có (20/50/70/90). Trên tuyến lấy mức cao nhất trong các camera còn dữ liệu mới. Đây là quy tắc thử nghiệm, không phải mô hình dự báo thủy văn. UI hiển thị riêng “Mức độ rác (AI)” và “Tỷ lệ ngập (AI)”.

## Ghim tọa độ có cần tra địa chỉ không?

Không. Kinh độ/vĩ độ chính là vị trí. Lưu Point `[longitude, latitude]` của camera một lần rồi gửi trực tiếp cho API dự báo. Dịch vụ thời tiết tự chọn điểm/lưới mô hình phù hợp. Reverse geocoding chỉ cần khi muốn hiện tên phường/đường; không cần để lấy thời tiết và không làm tọa độ chính xác hơn.

Công cụ lấy tọa độ trong project vẫn tạo bản nháp. Bạn cần tạo/sửa camera qua API hoặc lưu JSON trước khi dùng vị trí đó để dự báo. Thay vị trí camera → lần tải lại dùng tọa độ mới. Không dự báo từ các điểm đang bấm dở trong bản nháp.

## API thời tiết và checkbox

`GET http://localhost:8000/api/weather/cameras` — không có body.

Backend đọc tất cả camera đã lưu, gọi Open-Meteo bằng latitude/longitude, trả `cameras[]` gồm: camera_id, road_id, coordinates, status, fetched_at, window_start/window_end, will_rain, first_rain_at, max_probability và hourly. Có `rain_mm_per_hour` gồm rain + showers. Dữ liệu forecast được cache trong RAM, không thêm database hoặc ghi vào hai file dữ liệu chính.

Frontend tự tải trước dự báo ở nguồn **Máy chủ**, cập nhật mỗi 5 phút khi tab hiện, khi quay lại tab và khi tọa độ camera thay đổi. Tick **Hiện khu vực sắp mưa — 12 giờ tới** chỉ bật/tắt lớp bản đồ và bảng chi tiết; không cần gọi lại provider mỗi lần tick. Nguồn mô phỏng tĩnh không dùng thời tiết thật.

- Dấu hiệu mưa đề xuất: xác suất giáng thủy theo giờ ≥50% **hoặc** rain + showers ≥0.2 mm/giờ. Sửa tại `server/weather.js` → WEATHER_POLICY.
- Vòng xanh bán kính 500 m chỉ giúp nhận ra vị trí camera cần chú ý. **Không phải ranh giới vùng mưa, radar, hoặc độ phân giải của mô hình.** Camera không quan trắc mưa trực tiếp.
- Thời gian trả ISO UTC; UI đổi theo múi giờ thiết bị. Cửa sổ tính từ lúc request đến đúng 12 giờ sau. Vì dữ liệu nguồn là từng giờ, có thể có 13 khoảng giao nhau khi request ở giữa giờ; lượng mưa/xác suất vẫn của cả giờ nguồn, không nội suy thành số đo theo phút.
- Forecast fresh/partial có dấu hiệu mưa được ghép vào tín hiệu mưa hiển thị của tuyến và queue frontend; không ghi đè dữ liệu manual weather trong JSON. Bỏ tick chỉ ẩn lớp, không tắt đánh giá cảnh báo. Dự báo này chưa ghi vào GET road-alerts, nên các client khác muốn dùng phải đọc weather endpoint và ghép theo road_id.
- Không có đủ mẫu: `will_rain:null`, không coi là không mưa. Khi lỗi provider, giữ cache với nhãn `stale` nếu còn khung giờ phù hợp; không dùng cache stale để phát cảnh báo vận hành mới. Khi không có cache, hiện `unavailable`.

Cache 15 phút cho mỗi cặp tọa độ trùng nhau, dùng chung giữa request đồng thời. Lỗi chờ tối thiểu 1 phút trước khi retry. Giới hạn 4 request provider đồng thời, tối đa 100 tọa độ khác nhau trong một lượt; camera vượt giới hạn có trạng thái unavailable rõ ràng. Mỗi request provider timeout 8 giây. Với nhiều điểm, lần tải đầu có thể mất thời gian. Nên gom theo khu vực/lưới và dùng gói phù hợp nếu mở rộng.

Nguồn chính thức: [Open-Meteo Forecast API](https://open-meteo.com/en/docs), [điều khoản](https://open-meteo.com/en/terms). Gói miễn phí dành cho phi thương mại, có giới hạn tần suất; giữ attribution Open-Meteo/CC BY 4.0. Tọa độ camera được gửi từ backend đến Open-Meteo để lấy dự báo. Không có tên camera, ID hay ảnh được gửi cho nhà cung cấp thời tiết.

## Thử nghiệm

1. Chạy backend và frontend, tạo tuyến rồi camera qua các API cũ. Hai file dữ liệu rỗng đã được chuẩn hóa thành mảng JSON rỗng; không tự chèn điểm giả.
2. Gửi POST ai/reports với camera_id thực của bạn; thay URL ảnh ví dụ bằng ảnh truy cập được.
3. Trên frontend chọn Máy chủ, Cập nhật dữ liệu rồi chọn camera để xem chỉ số AI.
4. Tick lớp mưa; mở hàng camera trong bảng để xem các giờ. Nếu không có mưa dự báo thì không có vòng xanh; nếu chưa lưu camera thì không có vị trí để truy vấn.

Các bài kiểm tra mới: báo cáo bốn trường/định dạng sai/idempotency/kết quả cũ, tọa độ lat/lon, cache và request đồng thời, dự báo qua nửa đêm, phần dữ liệu thiếu, mất kết nối và không đưa cache stale vào cảnh báo. Live check provider dùng tọa độ minh họa riêng, không tạo camera trong dữ liệu người dùng.
