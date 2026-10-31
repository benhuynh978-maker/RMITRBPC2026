# Báo cáo exp01 — Chỉ số che cống: ROI cố định & làm mượt theo thời gian

*Tệp này do `05_report.py` sinh tự động; không sửa tay.*

## Kết luận

**Phương pháp ROI cố định (M1): ĐẠT** — mọi tiêu chí đạt trên cả gộp và chỉ test. Trên điều kiện ESP32 (C1), gộp valid+test (76 cống): M0 (công thức hiện tại) thiếu giá trị ở 47 cống (61.8%), trong đó 16/18 cống GT đỏ; M1 không bao giờ thiếu. Trên tập M0 có giá trị (n=29), MAE M0 = 8.36 điểm, MAE M1 = 6.04 điểm (chênh lệch cặp M1−M0 = -2.32 [-6.51; 0.00]). Bỏ sót nghiêm trọng (GT đỏ → xanh/thiếu): M0 = 18, M1 = 14. Dịch ROI 10% làm MAE tăng trung bình -0.07 điểm.

**Làm mượt (median 5 + hysteresis): KHÔNG KẾT LUẬN** — tiêu chí b cho kết quả khác nhau giữa gộp valid+test và chỉ test. Trên chuỗi mô phỏng (M1, gộp): số lần đổi trạng thái S0 = 84 → S2 = 2; MAE S0 = 21.18 → S1 = 21.21; độ chính xác trạng thái S0 = 70.1% → S2 = 71.1%. Trễ khi nhảy bậc 10%→70%: 3 khung.

Tiêu chí được đăng ký trước khi có kết quả; ngưỡng không được chỉnh sau khi chạy.

*Hai kết luận trên (tính trên C1) là kết luận chính và không đổi. Xem thêm mục "Phân tích bổ sung C2 — sát ảnh ESP32 thật" (JPEG OpenCV q25) — chỉ để tham khảo.*

## Tiêu chí đăng ký trước

### Phương pháp ROI

| Tiêu chí | Gộp valid+test (C1) | Chỉ test (C1) |
|---|---|---|
| (1) M1 không thiếu ở cống GT đỏ | M1 thiếu=0 / 18 đỏ (M0 thiếu=16) → **ĐẠT** | M1 thiếu=0 / 7 đỏ (M0 thiếu=5) → **ĐẠT** |
| (2) MAE(M1) ≤ MAE(M0) trên tập M0 không thiếu | M1=6.04 vs M0=8.36 (n=29) → **ĐẠT** | M1=6.14 vs M0=10.94 (n=14) → **ĐẠT** |
| (3) Bỏ sót nghiêm trọng M1 < M0 | M1=14 vs M0=18 → **ĐẠT** | M1=3 vs M0=7 → **ĐẠT** |
| (4) MAE(M2 dịch 10%, TB 4 hướng) − MAE(M1) ≤ 5 | 21.73 − 21.80 = -0.07 → **ĐẠT** | 16.82 − 16.87 = -0.05 → **ĐẠT** |


**Kết luận ROI: ĐẠT** (mọi tiêu chí đạt trên cả gộp và chỉ test).

### Làm mượt

| Tiêu chí | Gộp valid+test (C1) | Chỉ test (C1) |
|---|---|---|
| (a) Tổng lần đổi trạng thái S2 ≤ 50% S0 | S2=2 vs S0=84 (ngưỡng 42.0) → **ĐẠT** | S2=2 vs S0=53 (ngưỡng 26.5) → **ĐẠT** |
| (b) MAE(S1) ≤ MAE(S0) | S1=21.21 vs S0=21.18 → **KHÔNG ĐẠT** | S1=16.48 vs S0=17.31 → **ĐẠT** |
| (c) Độ chính xác trạng thái S2 ≥ S0 | S2=71.1% vs S0=70.1% → **ĐẠT** | S2=77.2% vs S0=74.0% → **ĐẠT** |
| (d) Kiểm tra trễ bậc (đỏ ở khung 70 thứ 3) | trễ=3 khung (kỳ vọng 3) → **ĐẠT** | trễ=3 khung (kỳ vọng 3) → **ĐẠT** |


**Kết luận làm mượt: KHÔNG KẾT LUẬN** (tiêu chí b cho kết quả khác nhau giữa gộp valid+test và chỉ test).

## MAE theo cống (điểm %)

C0 = ảnh gốc (GT ở kích thước gốc); C1 = giống ESP32 (640×640, JPEG q12; GT/ROI rasterize ở 640). CI bootstrap 95% (n=2000, lấy mẫu lại theo cống).

| Điều kiện | Tập | n cống | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập | M1−M0 (cặp) | MAE M1 tất cả | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | Báo động giả M0 / M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | gộp valid+test | 76 | 53 | 11.52 [6.30; 17.81] | 4.67 [1.84; 8.88] | -6.85 [-11.49; -3.18] | 13.05 [7.62; 18.89] | 12/18 | 18 / 8 | 0 / 0 |
| C0 | chỉ test | 26 | 20 | 13.46 [4.21; 24.66] | 4.53 [1.03; 10.14] | -8.94 [-17.50; -1.84] | 9.34 [3.98; 16.07] | 3/7 | 7 / 1 | 0 / 0 |
| C0 | chỉ valid | 50 | 33 | 10.34 [4.14; 17.97] | 4.75 [1.39; 10.54] | -5.59 [-10.95; -1.74] | 14.97 [7.27; 23.59] | 9/11 | 11 / 7 | 0 / 0 |
| C1 | gộp valid+test | 76 | 29 | 8.36 [3.20; 15.22] | 6.04 [2.46; 11.16] | -2.32 [-6.51; 0.00] | 21.80 [14.97; 29.25] | 16/18 | 18 / 14 | 0 / 0 |
| C1 | chỉ test | 26 | 14 | 10.94 [1.35; 23.92] | 6.14 [0.74; 15.11] | -4.80 [-13.49; 0.00] | 16.87 [6.84; 28.75] | 5/7 | 7 / 3 | 0 / 0 |
| C1 | chỉ valid | 50 | 15 | 5.95 [2.47; 10.28] | 5.95 [2.47; 10.28] | 0.00 [0.00; 0.00] | 24.36 [15.44; 33.92] | 11/11 | 11 / 11 | 0 / 0 |


### Phân tích phụ: ảnh có đúng 1 cống (64 ảnh)

M0 tính trên hợp mọi cống dự đoán của cả ảnh nên mọi cống trong ảnh nhiều cống nhận cùng một giá trị. Tập con này so sánh M0 và M1 công bằng ở mức từng cống.

| Điều kiện | Tập | n cống | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập | M1−M0 (cặp) | MAE M1 tất cả | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | Báo động giả M0 / M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | gộp valid+test | 64 | 41 | 9.80 [4.17; 16.38] | 3.31 [1.49; 5.89] | -6.50 [-11.72; -2.09] | 13.74 [7.87; 20.49] | 12/16 | 16 / 7 | 0 / 0 |
| C0 | chỉ test | 24 | 18 | 11.68 [2.19; 21.89] | 4.98 [1.21; 10.70] | -6.71 [-14.20; -0.65] | 10.08 [4.29; 17.01] | 3/6 | 6 / 1 | 0 / 0 |
| C0 | chỉ valid | 40 | 23 | 8.33 [2.88; 17.07] | 2.00 [0.91; 3.16] | -6.34 [-14.39; -1.49] | 15.94 [7.10; 25.68] | 9/10 | 10 / 6 | 0 / 0 |
| C1 | gộp valid+test | 64 | 27 | 7.68 [2.50; 14.46] | 5.19 [1.76; 10.45] | -2.49 [-7.00; 0.00] | 22.44 [14.75; 31.03] | 14/16 | 16 / 13 | 0 / 0 |
| C1 | chỉ test | 24 | 14 | 10.94 [1.35; 23.92] | 6.14 [0.74; 15.11] | -4.80 [-13.49; 0.00] | 17.92 [7.20; 31.02] | 4/6 | 6 / 3 | 0 / 0 |
| C1 | chỉ valid | 40 | 13 | 4.16 [1.50; 7.27] | 4.16 [1.50; 7.27] | 0.00 [0.00; 0.00] | 25.15 [15.05; 35.96] | 10/10 | 10 / 10 | 0 / 0 |


### Phân tích phụ: bỏ cống rất nhỏ (< 1024 px²)

Chỉ giữ cống có diện tích polygon GT ≥ 1024 px² đo ở 1024×1024 (bỏ 16 cống: [53, 165, 192, 201, 315, 317, 348, 461, 464, 655, 792, 824, 873, 893, 987, 1005] px²). Phân tích này **không** ảnh hưởng tiêu chí chính.

| Điều kiện | Tập | n cống | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập | M1−M0 (cặp) | MAE M1 tất cả | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | Báo động giả M0 / M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | gộp valid+test | 60 | 48 | 10.88 [5.39; 17.38] | 4.87 [1.79; 9.48] | -6.01 [-10.86; -2.29] | 13.99 [7.56; 21.32] | 10/15 | 15 / 7 | 0 / 0 |
| C0 | chỉ test | 23 | 19 | 11.07 [2.18; 21.20] | 4.71 [1.13; 10.13] | -6.35 [-13.74; -0.60] | 10.11 [4.13; 17.38] | 3/6 | 6 / 1 | 0 / 0 |
| C0 | chỉ valid | 37 | 29 | 10.76 [3.83; 19.50] | 4.97 [1.30; 11.54] | -5.79 [-12.40; -1.65] | 16.40 [6.88; 27.86] | 7/9 | 9 / 6 | 0 / 0 |
| C1 | gộp valid+test | 60 | 29 | 8.36 [3.20; 15.22] | 6.04 [2.46; 11.16] | -2.32 [-6.51; 0.00] | 23.04 [14.80; 32.04] | 13/15 | 15 / 12 | 0 / 0 |
| C1 | chỉ test | 23 | 14 | 10.94 [1.35; 23.92] | 6.14 [0.74; 15.11] | -4.80 [-13.49; 0.00] | 18.70 [7.49; 31.89] | 4/6 | 6 / 3 | 0 / 0 |
| C1 | chỉ valid | 37 | 15 | 5.95 [2.47; 10.28] | 5.95 [2.47; 10.28] | 0.00 [0.00; 0.00] | 25.73 [14.47; 37.78] | 9/9 | 9 / 9 | 0 / 0 |


## Ma trận nhầm lẫn (gộp valid+test)

**C0 — M0**

| GT \ dự đoán | xanh | vàng | đỏ | thiếu |
|---|---|---|---|---|
| xanh | 45 | 0 | 0 | 8 |
| vàng | 2 | 0 | 0 | 3 |
| đỏ | 6 | 0 | 0 | 12 |


**C0 — M1**

| GT \ dự đoán | xanh | vàng | đỏ |
|---|---|---|---|
| xanh | 52 | 1 | 0 |
| vàng | 1 | 3 | 1 |
| đỏ | 8 | 2 | 8 |


**C1 — M0**

| GT \ dự đoán | xanh | vàng | đỏ | thiếu |
|---|---|---|---|---|
| xanh | 26 | 0 | 0 | 26 |
| vàng | 1 | 0 | 0 | 5 |
| đỏ | 2 | 0 | 0 | 16 |


**C1 — M1**

| GT \ dự đoán | xanh | vàng | đỏ |
|---|---|---|---|
| xanh | 52 | 0 | 0 |
| vàng | 5 | 0 | 1 |
| đỏ | 14 | 2 | 2 |


## Độ nhạy ROI (M2, MAE điểm %, gộp)

| Biến thể | C0 | C1 |
|---|---|---|
| M1 (ROI đúng) | 13.05 [7.62; 18.89] | 21.80 [14.97; 29.25] |
| s05_left | 13.00 [7.70; 18.75] | 21.57 [14.77; 29.02] |
| s05_right | 13.50 [7.99; 19.39] | 21.95 [15.08; 29.48] |
| s05_up | 13.21 [7.79; 18.89] | 21.96 [15.03; 29.41] |
| s05_down | 13.16 [7.69; 19.09] | 21.61 [14.82; 29.07] |
| s10_left | 13.03 [7.82; 18.73] | 21.28 [14.52; 28.65] |
| s10_right | 14.33 [8.74; 20.32] | 22.02 [15.06; 29.57] |
| s10_up | 13.73 [8.24; 19.46] | 22.12 [15.13; 29.61] |
| s10_down | 13.58 [8.04; 19.37] | 21.50 [14.67; 28.94] |
| sc090 | 13.09 [7.70; 18.80] | 21.77 [14.89; 29.18] |
| sc110 | 13.15 [7.65; 18.91] | 21.74 [14.90; 29.22] |
| dịch 5% — TB 4 hướng | 13.22 | 21.77 |
| dịch 10% — TB 4 hướng | 13.67 | 21.73 |


## Độ tin cậy (C1, gộp)

Cũ = min confidence của mọi object trong ảnh (mặc định 0.575); mới = trung bình có trọng số (pixel trong ROI) của confidence các instance Trash; cờ = giá trị < 0.5. Độ tin cậy mới là NaN (không gắn cờ) ở 66 cống.

| Quy tắc | Tỷ lệ gắn cờ | MAE M1 có cờ | MAE M1 không cờ |
|---|---|---|---|
| old | 27.6% (21/76) | 34.69 | 16.88 |
| new | 7.9% (6/76) | 50.51 | 19.34 |


## Làm mượt theo thời gian (chuỗi mô phỏng)

76 cống × 20 khung, đánh giá khung 5..20 (4 khung đầu khởi động). S0 = giá trị thô + ngưỡng thường; S1 = median 5 khung; S2 = hysteresis trên S1. Với M0: khung thiếu tính là trạng thái 'thiếu' (sai), S1 bỏ khung thiếu trong cửa sổ, S2 giữ trạng thái cũ.

| Phương pháp | Tập | MAE S0 | MAE S1 | S1−S0 theo cống [CI] | Đổi trạng thái S0 / S1 / S2 | TB đổi/cống S0 / S2 | Cống 0 lần đổi S0 / S2 | Đúng trạng thái S0 / S1 / S2 (%) | MAE khung bị che S0 / S1 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | gộp valid+test | 21.18 | 21.21 | 0.03 [-0.64; 0.59] | 84 / 4 / 2 | 1.11 / 0.03 | 55 / 74 (của 76) | 70.1 / 70.7 / 71.1 | 22.06 / 22.70 (n=151) |
| M1 | chỉ test | 17.31 | 16.48 | -0.84 [-2.01; 0.14] | 53 / 4 / 2 | 2.04 / 0.08 | 15 / 24 (của 26) | 74.0 / 76.0 / 77.2 | 15.83 / 15.73 (n=61) |
| M1 | chỉ valid | 23.19 | 23.67 | 0.48 [-0.27; 1.19] | 31 / 0 / 0 | 0.62 / 0.00 | 40 / 50 (của 50) | 68.0 / 68.0 / 68.0 | 26.29 / 27.43 (n=90) |
| M0 | gộp valid+test | 7.60 | 7.58 | -0.03 [-0.34; 0.29] | 167 / 27 / 9 | 2.20 / 0.12 | 39 / 69 (của 76) | 31.4 / 40.0 / 41.1 | 7.00 / 6.87 (n=46) |
| M0 | chỉ test | 7.45 | 7.38 | -0.05 [-0.37; 0.31] | 64 / 8 / 2 | 2.46 / 0.08 | 11 / 24 (của 26) | 43.8 / 51.9 / 53.8 | 10.16 / 9.96 (n=23) |
| M0 | chỉ valid | 7.73 | 7.77 | -0.01 [-0.58; 0.49] | 103 / 19 / 7 | 2.06 / 0.14 | 28 / 45 (của 50) | 25.0 / 33.8 / 34.5 | 3.84 / 3.78 (n=23) |


### Phân rã sai số (khung thô, 20 khung/cống)

bias = TB(thô) − GT; nhiễu = độ lệch chuẩn (ddof=0) theo cống; MSE = bias² + phương sai.

| Phương pháp | Tập | |bias| TB | Nhiễu TB | Tỷ phần MSE do bias² | Tỷ phần do phương sai |
|---|---|---|---|---|---|
| M1 | gộp valid+test | 20.48 | 4.74 | 95.0% | 5.0% |
| M1 | chỉ test | 16.49 | 5.99 | 92.4% | 7.6% |
| M1 | chỉ valid | 22.56 | 4.08 | 95.9% | 4.1% |
| M0 | gộp valid+test | 15.15 | 1.02 | 99.2% | 0.8% |
| M0 | chỉ test | 15.45 | 0.95 | 99.5% | 0.5% |
| M0 | chỉ valid | 14.91 | 1.07 | 98.9% | 1.1% |


Giảm nhiễu bằng làm mượt chỉ xử lý được phần phương sai; phần bias (sai lệch hệ thống của model) không đổi.

## Thời gian suy luận (02_predict.py)

| Điều kiện | TB (ms) | Median (ms) | n |
|---|---|---|---|
| C0 | 32.9 | 31.2 | 69 |
| C1 | 27.5 | 27.1 | 69 |
| C2 | 31.0 | 30.8 | 69 |
| mô phỏng (640) | 54.2 | 52.7 | 1380 |
| mô phỏng C2 (640) | 69.8 | 69.3 | 1380 |


Dòng C2 được đo trong phiên chạy riêng (sau C0/C1), nên chênh lệch thời gian với C0/C1 có thể do trạng thái GPU/nhiệt, không chỉ do điều kiện ảnh.


## Biểu đồ và ví dụ

- `outputs/charts/scatter_C0.png`, `scatter_C1.png` — GT vs dự đoán (M0, M1), đường y=x.
- `outputs/charts/confusion_C0.png`, `confusion_C1.png` — ma trận nhầm lẫn.
- `outputs/charts/m2_sensitivity.png` — độ nhạy ROI.
- `outputs/charts/error_decomposition.png` — bias vs nhiễu.

- `outputs/charts/scatter_C2.png`, `confusion_C2.png` — như trên cho C2 (phân tích bổ sung).

- `outputs/charts/timeline_1.png` — Nhiều lần đổi S0 nhất (test #005 `mangcong_Rac-Ngap-Cong-Sai-Go-03` cống 0, GT 97.4%).

- `outputs/charts/timeline_2.png` — Một cống GT đỏ (test #007 `tphcm1_20260915_132659` cống 0, GT 58.6%).

- `outputs/charts/timeline_3.png` — Một cống GT xanh (test #024 `tphcm2_20260926_181738` cống 0, GT 16.0%).

- `outputs/examples/` — 10 ảnh overlay C1 (ROI xanh lá, rác dự đoán đỏ, cống dự đoán xanh dương); ưu tiên cống GT đỏ mà M0 thiếu, sau đó theo sai số lớn nhất.


| Tệp | GT | M0 | M1 |
|---|---|---|---|
| 01_test_002_d0.jpg | 95.5 | — | 0.0 |
| 02_test_005_d0.jpg | 97.4 | — | 25.8 |
| 03_test_003_d0.jpg | 93.7 | — | 30.2 |
| 04_test_007_d0.jpg | 58.6 | — | 67.2 |
| 05_test_012_d0.jpg | 69.6 | — | 0.0 |
| 06_valid_003_d0.jpg | 93.2 | — | 0.0 |
| 07_valid_002_d1.jpg | 87.5 | — | 0.0 |
| 08_valid_007_d0.jpg | 70.4 | — | 0.0 |
| 09_valid_008_d0.jpg | 93.8 | — | 0.0 |
| 10_valid_009_d0.jpg | 69.7 | — | 0.0 |


## Phân tích bổ sung C2 — sát ảnh ESP32 thật

> **Tham khảo bổ sung — không phải kết luận.** Kết luận chính ở đầu báo cáo vẫn tính trên C1 và không đổi.

**Lý do (quyết định trước khi có bất kỳ kết quả C2 nào):** firmware dùng esp32-camera `jpeg_quality = 12`, nhưng thang của esp32-camera ngược với OpenCV (esp32-camera: số **nhỏ** = chất lượng **cao**). Ảnh ESP32 VGA thật khoảng 12–15 KB; OpenCV quality 20–30 ở 640×480 cho 13,1–16,4 KB trên ảnh tphcm của Try1. Vì vậy C1 (OpenCV q12) có lẽ khắc nghiệt hơn thực tế.

**Định nghĩa C2:** resize 640×640 INTER_AREA → JPEG OpenCV q25 → giải mã; GT/ROI rasterize ở 640×640 (giống C1, chỉ khác quality). Chuỗi mô phỏng C2: giống hệt chuỗi chính (cùng seed theo ảnh × khung, cùng mọi nhiễu), chỉ JPEG cuối lấy ngẫu nhiên q20..30 thay vì q10..15.

Kích thước JPEG ở 640×640 (69 ảnh, chỉ mô tả): C1 q12 TB 13.1 KB (median 12.8); C2 q25 TB 19.3 KB (median 19.3). 640×640 nhiều hơn 640×480 khoảng 33% pixel nên KB lớn hơn mốc VGA.

### So sánh gọn C0 / C1 / C2

C0 không có chuỗi mô phỏng. C1 = chuỗi chính (JPEG q10..15); C2 = chuỗi bổ sung (JPEG q20..30). CI bootstrap 95% (n=2000, theo cống).

| Điều kiện | Tập | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập [95% CI] | M1−M0 (cặp) | MAE M1 tất cả [95% CI] | Đổi trạng thái S0 / S2 (M1, chuỗi) | Tỷ phần MSE do bias² (M1, chuỗi) |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | gộp valid+test | 12/18 | 18 / 8 | 53 | 11.52 [6.30; 17.81] | 4.67 [1.84; 8.88] | -6.85 [-11.49; -3.18] | 13.05 [7.62; 18.89] | — (không có chuỗi) | — |
| C0 | chỉ test | 3/7 | 7 / 1 | 20 | 13.46 [4.21; 24.66] | 4.53 [1.03; 10.14] | -8.94 [-17.50; -1.84] | 9.34 [3.98; 16.07] | — (không có chuỗi) | — |
| C1 | gộp valid+test | 16/18 | 18 / 14 | 29 | 8.36 [3.20; 15.22] | 6.04 [2.46; 11.16] | -2.32 [-6.51; 0.00] | 21.80 [14.97; 29.25] | 84 / 2 | 95.0% |
| C1 | chỉ test | 5/7 | 7 / 3 | 14 | 10.94 [1.35; 23.92] | 6.14 [0.74; 15.11] | -4.80 [-13.49; 0.00] | 16.87 [6.84; 28.75] | 53 / 2 | 92.4% |
| C2 | gộp valid+test | 14/18 | 17 / 9 | 36 | 9.37 [4.45; 15.24] | 4.34 [1.93; 7.76] | -5.04 [-9.15; -1.49] | 16.41 [10.55; 22.28] | 135 / 13 | 91.2% |
| C2 | chỉ test | 3/7 | 6 / 1 | 19 | 12.23 [3.35; 22.90] | 5.29 [1.28; 11.16] | -6.93 [-15.09; -0.93] | 10.06 [4.40; 17.12] | 68 / 7 | 85.2% |


### Tiêu chí trên C2 (tham khảo bổ sung)

Cùng tiêu chí và ngưỡng đã đăng ký, áp dụng nguyên vẹn cho C2. Kết quả dưới đây **không thay thế** kết luận chính.

#### Phương pháp ROI — C2

| Tiêu chí | Gộp valid+test (C2) | Chỉ test (C2) |
|---|---|---|
| (1) M1 không thiếu ở cống GT đỏ | M1 thiếu=0 / 18 đỏ (M0 thiếu=14) → **ĐẠT** | M1 thiếu=0 / 7 đỏ (M0 thiếu=3) → **ĐẠT** |
| (2) MAE(M1) ≤ MAE(M0) trên tập M0 không thiếu | M1=4.34 vs M0=9.37 (n=36) → **ĐẠT** | M1=5.29 vs M0=12.23 (n=19) → **ĐẠT** |
| (3) Bỏ sót nghiêm trọng M1 < M0 | M1=9 vs M0=17 → **ĐẠT** | M1=1 vs M0=6 → **ĐẠT** |
| (4) MAE(M2 dịch 10%, TB 4 hướng) − MAE(M1) ≤ 5 | 16.97 − 16.41 = 0.56 → **ĐẠT** | 10.95 − 10.06 = 0.89 → **ĐẠT** |


Kết quả tham khảo ROI trên C2: ĐẠT (mọi tiêu chí đạt trên cả gộp và chỉ test).

#### Làm mượt — chuỗi C2

| Tiêu chí | Gộp valid+test (chuỗi C2) | Chỉ test (chuỗi C2) |
|---|---|---|
| (a) Tổng lần đổi trạng thái S2 ≤ 50% S0 | S2=13 vs S0=135 (ngưỡng 67.5) → **ĐẠT** | S2=7 vs S0=68 (ngưỡng 34.0) → **ĐẠT** |
| (b) MAE(S1) ≤ MAE(S0) | S1=20.14 vs S0=19.98 → **KHÔNG ĐẠT** | S1=14.65 vs S0=14.90 → **ĐẠT** |
| (c) Độ chính xác trạng thái S2 ≥ S0 | S2=71.8% vs S0=70.0% → **ĐẠT** | S2=79.1% vs S0=75.7% → **ĐẠT** |
| (d) Kiểm tra trễ bậc (đỏ ở khung 70 thứ 3) | trễ=3 khung (kỳ vọng 3) → **ĐẠT** | trễ=3 khung (kỳ vọng 3) → **ĐẠT** |


Kết quả tham khảo làm mượt trên chuỗi C2: KHÔNG KẾT LUẬN (tiêu chí b cho kết quả khác nhau giữa gộp valid+test và chỉ test).

### MAE theo cống — C2 (điểm %)

| Điều kiện | Tập | n cống | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập | M1−M0 (cặp) | MAE M1 tất cả | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | Báo động giả M0 / M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| C2 | gộp valid+test | 76 | 36 | 9.37 [4.45; 15.24] | 4.34 [1.93; 7.76] | -5.04 [-9.15; -1.49] | 16.41 [10.55; 22.28] | 14/18 | 17 / 9 | 0 / 0 |
| C2 | chỉ test | 26 | 19 | 12.23 [3.35; 22.90] | 5.29 [1.28; 11.16] | -6.93 [-15.09; -0.93] | 10.06 [4.40; 17.12] | 3/7 | 6 / 1 | 0 / 0 |
| C2 | chỉ valid | 50 | 17 | 6.18 [2.93; 10.14] | 3.27 [1.51; 5.53] | -2.91 [-5.80; -0.70] | 19.72 [11.89; 28.06] | 11/11 | 11 / 8 | 0 / 0 |


Phụ — ảnh có đúng 1 cống:

| Điều kiện | Tập | n cống | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập | M1−M0 (cặp) | MAE M1 tất cả | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | Báo động giả M0 / M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| C2 | gộp valid+test | 64 | 32 | 7.62 [3.08; 13.57] | 4.46 [1.75; 8.23] | -3.16 [-6.50; -0.79] | 16.72 [10.70; 23.57] | 13/16 | 15 / 8 | 0 / 0 |
| C2 | chỉ test | 24 | 17 | 10.22 [2.23; 19.78] | 5.78 [1.40; 12.11] | -4.44 [-10.39; -0.62] | 10.80 [4.45; 18.20] | 3/6 | 5 / 1 | 0 / 0 |
| C2 | chỉ valid | 40 | 15 | 4.68 [1.94; 7.86] | 2.97 [1.02; 5.40] | -1.71 [-4.00; -0.29] | 20.27 [11.74; 29.65] | 10/10 | 10 / 7 | 0 / 0 |


Phụ — bỏ cống < 1024 px²:

| Điều kiện | Tập | n cống | n M0 có giá trị | MAE M0 [95% CI] | MAE M1 cùng tập | M1−M0 (cặp) | MAE M1 tất cả | M0 thiếu / GT đỏ | Bỏ sót nghiêm trọng M0 / M1 | Báo động giả M0 / M1 |
|---|---|---|---|---|---|---|---|---|---|---|
| C2 | gộp valid+test | 60 | 35 | 7.97 [3.66; 13.35] | 4.39 [1.96; 7.60] | -3.57 [-6.75; -1.07] | 16.43 [10.23; 23.39] | 12/15 | 14 / 7 | 0 / 0 |
| C2 | chỉ test | 23 | 18 | 9.65 [1.80; 19.25] | 5.46 [1.16; 11.54] | -4.20 [-10.11; -0.59] | 11.27 [4.87; 19.12] | 3/6 | 5 / 1 | 0 / 0 |
| C2 | chỉ valid | 37 | 17 | 6.18 [2.93; 10.14] | 3.27 [1.51; 5.53] | -2.91 [-5.80; -0.70] | 19.64 [10.21; 30.67] | 9/9 | 9 / 6 | 0 / 0 |


### Ma trận nhầm lẫn — C2 (gộp)

**C2 — M0**

| GT \ dự đoán | xanh | vàng | đỏ | thiếu |
|---|---|---|---|---|
| xanh | 31 | 0 | 0 | 21 |
| vàng | 1 | 0 | 0 | 5 |
| đỏ | 3 | 1 | 0 | 14 |


**C2 — M1**

| GT \ dự đoán | xanh | vàng | đỏ |
|---|---|---|---|
| xanh | 51 | 1 | 0 |
| vàng | 5 | 0 | 1 |
| đỏ | 9 | 3 | 6 |


Độ nhạy ROI C2 (gộp): MAE M1 = 16.41 [10.55; 22.28]; dịch 5% TB 4 hướng = 16.54; dịch 10% TB 4 hướng = 16.97.


### Độ tin cậy — C2 (gộp)

Độ tin cậy mới là NaN ở 52 cống.

| Quy tắc | Tỷ lệ gắn cờ | MAE M1 có cờ | MAE M1 không cờ |
|---|---|---|---|
| old | 56.6% (43/76) | 16.23 | 16.65 |
| new | 21.1% (16/76) | 23.66 | 14.48 |


### Làm mượt — chuỗi C2

76 cống × 20 khung, đánh giá như chuỗi chính.

| Phương pháp | Tập | MAE S0 | MAE S1 | S1−S0 theo cống [CI] | Đổi trạng thái S0 / S1 / S2 | TB đổi/cống S0 / S2 | Cống 0 lần đổi S0 / S2 | Đúng trạng thái S0 / S1 / S2 (%) | MAE khung bị che S0 / S1 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | gộp valid+test | 19.98 | 20.14 | 0.17 [-0.62; 0.95] | 135 / 18 / 13 | 1.78 / 0.17 | 49 / 70 (của 76) | 70.0 / 70.9 / 71.8 | 22.39 / 21.98 (n=151) |
| M1 | chỉ test | 14.90 | 14.65 | -0.25 [-1.37; 1.01] | 68 / 12 / 7 | 2.62 / 0.27 | 14 / 23 (của 26) | 75.7 / 76.4 / 79.1 | 16.18 / 15.74 (n=61) |
| M1 | chỉ valid | 22.61 | 23.00 | 0.39 [-0.61; 1.38] | 67 / 6 / 6 | 1.34 / 0.12 | 35 / 47 (của 50) | 67.0 / 68.0 / 68.0 | 26.60 / 26.21 (n=90) |
| M0 | gộp valid+test | 8.87 | 8.91 | -0.13 [-0.72; 0.23] | 150 / 29 / 7 | 1.97 / 0.09 | 39 / 70 (của 76) | 36.9 / 45.1 / 47.3 | 9.68 / 10.12 (n=57) |
| M0 | chỉ test | 10.39 | 10.35 | -0.40 [-1.72; 0.45] | 68 / 8 / 3 | 2.62 / 0.12 | 9 / 24 (của 26) | 49.0 / 58.7 / 60.8 | 12.75 / 13.20 (n=26) |
| M0 | chỉ valid | 7.52 | 7.62 | 0.07 [0.01; 0.14] | 82 / 21 / 4 | 1.64 / 0.08 | 30 / 46 (của 50) | 30.6 / 38.0 / 40.2 | 7.10 / 7.54 (n=31) |


Phân rã sai số (chuỗi C2):

| Phương pháp | Tập | |bias| TB | Nhiễu TB | Tỷ phần MSE do bias² | Tỷ phần do phương sai |
|---|---|---|---|---|---|
| M1 | gộp valid+test | 18.90 | 6.22 | 91.2% | 8.8% |
| M1 | chỉ test | 14.08 | 6.83 | 85.2% | 14.8% |
| M1 | chỉ valid | 21.40 | 5.91 | 92.8% | 7.2% |
| M0 | gộp valid+test | 12.80 | 1.26 | 97.2% | 2.8% |
| M0 | chỉ test | 12.22 | 2.43 | 93.2% | 6.8% |
| M0 | chỉ valid | 13.23 | 0.40 | 99.9% | 0.1% |


## Hạn chế

- Mẫu nhỏ: 76 cống, chỉ khoảng 6 cống vàng (C1) — CI rộng, ma trận nhầm lẫn kém ổn định.
- Tập valid đã được dùng để chọn `best.pt`, nên số trên valid có thể lạc quan; vì vậy tiêu chí yêu cầu kết quả trên chỉ test cùng chiều với tập gộp.
- Nhiễu mô phỏng độc lập giữa các khung; nhiễu thực tế (mưa, bóng đổ kéo dài, rác thay đổi) tương quan theo thời gian, nên lợi ích thật của làm mượt có thể nhỏ hơn.
- Vật che hình học (hình chữ nhật) không giống người/xe thật.
- Không có ảnh tham chiếu sạch của từng camera, nên phương án ROI do AI đề xuất chưa được kiểm tra.
- ROI lấy từ polygon GT là **cận trên** của độ chính xác M1; ROI vẽ tay thực tế sẽ lệch — xem M2 để ước lượng mức suy giảm.
- C1 chỉ xấp xỉ ESP32 (resize + JPEG chất lượng thấp), không mô phỏng cảm biến, nhiễu màu hay ánh sáng yếu thật.
- Thang `jpeg_quality` của esp32-camera ngược với OpenCV (esp32-camera: số nhỏ = chất lượng cao), nên C1 (OpenCV q12) có lẽ khắc nghiệt hơn ảnh ESP32 thật; C2 (OpenCV q25) gần thực tế hơn nhưng chỉ là phân tích bổ sung.
