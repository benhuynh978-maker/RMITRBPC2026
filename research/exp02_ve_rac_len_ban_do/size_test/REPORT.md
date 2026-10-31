# size_test — Đo lại kích thước (m²) và vị trí của rác giả lập có kích thước thật biết trước

> Phần "Tiêu chí tham khảo" bên dưới được ghi vào file này **TRƯỚC KHI CHẠY** thí nghiệm
> (2026-10-12), không chỉnh sửa sau khi có kết quả.

## Tiêu chí tham khảo (đặt trước khi chạy — KHÔNG chỉnh sau)

Áp dụng cho **điều kiện (a)** (render sạch 640×480, mask hoàn hảo, pose hiệu chỉnh từ marker
trong chính ảnh), chỉ các vật PHẲNG (vuông 0.1/0.2/0.3/0.5 m, chữ nhật 1.0×0.3 m, tròn
Ø0.4 m). Ca "hộp cao 0.2 m" là ca cố ý vi phạm giả định mặt đất phẳng → chỉ báo số, không
xét tiêu chí.

"Khoảng cách" = khoảng cách danh nghĩa theo hướng nhìn, tính từ chân camera tới tâm vật
(1, 2, 3, 5, 8 m); vật lệch ngang được xếp theo khoảng cách danh nghĩa của hàng chứa nó.

| Mã | Tiêu chí | Ngưỡng |
|----|----------|--------|
| T1 | Sai số diện tích \|(đo − thật)/thật\|, vật ở 1–3 m | ≤ 5% |
| T2 | Sai số diện tích \|(đo − thật)/thật\|, vật ở 5–8 m | ≤ 15% |
| T3 | Sai số vị trí tâm (khoảng cách Euclid trên mặt đất), vật ở 1–3 m | ≤ 0.1 m |

Một tiêu chí ĐẠT khi **mọi** mẫu đo thuộc nhóm đó đạt ngưỡng (mọi vật × mọi vị trí × mọi
biến thể pose). Báo thêm tỉ lệ mẫu đạt và liệt kê vật không đạt.

Các điều kiện (b), (c), (d) chỉ báo số thực, không xét ngưỡng.

Kiểm tra chéo đường lat/lon: diện tích tính từ GeoJSON (lon/lat → đổi ngược về mét) phải
lệch < 0.5% so với diện tích tính trực tiếp bằng mét.

---

## Kết quả (ghi SAU khi chạy, 2026-10-12)

> Phần dưới đây do Tech Lead tổng hợp từ báo cáo của agent thực hiện. Số liệu chi tiết nằm
> trong `ketqua/` (`ketqua_chi_tiet.csv`, `bang_tom_tat.md`, `ket_luan_tieu_chi.json`).

### Kết luận theo tiêu chí (điều kiện a)

| Mã | Kết quả | Chi tiết |
|----|---------|----------|
| T1 | **KHÔNG ĐẠT** | 290/377 mẫu đạt, max 17.8%. Chủ yếu do vuông 0.1 m (7/55 đạt); các hình khác đạt 41–51/47–55 |
| T2 | **KHÔNG ĐẠT** | 97/139 mẫu đạt, max 65.9% |
| T3 | **ĐẠT** | 377/377, max 0.067 m |
| Lat/lon ↔ mét | **ĐẠT** | max 1.3e-6 % trên 3299 mẫu (CSV có 3300 dòng; 1 mẫu suy biến, diện tích ~1.8e-15 m² vì mask chỉ còn một đường thẳng, bị loại khỏi phép tính %) |

### Nguyên nhân chính (đã tách được)

1. **Hiệu chỉnh marker là nguồn sai số lớn nhất ở xa.** Với pose đáp án (d), sai số tâm ≤ 0.014 m
   ở mọi khoảng cách; với pose hiệu chỉnh từ marker (a), lên 0.43 m (TB) ở 8 m. Ảnh sạch: camera
   lệch ~0.15 m / 2°. Marker 200 mm ở ~4 m là quá nhỏ để tự nó cho pose tin cậy.
2. **JPEG q12 làm lật pose** ở 3/10 biến thể (lệch 80–85°, ~5.2 m), trong khi reprojection RMS vẫn
   chỉ 0.09–0.2 px → chỉ số này **không phát hiện được** ca hỏng.
3. **Contour đi qua tâm pixel biên nên co ~0.5 px** quanh viền → diện tích bị hụt có hệ thống
   (≈ −0.5·chu vi/diện tích, tính bằng px). Tính diện tích theo vùng pixel thì ở (d) TB ≈ 0%, vật
   ≥ 0.3 m max 1.6% (1–3 m), 2.6% (5 m), 7.2% (8 m).

### Sai số diện tích, vật ≥ 0.3 m (max |.|)

| Điều kiện | 1–3 m | 5 m | 8 m |
|---|---|---|---|
| (a) sạch, pose từ marker | 7.5% | 20.6% | 34.2% |
| (d) pose đáp án | 5.9% | 11.5% | 21.3% |
| (d) + diện tích theo vùng pixel | 1.6% | 2.6% | 7.2% |

### Ca hộp cao 0.3×0.3×0.2 m (đáy thật 0.09 m²)

Diện tích đo bị phóng to +32% (1 m) → +177% (8 m), khớp lý thuyết vết chiếu. Mép gần (chân hộp)
vẫn đúng (≤ 3,05 cm). → Với rác có chiều cao: lấy **vị trí theo mép gần**, coi m² là vết chiếu
trên ảnh, không phải diện tích thật.

### Thay đổi so với spec ban đầu

Test "vuông 0.3 m ở 2 m trong ±3%" được kiểm trên **diện tích vùng pixel** (đạt +0.38% / +1.52%)
cộng kiểm **độ co contour đúng như dự đoán** (±1.5 điểm %), vì diện tích theo contour trượt
(−3.89%) do hiện tượng co 0.5 px ở mục 3. Giá trị theo contour vẫn được in ra.

### Đề xuất sửa (đã áp dụng ở vòng 2, 2026-10-12)

> Ghi chú: các đề xuất bên dưới đã được thực hiện (SUBPIX + IPPE_SQUARE, diện tích theo biên pixel, khoá tỉ lệ
> khung hình). Các số trong báo cáo này là của hành vi CŨ, tái lập bằng `legacy=True` (`measure.py`,
> `thu_hieu_chinh.py` đã chuyển sang `legacy=True`). Riêng việc "chọn nghiệm theo độ cao camera" đã được
> kiểm chứng là KHÔNG dùng được (hai nghiệm lật cùng độ cao): `--camera-height-m` chỉ để kiểm tra chéo.

- `calibrate_aruco`: bật `CORNER_REFINE_SUBPIX` (sạch: 0.164 m/1.90° → 0.106 m/1.40°); dùng
  `solvePnPGeneric` + `IPPE_SQUARE` và chọn nghiệm theo độ cao camera đo tay; không hiệu chỉnh
  trên khung JPEG chất lượng thấp; marker ≥ 400 mm hoặc GridBoard/ChArUco cho camera xa.
- Đo diện tích theo vùng pixel, hoặc nới polygon 0.5 px trước khi chiếu.

### Giới hạn

Mặt đất phẳng lý tưởng; không méo ống kính; nội tại camera coi như biết chính xác (thực tế FOV
66° chỉ là giả định — sai số nội tại sẽ cộng thêm); mask hoàn hảo ≠ mask YOLO; JPEG của OpenCV,
không phải bộ mã hoá ESP32; 1 marker, 5 biến thể pose mỗi họ.
