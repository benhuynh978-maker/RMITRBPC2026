# Dữ liệu demo "khách hàng đã lắp đặt xong" (thành phố mô phỏng, 100 camera)

Để cho người xem (giám khảo, khách hàng) thấy **dashboard thật của hệ thống** hiển thị như khi một khách hàng đã lắp camera, hiệu chỉnh xong và chỉ việc mở lên xem: nhiều camera ở nhiều nơi, tuyến đường tô theo mức cảnh báo, trạng thái cống, vùng rác (m²) vẽ trên bản đồ.

> **Toàn bộ là dữ liệu MÔ PHỎNG.** Vị trí camera, số đo, vùng rác do script sinh ra; không phải đo thực tế, không phải khách hàng thật. Dashboard ghi rõ (banner SIMULATION, "Figures come from a simulated API", mô tả tuyến có "[Simulated data via the test API]").

## Hai đầu ra (cùng một bộ mô phỏng)

| Đầu ra | Dùng cho | Lệnh |
|---|---|---|
| `ssc-v2/ssc-road-alerts/src/mocks/city.json` | **Dashboard thật (ssc-v2), chế độ "Demo simulation"** | `python make_dashboard_data.py` |
| `cleansight-site-v2/public/demo-data/city.json` | Trang `/ban-do` trên website (làm trước đó, đang giữ tạm, sẽ gỡ khi bản dashboard xong) | `python make_demo_data.py` |

## Cái gì "thật", cái gì giả

| | |
|---|---|
| **Mã thật của hệ thống (dùng nguyên văn)** | Dữ liệu dashboard được tạo bằng **chính mã backend ssc-v2** (chỉ đọc): `computeDrainState` (trung vị 5 lần đo trong 15 phút, ≥ 3 lần, ngưỡng có trễ), `publicCamera`, `aggregateRoad` (gộp theo tuyến, mức cảnh báo, `drain_summary`), `validateDataset`; mức rác/mức che cống theo `config.js`. Đầu ra đúng dạng `/api/cameras` và `/api/road-alerts`, rồi đi qua các hàm chuẩn hoá của dashboard. Hình học vùng camera nhìn thấy dùng `project_mask.ground_footprint_polygon` của lõi vẽ rác lên bản đồ. |
| **Kiểm chứng** | `test_demo_data.py` (36 kiểm tra) so từng bước luật trạng thái cống Python với mã Node thật trên 60 chuỗi ngẫu nhiên (15.000 bước, 0 lệch), so ngưỡng với `config.js`, và so trạng thái của cả 100 camera trong đầu ra dashboard với bộ mô phỏng. Bên dashboard: `npm test` trong `ssc-v2/ssc-road-alerts` (có thêm `tests/trash-regions.test.tsx`). |
| **Giả lập** | 100 camera và vị trí; mức rác tích tụ, hai trận mưa (khung bị loại), đội dọn buổi sáng; nhiễu đo và khung lệch; camera mất kết nối (5), mới lắp (3); hình dạng vùng rác (đa giác sinh ngẫu nhiên có diện tích m² đúng, nằm trong vùng camera thấy, khớp mức che cống). Tên tuyến/camera giả định. |

Không có trong demo: ảnh camera (không có ảnh), mưa/thời tiết (chế độ demo không gọi), lịch sử dài (backend thật chỉ giữ ~100 lần đo gần nhất mỗi camera). **Vùng rác (`trash_regions`) là trường tùy chọn MỚI chỉ giao diện**: backend và AI worker chưa nhận/gửi nó.

## Tệp

| Tệp | Việc |
|---|---|
| `pick_sites.py` | Chọn vị trí camera. **Chạy một lần, cần mạng.** Tải ~300 ô bản đồ OpenStreetMap France (zoom 18, ≤ 600 ô mỗi lần chạy, ≤ 1,6 yêu cầu/giây, có User-Agent mô tả, thử lại khi mạng ngắt), dò mặt đường bằng màu ô bản đồ, đặt miệng cống sát mép đường thẳng, camera trên vỉa hè cách 3–4,4 m nhìn vào miệng cống; loại điểm rơi xuống nước hay sát đường khác. |
| `camera_sites.json` | Kết quả của `pick_sites.py` (có trong repo để các bước sau chạy offline). |
| `make_demo_data.py` | Bộ mô phỏng (có hạt giống, chạy lại ra đúng từng byte) và dữ liệu cho trang website. |
| `make_dashboard_data.py` | Gom camera gần nhau thành tuyến (3–5 camera, tối đa ~2 km), rồi gọi `build_dashboard_state.mjs`. |
| `build_dashboard_state.mjs` | Chạy mã backend thật để ra đúng dữ liệu API cho dashboard. |
| `check_policy.mjs`, `test_demo_data.py` | Kiểm thử. |
| `open_dashboard_demo.ps1`, `close_dashboard_demo.ps1` | Phục vụ dashboard demo từ laptop (build mở sẵn ở "Demo simulation", máy chủ tĩnh 127.0.0.1:5175, Tailscale Funnel cổng 10000; không đụng 443/8443/8444). **Chưa chạy thử trên Windows.** |

## Chạy

```bash
python pick_sites.py                  # (một lần, cần mạng) -> camera_sites.json
python make_dashboard_data.py         # -> ../../ssc-v2/ssc-road-alerts/src/mocks/city.json
python make_demo_data.py              # -> ../../cleansight-site-v2/public/demo-data/city.json
python -B test_demo_data.py           # kiểm thử (cần Node)
```

Xem thử dashboard: `cd ../../ssc-v2/ssc-road-alerts && VITE_DEFAULT_SOURCE=demo npm run build`, rồi phục vụ thư mục `dist` bằng máy chủ tĩnh bất kỳ (hoặc `npm run dev` rồi chọn "Demo simulation" ở ô Data source).

## Giới hạn cần biết

- **Tuyến không bám theo phố.** Mỗi tuyến là đường nối các camera gần nhau (hệ thống thật vẽ tuyến theo hình học phố), nên đường vẽ có thể cắt ngang nhà. Camera lẻ lập một tuyến ngắn dọc trục đường đã dò.
- **Vị trí camera giả định**, đặt sát lề một đoạn đường thẳng thật dò từ màu ô bản đồ (dữ liệu bản đồ © OpenStreetMap contributors, ODbL). Dữ liệu đường qua Overpass bị chặn ở môi trường làm việc nên không dùng được; màu kiểu bản đồ có thể đổi, chữ tên đường làm mặt nạ đường khuyết nên có thể lệch vài chục cm. Cần vị trí chính xác từng mét thì phải dùng dữ liệu đường thật.
- **Giao diện thật khi có 100 camera:** biểu tượng camera chồng nhau ở mức thu nhỏ (dashboard chưa có gom cụm); vùng rác chỉ vài điểm ảnh khi thu nhỏ, phải phóng đến mức 20–21 để thấy (bản đồ nền được phóng to từ ô gốc nên mờ).
- Nhiều tuyến ở mức "Low" vì luật thật coi mọi tuyến khác "normal" là cần chú ý.
- Mốc thời gian cố định (23/11/2026 14:30, UTC+7), không phải giờ hiện tại.
