# Stress test nhận diện bảng ArUco trên ảnh xấu kiểu ESP32 (exp02 / stress_test)

> Phần 1–2 (thiết lập + tiêu chí) được viết và chốt **TRƯỚC KHI CHẠY** thí nghiệm.
> Không chỉnh tiêu chí sau khi xem kết quả.

## 1. Thiết lập thí nghiệm

- Camera: `camera_model.build_camera_matrix(640, 480, config.DIAGONAL_FOV_DEG=66°)` → f ≈ 615,9 px,
  cx=320, cy=240, không méo ống kính (đúng giả định của exp02).
- Marker: `DICT_4X4_50`, id=0, cạnh mã 200 mm (`config.MARKER_SIZE_MM`), có viền trắng (quiet zone)
  = 1 module (= S/6, khớp tỉ lệ `generate_marker.py`: mã 600 px + lề 100 px).
- Bộ dựng cảnh riêng (`stress_test/scene.py`), không gọi `make_synthetic_test.main()`:
  - Marker nằm trên mặt phẳng z=0 (hệ marker), mặt phẳng có caro tương phản thấp kiểu nền đường.
  - Giấy trắng mức xám 220, mực đen 35 (không dùng 0/255 lý tưởng — giả lập ánh sáng ban ngày thật).
  - Render siêu lấy mẫu ×4 (2560×1920) rồi thu nhỏ INTER_AREA về 640×480 để giả lập điểm ảnh tích
    phân ánh sáng (tránh răng cưa phi vật lý của warpPerspective trực tiếp).
  - Pose ĐÁP ÁN: camera đặt tại khoảng cách D (m) theo hướng lệch góc θ so với pháp tuyến marker,
    phương vị φ; nhìn về marker, sau đó xoay nhẹ camera để marker lệch khỏi tâm ảnh một đoạn (du, dv).
- Dò + giải pose: gọi trực tiếp `calibrate_aruco.detect_and_solve_pnp(path, 0, 200)` (ảnh JPEG tạm
  ghi vào `stress_test/tmp/`, xoá ngay sau khi đọc). Không gọi `save_calibration`/`main`.

### Lưới điều kiện
- Khoảng cách camera→tâm marker D: 1, 2, 3, 5, 8, 12 m.
- Góc nhìn nghiêng so với pháp tuyến marker θ: 20°, 45°, 65°.
- JPEG (thang OpenCV): 95, 50, 30, 25, 20, 15, 12, 8. **q20–30 = "gần ESP32 thật"** (theo exp01:
  firmware `jpeg_quality=12` thang esp32 ≈ OpenCV q20–30, ảnh ~12–15 KB). q12/q8 khắc nghiệt hơn thực tế.
- Nhiễu phụ ở q25: mờ Gaussian σ=1,0 và σ=2,0 px; nhiễu Gauss cộng σ=5 và σ=10 (mức xám 0–255).
  Thứ tự: mờ/nhiễu áp lên ảnh sạch → nén JPEG q25.
- Mỗi ô: 10 seed. Mỗi seed đổi: phương vị φ ngẫu nhiên trong [0°, 360°), độ lệch tâm marker
  du ∈ [−80, 80] px, dv ∈ [−60, 60] px, và (nếu có) mẫu nhiễu. Cùng seed dùng chung hình học cho mọi mức JPEG.

### Đại lượng ghi lại mỗi ảnh
- `detected` (có trả về id=0 hay không), `reproj_px` (RMS, do `detect_and_solve_pnp` trả về),
- `rot_err_deg` = acos((trace(R_gtᵀ·R_est) − 1)/2) (geodesic),
- `pos_err_m` = ‖C_est − C_gt‖ với C = −Rᵀt (vị trí camera trong hệ marker), `pos_err_rel` = pos_err_m / D,
- `side_mean_px`, `side_min_px`: độ dài cạnh trung bình / cạnh ngắn nhất của marker trên ảnh, tính từ
  4 góc ĐÁP ÁN (có cả khi không detect được), `side_det_px` từ 4 góc detect được.

## 2. Tiêu chí đánh giá (chốt trước khi chạy)

Một ô điều kiện (D, θ, mức suy giảm) gồm 10 seed được coi là **"dùng được"** khi đồng thời:
1. Tỉ lệ nhận diện ≥ 90% (≥ 9/10 seed detect được id=0);
2. Trung vị sai số xoay (trên các seed detect được) ≤ 2°;
3. Trung vị sai số vị trí camera (trên các seed detect được) ≤ 10% · D.

Tiêu chí phụ **"an toàn"** (chặt hơn, phản ánh rủi ro 1 lần hiệu chỉnh hỏng): tỉ lệ seed đạt *cả ba*
(detect được VÀ xoay ≤ 2° VÀ vị trí ≤ 10%·D) ≥ 90%. Báo cáo cả hai, kết luận chính dựa trên tiêu chí chính,
khuyến nghị kích thước marker dựa trên tiêu chí "an toàn" (vì hiệu chỉnh thật chỉ chụp 1 lần).

Quy tắc "N px tối thiểu" (chốt trước): gom mọi mẫu JPEG q20, q25, q30 (gần ESP32), mọi D và θ, chia bin
theo `side_min_px`; N = cận dưới của bin nhỏ nhất mà **từ bin đó trở lên** mọi bin có tỉ lệ seed đạt
"an toàn" ≥ 90%. Kích thước marker khuyến nghị cho D = 3/5/8 m = kích thước nhỏ nhất để `side_min_px` ≥ N
tại góc nhìn đang xét (tính số trên mô hình chiếu), làm tròn lên bội số 50 mm.

---

> Từ đây trở xuống là KẾT QUẢ (viết sau khi chạy). Tiêu chí ở mục 2 giữ nguyên, không chỉnh.

## 3. Cách chạy lại (chỉ CPU, mọi file ghi trong `stress_test/`)

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/run_stress.py             # lưới chính -> results.csv (~100 s)
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/analyze.py                # bảng + charts/01-03 + summary.json
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/supplementary.py          # validation.csv + sweep.csv (~4 phút)
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/analyze_supplementary.py  # bảng bổ sung + charts/04
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/make_examples.py          # examples/*.png
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B stress_test/test_stress.py            # test nhanh (~2 s)
```

Ba biến thể bộ dò được đo trên CÙNG một tập ảnh:
- **A (calibrate_aruco hiện tại)**: gọi thẳng `calibrate_aruco.detect_and_solve_pnp`. Đây là kết quả chính.
- **B (SUBPIX)**: cùng logic, chỉ thêm `cornerRefinementMethod = CORNER_REFINE_SUBPIX`. Đây là phương án đề xuất, không sửa code dùng chung.
- **C (SUBPIX + IPPE_SQUARE)**: như B, thêm cờ `SOLVEPNP_IPPE_SQUARE`. Kết quả gần như trùng B nên phần lớn bảng không in lại C.

Bản sao logic A trong `detect_variants.py` đã được đối chiếu với hàm chính thức: khớp 96/96 ô (cả việc detect được hay không lẫn sai số xoay, sai khác < 1e-6°).

## 4. Tóm tắt kết quả (marker 200 mm)

1. **Điểm gãy thật sự là ĐỘ CHÍNH XÁC POSE, không phải khả năng detect.** Ở q20–30 (gần ESP32), A vẫn detect ≥ 90% tới 5 m (θ ≤ 45°) và 3 m (θ = 65°). Nhưng sai số xoay vượt 2° từ rất sớm:
   - Tiêu chí chính "dùng được": A chỉ đạt tới **2 m** với θ = 45°/65° (riêng q30 tới 3 m). Với θ = 20° (gần nhìn thẳng) chỉ đạt tới **1 m** ở q25/q30.
   - Tiêu chí "an toàn": A đạt tới **2 m** với θ = 65°, **1–2 m** với θ = 45°, và chỉ **1 m** với θ = 20°.
   - Với B (SUBPIX), điểm gãy lùi ra **3 m** ở hầu hết các ô q20–30.

   Detect bắt đầu thất bại (< 90%) ở **8 m** với θ = 20°/45° (cạnh ~12–15 px) và ở **5 m** với θ = 65° (cạnh ngắn ~14 px). Tới 12 m (cạnh 6–10 px) gần như không còn detect được.
2. **Chất lượng JPEG ảnh hưởng ít hơn kích thước marker trên ảnh.** Từ q95 xuống q8, tỉ lệ detect ở D ≤ 3 m gần như không đổi. Sai số xoay chỉ tăng rõ ở 3 m: A đạt "an toàn" tại 3 m (θ = 45°/65°) khi ảnh q95, nhưng trượt khi ảnh q20–30. Thang q12/q8 (khắc nghiệt hơn ESP32 thật) cũng không làm luồng xử lý sụp ở ≤ 2 m.
3. **Mờ (lệch nét) là loại nhiễu phá hoại nhất.** Mờ σ = 2 px + q25 làm mất detect từ 2–3 m: θ = 45° còn 80% ở 2 m và 0% ở 3 m; θ = 65° về 0% ngay từ 2 m. Mờ σ = 1 px gây hại từ 5 m (θ = 65°: từ 3 m). Nhiễu Gauss σ = 5/10 hầu như không ảnh hưởng, vì ngưỡng thích nghi của ArUco chịu nhiễu tốt. Vì vậy **lấy nét ống kính OV2640 là việc quan trọng** khi lắp đặt.
4. **Sai số vị trí là hệ quả của sai số xoay.** Không có mẫu nào trượt vị trí (> 10% D) mà vẫn đạt xoay (≤ 2°).
5. **Lỗi lật pose** (sai số xoay > 10°, do nhập nhằng của mặt phẳng) chiếm 14,8% (A) / 13,4% (B) / 12,6% (C) số mẫu detect được, tập trung ở marker nhỏ (< 25 px).
6. **Sai số reprojection KHÔNG phân biệt được pose đúng hay sai.** Với A, trung vị reprojection RMS là 0,27 px khi xoay ≤ 2°, 0,24 px khi xoay sai 2–10°, và 0,23 px khi xoay sai > 10°. Nghĩa là con số mà `calibrate_aruco.py` in ra không dùng được làm ngưỡng chấp nhận.
7. **Có 1 lần detect nhầm id** (id = 17 ở 12 m, θ = 65°, q8). Code hiện tại từ chối đúng nhờ kiểm tra `marker_id`.
8. Ở q20–30, ảnh JPEG của cảnh giả lập nặng ~8–9 KB, nhỏ hơn ảnh thật 12–15 KB, vì cảnh giả lập ít chi tiết hơn. Bảng lượng tử hoá JPEG ở cùng mức q thì giống nhau, nên mức suy giảm quanh marker vẫn tương đương.

### Bảng điểm gãy rút gọn (A = code hiện tại, marker 200 mm, q20–30)

| θ | Detect ≥ 90% tới | "Dùng được" tới | "An toàn" tới | Cạnh ngắn tại điểm "an toàn" cuối |
|---|---|---|---|---|
| 20° | 5 m (8 m: 80–90%) | 1–2 m (q20: 2 m; q25/q30: 1 m) | 1 m | ~116 px |
| 45° | 5 m | 2–3 m (q30: 3 m) | 1–2 m (q20: 2 m) | ~47 px |
| 65° | 3 m | 2–3 m (q30: 3 m) | 2 m | ~30 px |

Với B (SUBPIX): "an toàn" tới 2 m (θ = 20°/65°) và 2–3 m (θ = 45°); "dùng được" tới 3 m ở mọi θ (trừ θ = 65°, q20: 2 m).

#### Điểm gãy (D lớn nhất còn đạt; ô đầu tiên trượt) — chỉ JPEG


**D lớn nhất (m) mà mọi D ≤ nó đều đạt 'dùng được (chính)'** (— = trượt ngay từ 1 m)

| biến thể | θ | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 |
|---|---|---|---|---|---|---|---|---|---|
| A | 20 | 2 | 2 | 1 | 1 | 2 | 2 | 2 | 2 |
| A | 45 | 5 | 3 | 3 | 2 | 2 | 2 | 3 | 2 |
| A | 65 | 5 | 3 | 3 | 2 | 2 | 2 | 2 | 2 |
| B | 20 | 5 | 3 | 3 | 3 | 3 | 2 | 2 | 2 |
| B | 45 | 5 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| B | 65 | 3 | 3 | 3 | 3 | 2 | 2 | 2 | 3 |
| C | 20 | 5 | 3 | 3 | 3 | 3 | 2 | 2 | 2 |
| C | 45 | 5 | 3 | 3 | 3 | 3 | 3 | 3 | 2 |
| C | 65 | 3 | 3 | 3 | 3 | 2 | 2 | 2 | 3 |

**D lớn nhất (m) mà mọi D ≤ nó đều đạt 'an toàn'** (— = trượt ngay từ 1 m)

| biến thể | θ | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 |
|---|---|---|---|---|---|---|---|---|---|
| A | 20 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| A | 45 | 3 | 1 | 1 | 1 | 2 | 2 | 2 | 2 |
| A | 65 | 3 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| B | 20 | 3 | 1 | 2 | 2 | 2 | 2 | 2 | 1 |
| B | 45 | 3 | 3 | 3 | 2 | 3 | 3 | 2 | 2 |
| B | 65 | 3 | 3 | 2 | 2 | 2 | 2 | 2 | 2 |
| C | 20 | 3 | 1 | 2 | 2 | 2 | 2 | 2 | 1 |
| C | 45 | 3 | 3 | 3 | 2 | 3 | 3 | 2 | 2 |
| C | 65 | 3 | 3 | 2 | 2 | 2 | 2 | 2 | 2 |

## 5. Bảng chi tiết

#### Kích thước marker 200 mm trên ảnh (px, trung bình 10 seed)

| D (m) | cạnh TB θ=20° | cạnh TB θ=45° | cạnh TB θ=65° | cạnh ngắn θ=20° | cạnh ngắn θ=45° | cạnh ngắn θ=65° |
|---|---|---|---|---|---|---|
| 1 | 120.8 | 107.3 | 93.1 | 116.4 | 93.0 | 72.2 |
| 2 | 60.1 | 53.3 | 45.2 | 58.7 | 47.0 | 30.0 |
| 3 | 40.0 | 35.5 | 30.6 | 39.0 | 31.4 | 22.8 |
| 5 | 24.1 | 21.4 | 18.4 | 23.6 | 18.8 | 14.3 |
| 8 | 15.0 | 13.3 | 11.4 | 14.7 | 11.9 | 8.0 |
| 12 | 10.0 | 8.9 | 7.6 | 9.8 | 8.0 | 5.6 |

#### Tỉ lệ nhận diện — A (calibrate_aruco hiện tại)


**θ = 20°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| 2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| 3 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 40% | 100% | 100% |
| 5 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 70% | 0% | 100% | 100% |
| 8 | 100% | 100% | 90% | 80% | 90% | 90% | 70% | 50% | 0% | 0% | 70% | 80% |
| 12 | 20% | 60% | 30% | 10% | 0% | 0% | 0% | 0% | 0% | 0% | 10% | 10% |

**θ = 45°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| 2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 80% | 100% | 100% |
| 3 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0% | 100% | 100% |
| 5 | 100% | 90% | 100% | 100% | 100% | 90% | 100% | 90% | 40% | 0% | 100% | 100% |
| 8 | 90% | 80% | 70% | 70% | 60% | 70% | 50% | 50% | 0% | 0% | 80% | 70% |
| 12 | 20% | 0% | 10% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |

**θ = 65°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| 2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0% | 100% | 100% |
| 3 | 100% | 100% | 100% | 100% | 100% | 90% | 90% | 90% | 60% | 0% | 100% | 100% |
| 5 | 100% | 80% | 60% | 70% | 70% | 80% | 70% | 40% | 0% | 0% | 80% | 80% |
| 8 | 60% | 10% | 20% | 20% | 0% | 10% | 0% | 0% | 0% | 0% | 0% | 10% |
| 12 | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |

#### Kết luận ô theo tiêu chí — A (calibrate_aruco hiện tại) (AT = an toàn, DĐ = dùng được, x = không đạt)


**θ = 20°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT |
| 2 | DĐ | DĐ | x | x | DĐ | DĐ | DĐ | DĐ | DĐ | x | DĐ | x |
| 3 | x | x | x | x | x | x | x | x | x | x | x | x |
| 5 | x | x | x | x | x | x | x | x | x | x | x | x |
| 8 | x | x | x | x | x | x | x | x | x | x | x | x |
| 12 | x | x | x | x | x | x | x | x | x | x | x | x |

**θ = 45°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT |
| 2 | AT | DĐ | DĐ | DĐ | AT | AT | AT | AT | AT | x | DĐ | AT |
| 3 | AT | DĐ | DĐ | x | x | x | DĐ | x | DĐ | x | x | x |
| 5 | DĐ | x | x | x | x | x | x | x | x | x | x | x |
| 8 | x | x | x | x | x | x | x | x | x | x | x | x |
| 12 | x | x | x | x | x | x | x | x | x | x | x | x |

**θ = 65°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT |
| 2 | AT | AT | AT | AT | AT | AT | AT | AT | DĐ | x | AT | AT |
| 3 | AT | DĐ | DĐ | x | x | x | x | x | x | x | x | DĐ |
| 5 | DĐ | x | x | x | x | x | x | x | x | x | x | x |
| 8 | x | x | x | x | x | x | x | x | x | x | x | x |
| 12 | x | x | x | x | x | x | x | x | x | x | x | x |

#### Kết luận ô theo tiêu chí — B (SUBPIX) (AT = an toàn, DĐ = dùng được, x = không đạt)


**θ = 20°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT |
| 2 | AT | DĐ | AT | AT | AT | AT | AT | DĐ | AT | x | AT | AT |
| 3 | AT | AT | DĐ | DĐ | DĐ | x | x | x | x | x | DĐ | DĐ |
| 5 | DĐ | x | x | x | x | x | x | x | x | x | x | x |
| 8 | x | x | x | x | x | x | x | x | x | x | x | x |
| 12 | x | x | x | x | x | x | x | x | x | x | x | x |

**θ = 45°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT |
| 2 | AT | AT | AT | AT | AT | AT | AT | AT | AT | x | AT | AT |
| 3 | AT | AT | AT | DĐ | AT | AT | DĐ | DĐ | AT | x | AT | DĐ |
| 5 | DĐ | x | x | x | x | x | x | x | x | x | x | x |
| 8 | x | x | x | x | x | x | x | x | x | x | x | x |
| 12 | x | x | x | x | x | x | x | x | x | x | x | x |

**θ = 65°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT | AT |
| 2 | AT | AT | AT | AT | AT | AT | AT | AT | AT | x | AT | AT |
| 3 | AT | AT | DĐ | DĐ | x | x | x | DĐ | x | x | DĐ | DĐ |
| 5 | x | x | x | x | x | x | x | x | x | x | x | x |
| 8 | x | x | x | x | x | x | x | x | x | x | x | x |
| 12 | x | x | x | x | x | x | x | x | x | x | x | x |

#### Trung vị sai số xoay (°) — A (calibrate_aruco hiện tại)


**θ = 20°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.79 | 0.90 | 0.77 | 0.73 | 0.78 | 0.76 | 0.78 | 0.89 | 0.72 | 1.01 | 0.73 | 1.12 |
| 2 | 1.26 | 1.29 | 2.62 | 2.07 | 1.79 | 1.75 | 1.48 | 1.71 | 1.79 | 2.47 | 1.24 | 2.45 |
| 3 | 2.49 | 5.14 | 3.31 | 4.10 | 22.24 | 4.67 | 28.05 | 3.83 | 4.21 | 6.06 | 3.80 | 3.64 |
| 5 | 6.17 | 5.37 | 7.31 | 6.63 | 5.83 | 6.70 | 5.91 | 22.74 | 13.68 | — | 5.12 | 5.86 |
| 8 | 7.72 | 37.59 | 11.54 | 11.08 | 9.30 | 9.73 | 11.54 | 22.59 | — | — | 15.12 | 24.60 |
| 12 | 20.36 | 19.26 | 34.44 | 53.12 | — | — | — | — | — | — | 53.12 | 53.12 |

**θ = 45°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.40 | 0.35 | 0.42 | 0.44 | 0.67 | 0.52 | 0.71 | 0.56 | 0.58 | 0.58 | 0.49 | 0.55 |
| 2 | 0.86 | 1.35 | 1.08 | 1.22 | 0.99 | 1.43 | 0.93 | 1.10 | 1.37 | 1.56 | 1.35 | 1.45 |
| 3 | 0.86 | 1.50 | 1.64 | 2.02 | 2.05 | 2.06 | 2.00 | 2.25 | 1.47 | — | 2.04 | 2.22 |
| 5 | 1.96 | 2.83 | 3.85 | 4.16 | 46.71 | 3.72 | 89.58 | 3.97 | 4.05 | — | 4.02 | 4.18 |
| 8 | 4.91 | 4.91 | 6.40 | 4.45 | 7.43 | 4.45 | 4.66 | 4.51 | — | — | 6.46 | 5.10 |
| 12 | 48.11 | — | 5.28 | — | — | — | — | — | — | — | — | — |

**θ = 65°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.43 | 0.62 | 0.71 | 0.79 | 0.79 | 0.89 | 0.66 | 0.74 | 0.83 | 0.76 | 0.72 | 0.79 |
| 2 | 0.67 | 0.95 | 0.95 | 1.54 | 1.09 | 1.11 | 0.95 | 1.54 | 1.32 | — | 1.21 | 1.28 |
| 3 | 1.38 | 1.56 | 1.76 | 2.30 | 2.43 | 2.50 | 2.64 | 2.70 | 3.23 | — | 2.39 | 1.63 |
| 5 | 1.59 | 2.94 | 3.14 | 3.73 | 3.53 | 3.81 | 3.31 | 68.49 | — | — | 2.94 | 3.28 |
| 8 | 5.61 | 2.25 | 68.86 | 68.17 | — | 5.06 | — | — | — | — | — | 3.95 |
| 12 | — | — | — | — | — | — | — | — | — | — | — | — |

#### Trung vị sai số vị trí (% D) — A (calibrate_aruco hiện tại)


**θ = 20°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1.5 | 1.6 | 1.5 | 1.5 | 1.5 | 1.5 | 1.4 | 1.6 | 1.4 | 1.8 | 1.5 | 1.9 |
| 2 | 2.3 | 2.3 | 4.6 | 3.7 | 3.2 | 3.2 | 2.6 | 3.0 | 3.4 | 4.5 | 2.4 | 4.3 |
| 3 | 4.7 | 9.2 | 6.0 | 7.2 | 38.6 | 8.4 | 48.7 | 6.9 | 7.6 | 11.6 | 6.7 | 6.3 |
| 5 | 11.8 | 9.3 | 12.8 | 11.6 | 10.1 | 11.8 | 10.9 | 40.7 | 28.0 | — | 9.3 | 10.5 |
| 8 | 14.1 | 66.4 | 20.9 | 19.7 | 17.2 | 17.7 | 20.9 | 44.6 | — | — | 26.1 | 43.3 |
| 12 | 39.2 | 37.2 | 60.4 | 92.9 | — | — | — | — | — | — | 92.9 | 92.9 |

**θ = 45°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.9 | 0.8 | 0.8 | 0.9 | 1.2 | 1.0 | 1.2 | 1.2 | 1.1 | 0.9 | 1.0 | 1.0 |
| 2 | 1.6 | 2.3 | 2.1 | 2.5 | 1.9 | 2.3 | 1.7 | 2.0 | 2.3 | 3.8 | 2.3 | 2.5 |
| 3 | 2.7 | 3.1 | 3.9 | 3.8 | 3.5 | 3.9 | 4.0 | 4.1 | 4.2 | — | 3.8 | 3.9 |
| 5 | 5.5 | 5.5 | 8.3 | 7.8 | 76.3 | 8.3 | 142.5 | 8.0 | 10.1 | — | 7.4 | 6.7 |
| 8 | 9.7 | 10.4 | 10.3 | 13.1 | 16.5 | 11.1 | 10.3 | 14.3 | — | — | 12.8 | 10.3 |
| 12 | 81.3 | — | 12.6 | — | — | — | — | — | — | — | — | — |

**θ = 65°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.9 | 1.2 | 1.2 | 1.1 | 1.4 | 1.5 | 1.1 | 1.5 | 1.5 | 1.3 | 1.1 | 1.4 |
| 2 | 2.0 | 2.0 | 2.2 | 2.6 | 2.0 | 2.0 | 1.8 | 2.7 | 2.8 | — | 2.3 | 2.7 |
| 3 | 3.2 | 3.9 | 3.0 | 4.4 | 4.5 | 5.1 | 5.2 | 5.1 | 7.5 | — | 4.6 | 4.2 |
| 5 | 4.3 | 5.7 | 5.8 | 9.1 | 7.7 | 9.6 | 9.8 | 94.3 | — | — | 6.6 | 6.9 |
| 8 | 14.3 | 10.3 | 106.6 | 101.1 | — | 11.1 | — | — | — | — | — | 10.7 |
| 12 | — | — | — | — | — | — | — | — | — | — | — | — |

#### Trung vị sai số xoay (°) — B (SUBPIX)


**θ = 20°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.14 | 0.15 | 0.18 | 0.18 | 0.17 | 0.22 | 0.26 | 0.68 | 0.26 | 0.62 | 0.19 | 0.27 |
| 2 | 0.29 | 0.40 | 0.54 | 1.02 | 0.60 | 0.43 | 1.06 | 1.86 | 0.64 | 4.36 | 0.76 | 0.75 |
| 3 | 0.50 | 1.09 | 1.45 | 1.01 | 1.56 | 2.08 | 2.26 | 4.23 | 2.32 | 14.19 | 1.52 | 1.60 |
| 5 | 1.78 | 2.71 | 12.07 | 35.24 | 12.44 | 7.38 | 8.81 | 13.20 | 16.23 | — | 6.75 | 8.46 |
| 8 | 4.12 | 22.87 | 36.75 | 8.42 | 6.30 | 6.09 | 8.64 | 14.61 | — | — | 8.02 | 8.03 |
| 12 | 21.76 | 41.64 | 42.96 | 46.02 | — | — | — | — | — | — | 51.42 | 46.79 |

**θ = 45°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.11 | 0.14 | 0.14 | 0.12 | 0.13 | 0.22 | 0.17 | 0.25 | 0.14 | 0.38 | 0.13 | 0.13 |
| 2 | 0.24 | 0.24 | 0.31 | 0.31 | 0.35 | 0.40 | 0.30 | 0.77 | 0.63 | 1.74 | 0.28 | 0.28 |
| 3 | 0.45 | 0.44 | 0.48 | 0.77 | 0.87 | 0.86 | 1.46 | 1.56 | 0.97 | — | 0.81 | 0.76 |
| 5 | 1.18 | 3.50 | 4.02 | 6.83 | 47.48 | 91.00 | 7.80 | 4.92 | 3.93 | — | 6.50 | 3.51 |
| 8 | 3.43 | 4.08 | 4.28 | 6.88 | 6.31 | 4.99 | 4.25 | 7.42 | — | — | 7.46 | 6.09 |
| 12 | 97.21 | — | 98.89 | — | — | — | — | — | — | — | — | — |

**θ = 65°**

| D (m) | q95 | q50 | q30 | q25 | q20 | q15 | q12 | q8 | q25+blur1.0 | q25+blur2.0 | q25+noise5 | q25+noise10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.16 | 0.18 | 0.15 | 0.13 | 0.18 | 0.20 | 0.19 | 0.31 | 0.21 | 0.25 | 0.12 | 0.15 |
| 2 | 0.27 | 0.34 | 0.51 | 0.43 | 0.46 | 0.43 | 0.53 | 0.94 | 0.84 | — | 0.41 | 0.40 |
| 3 | 0.91 | 0.78 | 1.34 | 1.33 | 2.08 | 2.16 | 2.03 | 1.94 | 2.58 | — | 1.57 | 1.36 |
| 5 | 2.75 | 1.63 | 3.73 | 4.27 | 4.10 | 3.54 | 3.67 | 6.99 | — | — | 3.54 | 3.57 |
| 8 | 67.81 | 3.79 | 69.22 | 132.47 | — | 8.10 | — | — | — | — | — | 6.06 |
| 12 | — | — | — | — | — | — | — | — | — | — | — | — |

## 6. Quy tắc "marker cần chiếm tối thiểu N px cạnh"

### 6.1 Theo quy tắc đã chốt trước (mục 2)

#### Quy tắc N px — A (calibrate_aruco hiện tại) (mẫu q20/25/30, mọi D, θ)

| cạnh ngắn (px) | n | det_rate | pass_rate |
|---|---|---|---|
| [0, 8) | 63 | 2% | 0% |
| [8, 12) | 87 | 29% | 0% |
| [12, 16) | 45 | 78% | 2% |
| [16, 20) | 48 | 98% | 23% |
| [20, 25) | 51 | 100% | 22% |
| [25, 30) | 33 | 100% | 76% |
| [30, 35) | 24 | 100% | 46% |
| [35, 40) | 36 | 100% | 31% |
| [40, 45) | 18 | 100% | 100% |
| [45, 50) | 9 | 100% | 44% |
| [50, 60) | 42 | 100% | 55% |
| [60, 80) | 15 | 100% | 100% |
| ≥ 80 | 69 | 100% | 99% |

=> N = 60.0

Kích thước marker khuyến nghị (mm, làm tròn lên bội 50) với N=60, k(θ)={20: 0.942290417729588, 45: 0.7181417046210267, 65: 0.4269189282490605}:

| góc nhìn | D=3 m | D=5 m | D=8 m |
|---|---|---|---|
| θ=20° | 350 | 550 | 850 |
| θ=45° | 450 | 700 | 1100 |
| θ=65° | 700 | 1150 | 1850 |

#### Quy tắc N px — B (SUBPIX) (mẫu q20/25/30, mọi D, θ)

| cạnh ngắn (px) | n | det_rate | pass_rate |
|---|---|---|---|
| [0, 8) | 63 | 2% | 0% |
| [8, 12) | 87 | 29% | 1% |
| [12, 16) | 45 | 78% | 4% |
| [16, 20) | 48 | 98% | 29% |
| [20, 25) | 51 | 100% | 25% |
| [25, 30) | 33 | 100% | 91% |
| [30, 35) | 24 | 100% | 83% |
| [35, 40) | 36 | 100% | 78% |
| [40, 45) | 18 | 100% | 100% |
| [45, 50) | 9 | 100% | 89% |
| [50, 60) | 42 | 100% | 100% |
| [60, 80) | 15 | 100% | 100% |
| ≥ 80 | 69 | 100% | 100% |

=> N = 50.0

Kích thước marker khuyến nghị (mm, làm tròn lên bội 50) với N=50, k(θ)={20: 0.942290417729588, 45: 0.7181417046210267, 65: 0.4269189282490605}:

| góc nhìn | D=3 m | D=5 m | D=8 m |
|---|---|---|---|
| θ=20° | 300 | 450 | 700 |
| θ=45° | 350 | 600 | 950 |
| θ=65° | 600 | 1000 | 1550 |

Theo quy tắc chốt trước: **N = 60 px với A (code hiện tại)** và **N = 50 px với B/C (có SUBPIX)**, tính theo cạnh ngắn nhất của marker trên ảnh 640×480.

Để đổi N px thành kích thước marker, dùng hệ số hình học: `cạnh_ngắn_px ≈ k(θ) · f · S / D`, với f = 615,9 px. Lấy phân vị 10% của k từ ảnh đáp án: k(20°) = 0,942, k(45°) = 0,718, k(65°) = 0,427. Các giá trị này rất sát cos θ (0,940 / 0,707 / 0,423), nên có công thức nhanh: **S ≥ N · D / (616 · cos θ)** (mét).

### 6.2 Kiểm chứng kích thước khuyến nghị (seed mới 100–109, không dùng lại ảnh của lưới chính)

#### Kiểm chứng kích thước khuyến nghị (seed mới 100–109)

| biến thể | D (m) | θ | marker (mm) | q30 | q25 | q20 |
|---|---|---|---|---|---|---|
| A | 3.0 | 20 | 350.0 | DĐ: det 100% / đạt 60% / xoay 1.78° | DĐ: det 100% / đạt 70% / xoay 1.03° | DĐ: det 100% / đạt 80% / xoay 1.02° |
| A | 3.0 | 45 | 450.0 | AT: det 100% / đạt 100% / xoay 0.59° | AT: det 100% / đạt 100% / xoay 0.68° | AT: det 100% / đạt 100% / xoay 0.64° |
| A | 3.0 | 65 | 700.0 | AT: det 100% / đạt 100% / xoay 0.55° | AT: det 100% / đạt 100% / xoay 0.59° | AT: det 100% / đạt 100% / xoay 0.60° |
| A | 5.0 | 20 | 550.0 | DĐ: det 100% / đạt 70% / xoay 1.17° | DĐ: det 100% / đạt 60% / xoay 1.57° | DĐ: det 100% / đạt 50% / xoay 1.78° |
| A | 5.0 | 45 | 700.0 | AT: det 100% / đạt 100% / xoay 0.75° | AT: det 100% / đạt 100% / xoay 0.65° | AT: det 100% / đạt 100% / xoay 0.65° |
| A | 5.0 | 65 | 1150.0 | AT: det 100% / đạt 100% / xoay 0.43° | AT: det 100% / đạt 100% / xoay 0.59° | AT: det 100% / đạt 100% / xoay 0.42° |
| A | 8.0 | 20 | 850.0 | x: det 100% / đạt 50% / xoay 2.18° | x: det 100% / đạt 50% / xoay 2.11° | DĐ: det 100% / đạt 70% / xoay 1.50° |
| A | 8.0 | 45 | 1100.0 | AT: det 100% / đạt 90% / xoay 0.63° | AT: det 100% / đạt 100% / xoay 0.76° | AT: det 100% / đạt 100% / xoay 0.69° |
| A | 8.0 | 65 | 1850.0 | AT: det 100% / đạt 100% / xoay 0.36° | AT: det 100% / đạt 100% / xoay 0.54° | AT: det 100% / đạt 100% / xoay 0.50° |
| B | 3.0 | 20 | 300.0 | AT: det 100% / đạt 100% / xoay 0.52° | AT: det 100% / đạt 100% / xoay 0.53° | AT: det 100% / đạt 100% / xoay 0.73° |
| B | 3.0 | 45 | 350.0 | AT: det 100% / đạt 100% / xoay 0.25° | AT: det 100% / đạt 100% / xoay 0.32° | AT: det 100% / đạt 100% / xoay 0.27° |
| B | 3.0 | 65 | 600.0 | AT: det 100% / đạt 100% / xoay 0.12° | AT: det 100% / đạt 100% / xoay 0.17° | AT: det 100% / đạt 100% / xoay 0.17° |
| B | 5.0 | 20 | 450.0 | AT: det 100% / đạt 100% / xoay 0.59° | AT: det 100% / đạt 90% / xoay 0.70° | DĐ: det 100% / đạt 70% / xoay 1.65° |
| B | 5.0 | 45 | 600.0 | AT: det 100% / đạt 100% / xoay 0.32° | AT: det 100% / đạt 90% / xoay 0.39° | AT: det 100% / đạt 100% / xoay 0.28° |
| B | 5.0 | 65 | 1000.0 | AT: det 100% / đạt 100% / xoay 0.14° | AT: det 100% / đạt 100% / xoay 0.15° | AT: det 100% / đạt 100% / xoay 0.14° |
| B | 8.0 | 20 | 700.0 | AT: det 100% / đạt 100% / xoay 0.58° | AT: det 100% / đạt 100% / xoay 0.84° | AT: det 100% / đạt 100% / xoay 1.03° |
| B | 8.0 | 45 | 950.0 | AT: det 100% / đạt 100% / xoay 0.29° | AT: det 100% / đạt 100% / xoay 0.34° | AT: det 100% / đạt 100% / xoay 0.35° |
| B | 8.0 | 65 | 1550.0 | AT: det 100% / đạt 100% / xoay 0.15° | AT: det 100% / đạt 100% / xoay 0.22° | AT: det 100% / đạt 100% / xoay 0.20° |

Kết luận kiểm chứng:
- **B (SUBPIX)**: kích thước theo N = 50 đạt "an toàn" ở 26/27 ô. Ô còn lại (D = 5 m, θ = 20°, q20) chỉ đạt "dùng được", với 70% mẫu đạt.
- **A (code hiện tại)**: kích thước theo N = 60 đạt "an toàn" ở θ = 45° và 65°, nhưng **trượt ở θ = 20°**: chỉ 50–80% mẫu đạt, và ở 8 m với q25/q30 trượt cả tiêu chí chính. Nghĩa là với code hiện tại, một con số N duy nhất **không đủ** khi nhìn gần thẳng mặt marker.

### 6.3 Phân tích phụ (hậu kiểm, không thay quy tắc chính): ngưỡng px tách theo góc nhìn

Quét kích thước marker từ 200 đến 1900 mm tại D = 5 m và 8 m (seed 100–109, q20/25/30, 30 mẫu mỗi ô):

#### Quét kích thước marker: tỉ lệ đạt 'an toàn' (gộp q20/25/30, 30 mẫu/ô)


**A (calibrate_aruco hiện tại)** — mỗi ô: cạnh ngắn px / tỉ lệ đạt / (AT = mọi q an toàn, DĐ = mọi q dùng được)

| marker (mm) | D=5 θ=20° | D=5 θ=45° | D=5 θ=65° | D=8 θ=20° | D=8 θ=45° | D=8 θ=65° |
|---|---|---|---|---|---|---|
| 200.0 | 24px/0% | 19px/23% | 13px/17% | 15px/0% | 12px/3% | 9px/0% |
| 250.0 | 29px/3% | 24px/43% | 16px/33% | 18px/0% | 15px/7% | 11px/0% |
| 300.0 | 35px/13% | 28px/47% | 20px/70% DĐ | 22px/7% | 18px/13% | 13px/3% |
| 350.0 | 41px/13% | 33px/80% DĐ | 23px/67% DĐ | 26px/23% | 21px/23% | 15px/17% |
| 400.0 | 47px/33% | 38px/87% DĐ | 26px/73% DĐ | 29px/7% | 24px/47% | 17px/23% |
| 500.0 | 59px/37% | 47px/100% AT | 33px/90% AT | 37px/23% | 30px/47% | 22px/43% |
| 600.0 | 70px/70% DĐ | 57px/87% DĐ | 39px/100% AT | 44px/30% | 36px/80% DĐ | 26px/57% |
| 700.0 | 82px/73% DĐ | 66px/100% AT | 45px/100% AT | 51px/43% | 42px/83% DĐ | 30px/83% DĐ |
| 800.0 | 94px/83% DĐ | 76px/100% AT | 52px/97% AT | 58px/70% DĐ | 47px/90% AT | 35px/93% DĐ |
| 1000.0 | 117px/93% AT | 95px/100% AT | 64px/100% AT | 73px/60% DĐ | 59px/97% AT | 43px/93% AT |
| 1200.0 | 140px/87% DĐ | 114px/100% AT | 77px/100% AT | 87px/67% DĐ | 71px/100% AT | 52px/100% AT |
| 1500.0 | 174px/93% AT | 142px/97% AT | 96px/97% AT | 109px/87% DĐ | 89px/100% AT | 65px/100% AT |
| 1900.0 |  |  |  | 138px/100% AT | 112px/100% AT | 82px/100% AT |

**B (SUBPIX)** — mỗi ô: cạnh ngắn px / tỉ lệ đạt / (AT = mọi q an toàn, DĐ = mọi q dùng được)

| marker (mm) | D=5 θ=20° | D=5 θ=45° | D=5 θ=65° | D=8 θ=20° | D=8 θ=45° | D=8 θ=65° |
|---|---|---|---|---|---|---|
| 200.0 | 24px/3% | 19px/13% | 13px/7% | 15px/0% | 12px/7% | 9px/0% |
| 250.0 | 29px/27% | 24px/47% | 16px/47% | 18px/3% | 15px/23% | 11px/0% |
| 300.0 | 35px/63% DĐ | 28px/97% AT | 20px/83% DĐ | 22px/13% | 18px/17% | 13px/0% |
| 350.0 | 41px/67% DĐ | 33px/97% AT | 23px/83% DĐ | 26px/10% | 21px/37% | 15px/13% |
| 400.0 | 47px/87% DĐ | 38px/97% AT | 26px/90% DĐ | 29px/17% | 24px/37% | 17px/37% |
| 500.0 | 59px/100% AT | 47px/100% AT | 33px/90% AT | 37px/87% DĐ | 30px/97% AT | 22px/70% DĐ |
| 600.0 | 70px/100% AT | 57px/97% AT | 39px/100% AT | 44px/83% DĐ | 36px/93% AT | 26px/90% DĐ |
| 700.0 | 82px/100% AT | 66px/100% AT | 45px/100% AT | 51px/100% AT | 42px/93% AT | 30px/100% AT |
| 800.0 | 94px/100% AT | 76px/100% AT | 52px/97% AT | 58px/97% AT | 47px/100% AT | 35px/97% AT |
| 1000.0 | 117px/100% AT | 95px/100% AT | 64px/100% AT | 73px/100% AT | 59px/100% AT | 43px/100% AT |
| 1200.0 | 140px/100% AT | 114px/100% AT | 77px/100% AT | 87px/100% AT | 71px/100% AT | 52px/100% AT |
| 1500.0 | 174px/93% AT | 142px/97% AT | 96px/97% AT | 109px/100% AT | 89px/100% AT | 65px/100% AT |
| 1900.0 |  |  |  | 138px/100% AT | 112px/100% AT | 82px/100% AT |

#### Ngưỡng px theo từng θ (phân tích phụ): cạnh ngắn nhỏ nhất mà từ đó trở lên mọi kích thước đều AT

| biến thể | θ | D (m) | S_min_mm | side_min_px | side_mean_px |
|---|---|---|---|---|---|
| A | 20 | 5 | 1500 | 174.5 | 181.3 |
| A | 20 | 8 | 1900 | 137.8 | 143.2 |
| A | 45 | 5 | 700 | 66.3 | 75.1 |
| A | 45 | 8 | 800 | 47.4 | 53.4 |
| A | 65 | 5 | 500 | 32.5 | 45.8 |
| A | 65 | 8 | 1000 | 43.2 | 57.7 |
| B | 20 | 5 | 500 | 58.7 | 60.2 |
| B | 20 | 8 | 700 | 51.1 | 52.6 |
| B | 45 | 5 | 300 | 28.5 | 32.1 |
| B | 45 | 8 | 500 | 29.7 | 33.3 |
| B | 65 | 5 | 500 | 32.5 | 45.8 |
| B | 65 | 8 | 700 | 30.3 | 40.3 |

Đọc bảng:
- **A (code hiện tại)**: nhìn gần thẳng (θ ≈ 20°) cần cạnh ~**140–175 px** mới ổn định; θ = 45° cần ~**50–65 px**; θ = 65° cần ~**33–43 px**. Nhìn chính diện là ca tệ nhất cho sai số xoay, vì độ nghiêng của mặt phẳng khó ước lượng khi phối cảnh yếu. Việc thiếu tinh chỉnh subpixel làm điểm yếu này nặng thêm.
- **B (SUBPIX)**: θ = 20° cần ~**50–60 px**; θ = 45°/65° chỉ cần ~**30 px**. Quy tắc đơn giản: **cạnh ngắn ≥ ~50–60 px là an toàn ở mọi góc; ≥ ~30–33 px là đủ khi θ ≥ 45°.**

## 7. Khuyến nghị kích thước marker cần in (cạnh vùng mã đen, chưa tính lề trắng)

### 7.1 Theo quy tắc chốt trước, đã kiểm chứng ở mục 6.2 (mm, làm tròn lên bội 50)

| Góc nhìn θ | A: 3 m | A: 5 m | A: 8 m | B (SUBPIX): 3 m | B: 5 m | B: 8 m |
|---|---|---|---|---|---|---|
| 20° (bảng dựng gần thẳng mặt camera) | 350* | 550* | 850* | 300 | 450 | 700 |
| 45° | 450 | 700 | 1100 | 350 | 600 | 950 |
| 65° (bảng nằm phẳng, nhìn xiên) | 700 | 1150 | 1850 | 600 | 1000 | 1550 |

\* Đã kiểm chứng là KHÔNG đủ với code hiện tại (mục 6.2). Nếu giữ code A mà vẫn nhìn gần thẳng thì cần cạnh ≥ ~140 px (mục 6.3), tức khoảng 2,2 lần: ~0,75 m ở 3 m, ~1,2 m ở 5 m, ~1,95 m ở 8 m. Cách khác là nghiêng bảng về θ ≈ 45°.

### 7.2 Kịch bản thực tế: camera cao ~3 m, marker nằm phẳng trên mặt đất (cos θ = 3 / D)

- **D = 3 m**: marker nằm ngay dưới camera (θ ≈ 0°). Ca này nằm ngoài lưới và là ca nhìn thẳng (tệ nhất cho sai số xoay), nên không khuyến nghị.
- **D = 5 m → θ ≈ 53°**:
  - B: S ≥ 50·5/(616·0,6) ≈ 0,68 m → **700 mm**.
  - A: S ≥ 60·5/(616·0,6) ≈ 0,81 m → **850 mm**.
  - Bảng quét cho thấy B ở 5 m đã an toàn từ 300 mm (θ = 45°) và 500 mm (θ = 65°), nên 700 mm còn dư biên an toàn.
- **D = 8 m → θ ≈ 68°**:
  - B: S ≥ 50·8/(616·0,375) ≈ 1,73 m → **~1,75 m**.
  - A: S ≥ 60·8/(616·0,375) ≈ 2,08 m → **~2,1 m**.
  - Bảng quét cho thấy B ở 8 m, θ = 65° đã an toàn từ 700 mm, nên quy tắc chốt trước khá bảo thủ ở góc xiên lớn.

### 7.3 Khuyến nghị thực hành

1. **Marker 200 mm hiện tại chỉ dùng được khi camera cách marker ≤ 2 m** (code hiện tại, ảnh ESP32 q20–30). Nếu bật SUBPIX thì dùng được tới ≤ 3 m. Ở 5–8 m, marker 200 mm vẫn detect được nhưng pose sai 3–10°.
2. Đặt bảng **nghiêng về phía camera sao cho θ ≈ 45°**, không nhìn thẳng và không nằm bẹt quá xiên. Với code hiện tại, đây là góc cần marker nhỏ nhất.
3. Kích thước từ 600 mm trở lên không in được trên A4/A3. Cần in bạt hoặc khổ A1–A0, hoặc chuyển sang bảng nhiều marker / ChArUco (chưa thử trong bài này).
4. Riêng ảnh dùng để hiệu chỉnh nên chụp ở chất lượng cao nhất firmware cho phép: q95 đẩy điểm "an toàn" từ 2 m lên 3 m. Lưu ý thang esp32 ngược thang OpenCV (số nhỏ hơn = chất lượng cao hơn).
5. Lấy nét kỹ ống kính, vì mờ σ = 2 px làm mất detect ngay từ 2–3 m.
6. (Chưa thử) Chụp nhiều khung rồi lấy trung vị pose để giảm sai số xoay.

## 8. Ảnh và chart

- `charts/01_ti_le_nhan_dien_A.png`: heatmap tỉ lệ detect theo (D × JPEG) cho 3 góc nhìn; khung xanh là vùng q20–30.
- `charts/02_ti_le_dat_theo_px.png`: tỉ lệ đạt "an toàn" và tỉ lệ detect theo bin cạnh ngắn (px), ảnh q20–30, A/B/C.
- `charts/03_sai_so_xoay_theo_khoang_cach.png`: trung vị sai số xoay theo D (A nét liền, B nét đứt), ngưỡng 2°.
- `charts/04_quet_kich_thuoc_theo_goc.png`: quét kích thước marker, tỉ lệ đạt theo px, tách theo θ.
- `examples/01_dat_D2_th45_q25.png`: ca đạt (2 m, θ = 45°, q25).
- `examples/02_gay_pose_D3_th20_q25.png`: ca vừa gãy pose (3 m, θ = 20°, q25): detect được nhưng xoay sai 4,2°, vị trí sai 7%.
- `examples/03_gay_detect_D8_th45_q25.png`: ca vừa gãy detect (8 m, θ = 45°, q25, cạnh ~12 px).
- `examples/04_gay_detect_D3_th45_blur2.png`: mờ σ = 2 + q25 ở 3 m, không detect được.

Trong các ảnh ví dụ: khung đỏ là 4 góc đáp án, khung xanh lá là 4 góc detect (A). Nửa bên phải là vùng quanh marker được phóng to kiểu nearest, để thấy rõ các khối 8×8 của JPEG.

## 9. Giả định tự chọn và giới hạn

- Camera pinhole không méo, f suy từ FOV chéo 66° (giả định của exp02, chưa đo thật). Méo ống kính thật sẽ làm sai số tệ hơn ở rìa ảnh, vì vậy marker luôn được đặt gần tâm ảnh (lệch tối đa ±80/±60 px).
- JPEG dùng libjpeg của OpenCV (chroma 4:2:0), không phải bộ mã hoá phần cứng của OV2640. Mốc "q20–30 ≈ ESP32" lấy từ exp01. Chưa mô phỏng nhiễu cảm biến, cân bằng trắng, méo ống kính, bóng đổ, chói, bẩn hay marker bị cong.
- Giấy trắng mức xám 220, mực đen 35, ánh sáng đều.
- θ và D là pose tương đối giữa camera và marker. Trong lưới chính, độ cao camera = D·cos θ (không cố định 3 m). Kịch bản "camera cao 3 m, marker nằm phẳng trên đất" được quy đổi ở mục 7.2; quy đổi này hợp lệ vì ảnh của marker chỉ phụ thuộc pose tương đối.
- Mỗi seed thay đổi phương vị φ, độ lệch tâm và mẫu nhiễu. Với các điều kiện chỉ có JPEG, khác biệt giữa các seed đến từ hình học (vị trí lưới pixel và khối JPEG so với cạnh marker).
- Lưới chính có 10 seed mỗi ô, phần quét kích thước có 30 mẫu mỗi ô. Mỗi seed chiếm 10% tỉ lệ, nên các ô sát ngưỡng 90% có độ bất định đáng kể.
- Tác động của sai số xoay 2° lên việc chiếu mask ra bản đồ chưa được định lượng trong bài này.

## 10. Vấn đề phát hiện trong code dùng chung (KHÔNG tự sửa, chỉ đề xuất)

> **Cập nhật 2026-10-12 (vòng 2):** các đề xuất 1–2 dưới đây đã được áp dụng vào `calibrate_aruco.py`
> (SUBPIX + IPPE_SQUARE + khối `quality`/cảnh báo). Các số trong báo cáo này (biến thể A, "mặc định")
> là của hành vi CŨ, tái lập được bằng `detect_and_solve_pnp(..., legacy=True)`; `detect_variants.py`
> đã được chuyển sang `legacy=True` cho biến thể A. Lưu ý: chọn nghiệm theo độ cao camera nhập tay
> KHÔNG dùng được (hai nghiệm cùng độ cao), chỉ dùng để kiểm tra chéo.

1. `calibrate_aruco.detect_and_solve_pnp` dùng `aruco.DetectorParameters()` mặc định. Trên OpenCV 5.0.0, giá trị mặc định là `cornerRefinementMethod` = NONE. Đo trên ảnh sạch:
   - Góc detect lệch vào trong trung bình 0,57 px, sai số góc trung bình 0,69 px.
   - Bật SUBPIX thì sai số góc còn 0,20 px.

   Đề xuất thêm `params.cornerRefinementMethod = aruco.CORNER_REFINE_SUBPIX` ngay sau dòng `params = aruco.DetectorParameters()`. Thay đổi này giảm N từ 60 xuống 50 px, và quan trọng hơn là sửa điểm yếu khi nhìn gần thẳng (mục 6.3). Thêm `SOLVEPNP_IPPE_SQUARE` không cải thiện đáng kể.
2. README và `calibrate_aruco.py` coi reprojection là chỉ số chất lượng ("càng nhỏ càng tốt"), nhưng reprojection gần như không đổi giữa pose đúng và pose sai hoặc bị lật (mục 4, ý 6). Đề xuất không dùng reprojection làm ngưỡng chấp nhận. Thay vào đó, kiểm tra cạnh marker trên ảnh ≥ N px, và/hoặc dùng `solvePnPGeneric` (IPPE) để so sánh 2 nghiệm.
3. `generate_marker.py`: mã 200 mm cộng lề trắng 1 module (~33 mm mỗi bên) thành ~267 mm, **không vừa khổ A4** (210 mm), phải in A3.
4. `make_synthetic_test.py`: lề trắng bằng 0,2·S, không khớp tỉ lệ 1/6·S của `generate_marker.py`. Hàm còn warp trực tiếp, không siêu lấy mẫu, nên ảnh bị răng cưa. Lỗi này chỉ ảnh hưởng demo, không ảnh hưởng bài này vì bài này dùng bộ dựng cảnh riêng.

## 11. File trong `stress_test/`

- `scene.py`: dựng cảnh, pose đáp án, suy giảm ảnh, đo sai số.
- `detect_variants.py`: gọi `detect_and_solve_pnp` qua file tạm; chứa thêm biến thể B/C.
- `run_stress.py`: lưới chính, ra `results.csv` (6480 dòng = 18 hình học × 10 seed × 12 điều kiện × 3 biến thể).
- `analyze.py`: bảng, điểm gãy, quy tắc N, `summary.json`, charts 01–03.
- `supplementary.py`: ra `validation.csv` (540 dòng) và `sweep.csv` (4500 dòng).
- `analyze_supplementary.py`: phân tích validation/sweep, chart 04.
- `make_examples.py`: tạo ảnh trong `examples/`.
- `test_stress.py`: 3 test, chạy ~2 s.
- `tmp/`: rỗng; file JPEG tạm được xoá ngay sau khi đọc.
