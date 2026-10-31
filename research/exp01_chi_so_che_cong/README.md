# exp01 — Chỉ số che cống: ROI cố định & làm mượt theo thời gian

## Mục tiêu

Trả lời bằng số liệu:

1. Tính độ che cống bằng **vùng cống cố định theo camera (ROI)** có cho số chính xác hơn công thức production
   hiện tại (`inference/analysis.py`) không — kể cả trên ảnh xuống cấp giống ESP32?
2. **Làm mượt theo thời gian** (median 5 khung + hysteresis) có giảm sai số và giảm nhấp nháy trạng thái không?

Thí nghiệm độc lập, chỉ đọc model và dữ liệu, chỉ ghi trong thư mục này. Chỉ dùng split `valid` và `test`
(không bao giờ dùng `train`).

## Phương pháp (tóm tắt)

- **M0** — công thức production: `|hợp Trash dự đoán ∩ hợp Drain dự đoán| / |hợp Drain dự đoán|`, bỏ trống nếu không
  phát hiện Drain. Một giá trị cho cả ảnh.
- **M1** — ROI = polygon Drain GT: `|hợp Trash dự đoán ∩ ROI| / |ROI|`. Không bao giờ thiếu.
- **M2** — như M1 nhưng ROI lệch: dịch 5% / 10% kích thước bbox theo 4 hướng; co giãn ×0.9 / ×1.1 quanh tâm.
- **C0** = ảnh gốc; **C1** = giống ESP32 (resize 640×640 INTER_AREA, JPEG q12).
- **C2** (phân tích bổ sung, xem bên dưới) = resize 640×640 INTER_AREA, JPEG OpenCV **q25**; GT/ROI ở 640×640.
- Mức: xanh < 20, vàng 20–<50, đỏ ≥ 50. Hysteresis: đỏ vào 50 / ra 35; vàng vào 20 / ra 12.
- Độ tin cậy cũ = min confidence mọi object; mới = trung bình có trọng số (pixel trong ROI) của conf Trash. Cờ = < 0.5.

## Tiêu chí đạt (đăng ký trước)

Tính trên **gộp valid+test, điều kiện C1**; tính lại trên **chỉ test** — nếu bất kỳ tiêu chí nào cho kết quả
khác chiều giữa gộp và chỉ test thì kết luận chung = **"KHÔNG KẾT LUẬN"** kèm giải thích.

**Phương pháp ROI ĐẠT khi và chỉ khi tất cả:**

1. M1 không thiếu giá trị ở bất kỳ cống GT đỏ nào (hiển thị số thiếu của M0);
2. MAE(M1) ≤ MAE(M0) trên tập con M0 không thiếu;
3. số bỏ sót nghiêm trọng (GT đỏ → dự đoán xanh hoặc thiếu) của M1 < của M0;
4. dung sai hiệu chỉnh: MAE trung bình 4 hướng của M2 dịch 10% trừ MAE(M1) ≤ 5 điểm.

**Làm mượt ĐẠT khi và chỉ khi tất cả (M1, chuỗi mô phỏng):**

- (a) tổng số lần đổi trạng thái S2 ≤ 50% của S0;
- (b) MAE(S1) ≤ MAE(S0);
- (c) độ chính xác trạng thái S2 ≥ S0;
- (d) kiểm tra trễ bậc bằng số đạt (10%×10 khung rồi 70%: lên đỏ ở khung 70 thứ 3).

Không chỉnh ngưỡng sau khi có kết quả.

**Phân tích phụ (không ảnh hưởng tiêu chí chính):** ảnh có đúng 1 cống (M0 là giá trị theo ảnh, nên tập này so
sánh công bằng theo cống); bỏ cống rất nhỏ (< 1024 px² đo ở 1024×1024).

## Phân tích bổ sung C2 — sát ảnh ESP32 thật

**Lý do (quyết định trước khi có bất kỳ kết quả C2 nào):** firmware dùng esp32-camera `jpeg_quality = 12`, nhưng
thang của esp32-camera **ngược** với OpenCV (esp32-camera: số nhỏ = chất lượng cao; OpenCV: số lớn = chất lượng
cao). Ảnh ESP32 VGA thật khoảng 12–15 KB; OpenCV quality 20–30 ở 640×480 cho 13,1–16,4 KB trên ảnh tphcm của Try1.
Vì vậy C1 (OpenCV q12) có lẽ khắc nghiệt hơn thực tế.

**Định nghĩa (đăng ký trước):**

- C2 = resize 640×640 INTER_AREA → JPEG OpenCV q25 (`C2_JPEG_QUALITY` trong `config.py`) → giải mã; GT/ROI
  rasterize ở 640×640 (giống C1, chỉ khác quality).
- Chuỗi mô phỏng C2: giống hệt chuỗi chính (cùng seed `[SEED, image_idx, frame]`, cùng mọi nhiễu), chỉ JPEG cuối
  lấy ngẫu nhiên q20..30 (`SIM_C2_JPEG_QUALITY`) thay vì q10..15. Ghi ra tệp riêng, không ghi đè chuỗi chính.
- Trên C2 tính đúng các chỉ số và tiêu chí như C1 (ROI 1–4, làm mượt a–d, gộp và chỉ test), nhưng chỉ trình bày
  là **tham khảo bổ sung**. **Kết luận chính vẫn là kết luận trên C1 và không đổi.**
- `outputs/summary_before_C2.json` là bản sao `summary.json` trước khi thêm C2; mọi giá trị C0/C1 sau khi chạy lại
  phải giống hệt bản này.

## Chạy (theo thứ tự)

Chạy từ trong thư mục thí nghiệm:

```bash
cd C:/Users/ASUS/Desktop/SSC/research/exp01_chi_so_che_cong
PY=C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe
$PY -B tests/test_logic.py      # kiem tra logic (CPU, khong model)
$PY -B 01_ground_truth.py       # CPU  -> outputs/ground_truth.csv
$PY -B 02_predict.py            # GPU  -> cache/*.npz, outputs/inference_times.csv
$PY -B 03_measure.py            # CPU  -> outputs/per_drain.csv
$PY -B 04_smoothing_sim.py      # GPU  -> outputs/per_frame.csv, outputs/perturbations.csv
$PY -B 05_report.py             # CPU  -> outputs/summary.json, charts, examples, REPORT.md
$PY -B tests/test_logic.py      # chay lai: doi chieu them voi ground_truth.csv
```

Thêm C2 (phân tích bổ sung) mà **không** tính lại C0/C1:

```bash
$PY -B tests/test_logic.py
$PY -B 02_predict.py --conds C2          # GPU, 69 ảnh -> cache/*_C2.npz; giữ nguyên dòng C0/C1 trong index/timing
$PY -B 03_measure.py                     # CPU, tất định: tính lại per_drain.csv cho C0, C1, C2 (C0/C1 giống hệt)
$PY -B 04_smoothing_sim.py --variant C2  # GPU, 1380 khung -> outputs/per_frame_C2.csv, outputs/perturbations_C2.csv
$PY -B 05_report.py                      # thêm mục "Phân tích bổ sung C2" vào REPORT.md và summary.json
$PY -B tests/test_logic.py
```

`02_predict.py` không tham số chạy C0 C1 như ban đầu; `04_smoothing_sim.py` không tham số chạy chuỗi chính (q10..15).

## Đầu ra

- `outputs/ground_truth.csv` — GT theo từng cống (gồm `gt_area_px_1024`).
- `cache/*.npz`, `cache/index.csv` — mask dự đoán (hợp Trash, hợp Drain, từng instance) cho C0/C1/C2.
- `outputs/inference_times.csv` — thời gian suy luận (dòng C2 đo trong phiên chạy riêng).
- `outputs/per_drain.csv` — GT, M0, M1, M2, độ tin cậy cũ/mới, mức, theo cống × điều kiện.
- `outputs/per_frame.csv`, `outputs/perturbations.csv` — chuỗi mô phỏng và mọi tham số nhiễu từng khung.
- `outputs/per_frame_C2.csv`, `outputs/perturbations_C2.csv` — chuỗi mô phỏng bổ sung C2 (JPEG cuối q20..30).
- `outputs/summary.json` — toàn bộ chỉ số và kết luận (C2 nằm ở khóa `supplementary_C2` và các khóa `C2|...`).
- `outputs/summary_before_C2.json` — bản sao summary.json trước khi thêm C2 (để đối chiếu).
- `outputs/charts/*.png` — scatter, ma trận nhầm lẫn (C0/C1/C2), độ nhạy M2, phân rã sai số, 3 timeline
  (tiêu đề timeline dùng split + chỉ số trong split, khớp tên tệp overlay).
- `outputs/examples/*.jpg` — 10 ảnh overlay (C1).
- `REPORT.md` — báo cáo tiếng Việt (sinh tự động bởi `05_report.py`).

## Xóa thí nghiệm

Không có gì ngoài thư mục này bị thay đổi. Để xóa, chỉ cần xóa thư mục
`research/exp01_chi_so_che_cong/`.
