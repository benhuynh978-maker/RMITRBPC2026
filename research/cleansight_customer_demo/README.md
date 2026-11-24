# Bộ dữ liệu demo "bản đồ rác của một khách hàng đã lắp xong"

Dữ liệu cho trang **/ban-do** của website (`cleansight-site-v2`): 100 camera ở 6 khu, mở lên là xem trạng thái cống, mức rác và vùng rác (m²) trên bản đồ, như khách hàng sau khi lắp đặt và hiệu chỉnh xong.

> **Toàn bộ là dữ liệu MÔ PHỎNG.** Vị trí camera, số đo, vùng rác đều do script sinh ra; không phải đo thực tế, không phải khách hàng thật. Trang web ghi rõ điều đó ở nhiều chỗ và từ chối hiển thị tệp dữ liệu không có cờ `simulated: true`.

## Cái gì "thật", cái gì giả

| | |
|---|---|
| **Luật của sản phẩm (dùng nguyên văn)** | Trạng thái cống = trung vị 5 lần đo gần nhất trong 15 phút, cần ≥ 3 lần, ngưỡng có trễ (vào Theo dõi 20, Cần dọn 50; ra 12 và 35). Các mức rác (1/5/10/20 %) và mức che cống (20/50/70/90 %). Hàm tính vùng camera nhìn thấy trên mặt đất là `project_mask.ground_footprint_polygon` của lõi vẽ rác lên bản đồ. |
| **Kiểm chứng** | `test_demo_data.py` chạy **mã Node thật** của backend (`ssc-v2/ssc-road-alerts/server/aggregation.js`, chỉ đọc) trên 60 chuỗi đo ngẫu nhiên và so với bản Python từng bước (trạng thái, lý do, số lần đo, mốc `since`, giá trị trung vị); so ngưỡng với `config.js`. |
| **Giả lập** | 100 camera và vị trí; mức rác tích tụ, hai trận mưa, đội dọn buổi sáng; nhiễu đo và khung lệch; camera mất kết nối, camera mới lắp; hình dạng vùng rác (đa giác sinh ngẫu nhiên có diện tích đúng). |

Không có trong demo (và trang nói rõ): cảnh báo theo tuyến đường, mưa, lịch sử dài (backend thật chỉ giữ ~100 lần đo gần nhất mỗi camera), các giới hạn thực tế (ban ngày, camera cố định, mặt đất phẳng, model còn bỏ sót rác).

## Tệp

| Tệp | Việc |
|---|---|
| `pick_sites.py` | Chọn vị trí camera. **Chạy một lần, cần mạng.** Tải ~300 ô bản đồ OpenStreetMap France (zoom 18; ≤ 600 ô, ≤ 1,6 yêu cầu/giây, có User-Agent mô tả), dò mặt đường bằng màu của kiểu bản đồ (đường vàng/cam/hồng đỏ), đặt miệng cống sát mép đường thẳng, camera trên vỉa hè cách 3–4,4 m nhìn vào miệng cống; loại điểm rơi xuống nước và điểm sát đường khác. |
| `camera_sites.json` | Kết quả của `pick_sites.py` (có trong repo để bước sau chạy offline). |
| `make_demo_data.py` | Sinh `cleansight-site-v2/public/demo-data/city.json` (có hạt giống, chạy lại ra đúng từng byte). |
| `check_policy.mjs` | Chạy luật thật của backend để test so sánh. |
| `test_demo_data.py` | Kiểm thử. |

## Chạy

```bash
python pick_sites.py                  # (một lần, cần mạng) -> camera_sites.json
python make_demo_data.py              # -> ../../cleansight-site-v2/public/demo-data/city.json
python -B test_demo_data.py           # kiểm thử (cần Node để so với backend thật)
```

## Vì sao đặt camera bằng ô bản đồ

Dữ liệu đường của OpenStreetMap qua Overpass bị chặn ở môi trường làm việc, nên không lấy được hình học đường trực tiếp. Dò từ màu ô bản đồ cho cùng kết quả cần thiết: camera nằm ở lề một đoạn đường thật. Dữ liệu bản đồ © OpenStreetMap contributors (ODbL), hiển thị bằng ô của OpenStreetMap France (trang web đã ghi nguồn). Vị trí camera vẫn là **giả định**.

Giới hạn: màu của kiểu bản đồ có thể thay đổi; chữ tên đường làm mặt nạ đường bị khuyết nên có thể lệch vài chục cm; `pick_sites.py` chỉ nhận đoạn đường thẳng, không có đoạn rẽ/ngã tư. Muốn vị trí chính xác từng mét cần dữ liệu đường thật.
