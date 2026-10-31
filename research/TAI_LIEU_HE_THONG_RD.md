# Tài liệu hệ thống — SSC (HV Tech): bản thử nghiệm & phát triển (R&D)

> Ngày viết: 2026-10-20. Đối tượng đọc chính: một AI/kỹ sư mới vào dự án, cần nắm cấu trúc, logic và trạng thái thật của hệ thống.
> Mọi đường dẫn tính từ thư mục gốc dự án `C:\Users\ASUS\Desktop\SSC` (gọi tắt `<root>`).
> **Quy ước trung thực:** mục 9 ghi rõ cái gì đã được đo, cái gì mới chỉ chạy được, cái gì chưa kiểm. Đừng suy diễn vượt quá mục đó.

---

## 0. Đọc nhanh (TL;DR)

- **Sản phẩm:** hệ thống camera + AI đánh giá **mức rác ở khu vực xung quanh** và **tình trạng miệng cống** trên đường phố, hiển thị trên bản đồ, cảnh báo sớm nguy cơ ngập cục bộ. Đội HV Tech (THPT chuyên Hùng Vương), thi Sustainable Society Challenge 2026 (SDG 11). Phạm vi hiện tại: **ban ngày, thời tiết tốt, 1 camera = 1 miệng cống**.
- **Hệ thống chính (đang chạy thật, KHÔNG được sửa):** ESP32-CAM → backend Node → AI worker Python (YOLO26s-seg) → web React/Leaflet.
- **Bản R&D:** mọi thứ mới nằm ở thư mục riêng, không đụng hệ thống chính:
  1. `ssc-v2/` — bản sao hệ thống chính + logic mới cho **chỉ số che cống** (vùng ROI cố định, làm mượt trung vị + trễ).
  2. `research/exp01_chi_so_che_cong/` — thí nghiệm kiểm chứng logic che cống (cơ sở của ssc-v2).
  3. `research/exp02_ve_rac_len_ban_do/` — thí nghiệm **vẽ vùng rác từ ảnh camera lên bản đồ thật (lat/lon)** bằng bảng ArUco; kèm `webtest/` là trang web thử nghiệm dùng được bằng điện thoại.
- **Trạng thái:** logic chạy thông đầu-cuối và qua test tự động; số đo độ chính xác mới có trên **ảnh giả lập**; **chưa có bảng sai số đo bằng ảnh thật ngoài hiện trường**. Model AI còn yếu (bỏ sót rác). Chưa tích hợp exp02 vào `ssc-v2`.

---

## 1. Bài toán và phạm vi

- Rác che miệng cống ở TP.HCM gây ngập cục bộ; rác ngoài đường còn ảnh hưởng mỹ quan đô thị và nhiều vấn đề khác. Sản phẩm đo **rác của cả môi trường xung quanh** và **cống**, rồi suy ra chỉ số/cảnh báo — không chỉ riêng cống.
- Khách hàng giả định (bối cảnh thiết kế): công ty môi trường — cần **đơn giản, dễ hiểu, hiệu quả**.
- Giai đoạn: **nghiên cứu/phát triển + thi**, chưa bán. Cuộc thi chỉ yêu cầu ở mức ý tưởng; ưu tiên **độ chính xác của con số trong phạm vi nghiên cứu hẹp** hơn là hoàn thiện sản phẩm.
- Không được tuyên bố: "dự báo ngập", "thời gian thực" (hệ thống chụp định kỳ ~60 s, trạng thái cống có độ trễ do làm mượt).

---

## 2. Bản đồ thư mục

```
<root>/
  ssc-road-alerts/        HỆ THỐNG CHÍNH: backend Node (server/), frontend React (src/), firmware ESP32, docs, tests   [KHÔNG SỬA]
  inference/              HỆ THỐNG CHÍNH: AI worker Python (ai_worker.py, analysis.py)                              [KHÔNG SỬA]
  test-WebUI-modelAI/     HỆ THỐNG CHÍNH: site demo cho giám khảo (FastAPI :8100 + web tĩnh)                         [KHÔNG SỬA]
  runs/segment/runs/train/baseline_v1_rev2/weights/best.pt   Trọng số model đang dùng (đọc dùng chung, chỉ đọc)
  datasets/Try1/          Dataset train/val/test (chia 70/20/10 theo nhóm chống leakage)
  .venv/                  Python venv dùng chung (ultralytics, torch, fastapi, opencv, pillow...)
  ssc-v2/                 BẢN SAO R&D của 3 khối trên (cổng riêng) + logic mới   (xem mục 4)
  research/
    exp01_chi_so_che_cong/        Thí nghiệm chỉ số che cống                     (mục 5)
    exp02_ve_rac_len_ban_do/      Thí nghiệm vẽ rác lên bản đồ + webtest         (mục 6, 7, 8)
    TAI_LIEU_HE_THONG_RD.md       File này
  .claude/CLAUDE.md, .claude/agents/   Quy trình làm việc với AI (xem mục 12)
  HV Tech - Thuyết minh.docx/.pdf      Thuyết minh dự án (nguồn gốc nghiệp vụ)
  Label-app/, Anh_Lon_xon/, test1/, a.py, ...   Công cụ gán nhãn bên thứ ba, ảnh thô, file tạp — không phải lõi
```

Bảng cổng (không được đụng nhau):

| Thành phần | Hệ thống chính | ssc-v2 | exp02 webtest |
|---|---|---|---|
| Backend HTTP | 8000 | 8010 | 8120 (FastAPI) |
| Backend HTTPS (cho modem) | 8443 (Tailscale Funnel → đây) | 8453 | — |
| Frontend Vite dev | 5173 | 5174 | — (1 file HTML do FastAPI phục vụ) |
| Site demo FastAPI | 8100 | 8110 | — |

---

## 3. Hệ thống chính (bối cảnh — để hiểu cái R&D bám vào)

### 3.1 Luồng dữ liệu

```
ESP32-CAM (640x480 JPEG, ~60 s/ảnh, modem 4G A7670C)
   │  POST qua Tailscale Funnel :8443 (idempotent, observation_id lưu NVS, retry backoff)
   ▼
Backend Node  (ssc-road-alerts/server/, Node>=22, không framework, không DB; lưu JSON atomic + hàng chờ ghi)
   │  tạo job (pending) ──────────────►  AI worker Python  (inference/ai_worker.py)
   │                                        poll GET /api/ai/jobs mỗi 3 s
   │  ◄── POST /api/ai/results (hoặc /jobs/fail)   YOLO26s-seg → analyze() → số liệu + ảnh overlay
   ▼
Frontend React 19 + TS + Vite + React-Leaflet  (poll 30 s) → bản đồ, mức độ, cảnh báo tuyến đường
```

### 3.2 Backend Node (`ssc-road-alerts/server/`)
- File chính: `app.js` (router), `service.js`, `store.js` (JSON store, ghi nguyên tử), `aggregation.js` (tổng hợp theo tuyến), `config.js` (ngưỡng), `validation.js`, `weather.js` (Open-Meteo), `ai-worker.js` (bản Node cũ, đã thay bởi worker Python).
- API chính: `/api/health`, `/api/policy`, `/api/weather/cameras`, `/api/esp32/observations` (thiết bị gửi ảnh), `/api/cameras` (CRUD, admin), `/api/ai/jobs` (GET), `/api/ai/results` (POST), `/api/ai/jobs/fail|retry` (POST), `/api/road-alerts`, `/api/test/simulate`. API key theo vai `admin/device/ai`.
- Máy trạng thái observation: `pending → processed | needs_review | failed` (+ retry). Kết quả chỉ được **áp (`applied`) lên `latest_analysis`** khi: mới hơn kết quả đang dùng, ≤ 15 phút kể từ `captured_at`, cùng tuyến.
- Ngưỡng nhãn rác `POLICY.waste` = **1/5/10/20 %** (low/medium/high/critical); ngưỡng che cống 20/50/70/90 (bản chính).
- **Tổng hợp tuyến dùng TRUNG BÌNH** các camera còn tươi (kèm `waste_max_pct`/`flood_max_pct`, số camera) — `docs/BUOC1-GIAI-PHAU-HE-THONG.md` ghi MAX là **đã cũ**.
- Mưa (Open-Meteo): xác suất ≥ 50% hoặc ≥ 0.2 mm/h → đẩy mức nghiêm trọng lên một bậc. `data_quality`: `fresh/partial/unknown/unconfigured`; `normal + unknown` = "chưa biết", **không phải "an toàn"**.

### 3.3 AI worker & model (`inference/`)
- Model: **YOLO26s-seg**, 2 lớp (0 `Trash`, 1 `Drain`), `imgsz=1024`, `conf=0.25`, `retina_masks`. File `runs/segment/runs/train/baseline_v1_rev2/weights/best.pt`.
- Chỉ số val (mask): baseline_v1_rev2 mAP50 0.459, mAP50-95 0.246, **P 0.638, R 0.438**. → bỏ sót nhiều rác. Rủi ro lệch miền: ảnh train là ảnh điện thoại độ phân giải cao, ảnh ESP32 là 640×480 nén nặng.
- `analysis.py` (bản chính): `waste_coverage_pct = |union mask Trash| / |ảnh| × 100`; `drain_blockage_pct = |Trash ∩ Drain| / |Drain| × 100` (không thấy Drain → bỏ trống, không gửi 0); `confidence = min` conf các object (0.575 khi không phát hiện gì). Ảnh > 24 MP bị từ chối.
- Chỉ chạy **1 worker, 1 backend**. Allowlist URL chống SSRF; ảnh overlay ghi vào `server/data/images/` tên uuid5 tất định.

### 3.4 Frontend (`ssc-road-alerts/src/`)
React 19 + TypeScript + Vite + React-Leaflet. `components/map`, `components/monitoring`, `hooks/` (`useMapData`, `useWeather`, `useAlertHandling`), `services/` (`mapService`, `monitoringService`, `normalize*`), `models/`, `config/` (`severity.ts`, `monitoring.ts`, `basemaps.ts`). Poll 30 s; trạng thái xác nhận/phiếu lưu `localStorage`.

---

## 4. `ssc-v2/` — bản sao R&D + logic che cống mới

Tạo 2026-10-11, **bản sao nguyên vẹn** của hệ thống chính, dữ liệu riêng, cổng riêng (bảng cổng ở mục 2). Trọng số model dùng chung (chỉ đọc). ESP32 thật **vẫn gửi vào hệ thống chính**, firmware không sửa. Chuyển sang v2 sau này = trỏ thiết bị/worker/frontend sang v2 (hướng dẫn trong `ssc-v2/README-V2.md`).

Ba thay đổi logic (lý do: exp01):

1. **ROI cố định theo camera** — `cameras[].drain_roi = { polygon:[[x,y]..] (3–64 điểm, chuẩn hoá 0..1), source:"ai"|"manual", calibrated_at }`. Server đặt `calibrated_at` (tăng ngặt) làm **phiên bản ROI**. Công thức mới: `drain_blockage_pct = |Trash ∩ ROI| / |ROI| × 100` (`blockage_method:"roi"`); camera chưa có ROI dùng công thức cũ (`"legacy"`). Lý do: công thức cũ cần model *nhìn thấy* cống, mà cống bị rác che kín thì model không thấy → "không có giá trị". ROI tạo bằng `ssc-v2/inference/calibrate_roi.py` (đề xuất bằng model hoặc nhập tay; **bắt buộc xem preview rồi mới `--apply`**; không bao giờ tự áp dụng).
2. **Làm mượt theo thời gian** (`drain_state` theo camera): cửa sổ 5 lần đo gần nhất (`usable`, cùng `roi_version`, trong 15 phút) → **trung vị** (cần ≥ 3 lần, dưới đó `unknown/collecting`) → ngưỡng có **trễ (hysteresis)**:

   | Trạng thái trước | → `clean` | → `watch` | → `clear` |
   |---|---|---|---|
   | không/`unknown`/`clear` | v ≥ 50 | 20 ≤ v < 50 | v < 20 |
   | `watch` | v ≥ 50 | 12 ≤ v < 50 | v < 12 |
   | `clean` | v ≥ 35 | 12 ≤ v < 35 | v < 12 |

   (Tên trạng thái theo mã nguồn; ý nghĩa suy từ ngưỡng, che càng nhiều càng cao: `clear` = thấp, `watch` = trung bình/theo dõi, `clean` = cao/cần dọn. **Frontend `ssc-v2/ssc-road-alerts/src` hiện chưa đọc `drain_state`/`drain_summary`** — chỉ backend trả; UI còn dùng `latest_analysis` và đã đổi nhãn "Mức che miệng cống".) Dữ liệu cũ hơn 15 phút hoặc camera mất kết nối → trình bày `unknown/stale`, không ghi lại file. Tuyến có `drain_summary` (đếm theo trạng thái, `worst_state`).
3. **Bỏ gating confidence cũ** — `confidence = min` phản thông tin (càng nhiều rác càng thấp → hầu hết ảnh có rác vào `needs_review`). v2: mọi kết quả → `processed`; thêm `certainty` (trung bình có trọng số pixel-trong-ROI của conf các instance Trash) **chỉ làm nhãn**; `low_certainty = certainty < 0.5`.

Thêm: **cổng chất lượng ảnh** — độ sáng trung bình xám < 40 → `usable:false, quality_reason:"thieu_sang"`, không chạy model, không gửi phần trăm, không cập nhật `latest_analysis`/`drain_state`. Đổi nhãn UI "Tỉ lệ ngập" → **"Mức che miệng cống"** (tên trường `drain_blockage_pct`, `flood*` giữ nguyên; "Nguy cơ ngập" là khái niệm khác).

Hợp đồng job/result chi tiết: `ssc-v2/README-V2.md`, `ssc-v2/inference/README-INFERENCE-V2.md`. Test: `npm test` (vitest, 39 test đạt khi kiểm), `ssc-v2/inference/tests/test_analysis_logic.py` (19 test đạt khi kiểm, không cần GPU).

---

## 5. `research/exp01_chi_so_che_cong/` — thí nghiệm che cống

Script đánh số `01_ground_truth.py … 05_report.py`, `common.py`, `config.py`, `tests/`, kết quả `REPORT.md` (tự sinh, **không sửa tay**). Tiêu chí được đăng ký **trước** khi chạy, không chỉnh sau.
- Điều kiện ảnh: C0 = ảnh gốc, C1 = giống ESP32 (640×640, JPEG OpenCV q12), C2 = q25 (sát ESP32 thật hơn vì thang `jpeg_quality` của esp32-camera ngược OpenCV). Kết luận chính tính trên C1.
- **Kết luận đã có:** ROI cố định (M1) **ĐẠT** mọi tiêu chí trên cả gộp và chỉ-test (M0 thiếu giá trị ở 47/76 cống; MAE M0 8.36 vs M1 6.04 trên tập M0 có giá trị; dịch ROI 10% gần như không làm sai thêm). Làm mượt: **KHÔNG KẾT LUẬN về MAE** (tiêu chí b khác nhau giữa các tập) nhưng **giảm hẳn nhấp nháy** (số lần đổi trạng thái 84 → 2). Độ trễ khi nhảy bậc: 3 khung.
- Hạn chế (đọc kỹ): mẫu nhỏ (76 cống, ~6 cống "vàng"); phần lớn sai số là **bias của model** (≈ 95% MSE) — làm mượt chỉ giảm được phần phương sai; ROI lấy từ GT là cận trên (ROI vẽ tay sẽ lệch); nhiễu mô phỏng độc lập giữa các khung.

---

## 6. `research/exp02_ve_rac_len_ban_do/` — vẽ vùng rác lên bản đồ

### 6.1 Ý tưởng
Camera **đặt cố định** nhìn xuống mặt đất. Đặt **một bảng ArUco** (kích thước thật biết trước) lên mặt đất trong tầm nhìn, chụp **một ảnh hiệu chỉnh**. Từ ảnh đó giải được **vị trí + hướng camera so với bảng** (pose). Sau đó mỗi điểm ảnh → một tia → giao với **mặt phẳng đất** → toạ độ mét quanh bảng → xoay theo hướng la bàn của bảng → đổi sang lat/lon. Vùng rác (mask do model YOLO) được chiếu thành đa giác trên bản đồ, có **diện tích (m²)**. Con người chỉ làm **một lần**: đặt bảng, nhập 1 số (cạnh thật của bảng, mm), chấm vị trí + hướng bảng trên bản đồ. Các ảnh sau tự động.

### 6.2 Modules lõi (tất cả ở thư mục gốc exp02)
| File | Vai trò |
|---|---|
| `config.py` | Hằng số: marker `DICT_4X4_50 id=0`; bảng in `PRINT_MARKER_SIZE_MM=250` (A3); FOV mặc định 66°; cỡ bảng demo 400 mm; bán kính Trái Đất |
| `camera_model.py` | Pinhole không méo: `f = (đường chéo/2)/tan(FOV/2)`, tâm ảnh làm điểm chính; hệ camera OpenCV (X phải, Y xuống, Z trước); 4 góc marker trong hệ marker |
| `calibrate_aruco.py` | Dò marker (`CORNER_REFINE_SUBPIX`) + `solvePnPGeneric` với `SOLVEPNP_IPPE_SQUARE`; chọn nghiệm theo sai số reprojection; trả `R,t`, khối `quality`, cảnh báo; CLI lưu `calibration/<camera_id>.json` |
| `calib_quality.py` | Quy tắc chất lượng (xem 6.4) |
| `project_mask.py` | Chiếu pixel → mặt đất → ENU(m) → lat/lon; biên pixel; footprint camera nhìn thấy |
| `generate_marker.py` | Sinh trang in bảng (PDF/PNG), tự chọn khổ giấy theo cỡ bảng |
| `make_synthetic_test.py`, `run_demo_vehtruong.py`, `model_demo/`, `viewer/` | Ảnh giả lập, demo đầu-cuối, demo mask do model thật, viewer Leaflet độc lập |
| `stress_test/`, `size_test/` | Hai thí nghiệm đo (6.5) |
| `docs/HUONG_DAN_IN_BANG.md`, `docs/HUONG_DAN_THU_O_NHA.md` | Hướng dẫn in bảng / thử ở nhà (**HUONG_DAN_THU_O_NHA hiện còn viết theo luồng chép ảnh sang laptop, chưa cập nhật cho luồng điện thoại**) |
| `tests/` | `test_logic`, `test_calibration_v2`, `test_projection_v2`, `test_marker_print`, `test_azimuth_fov` |

### 6.3 Toán học (đủ để tái hiện)
- **FOV từ EXIF**: `FOV_chéo = 2·atan(43.267 / (2·f35))` với `f35` = `FocalLengthIn35mmFilm`; không có EXIF → mặc định 66° (camera ESP32) + cảnh báo (điện thoại thường ~70–85°). Người dùng có thể nhập tay.
- **Pose**: `R,t` = marker → camera. Tâm camera trong hệ marker `C = −Rᵀ t`. Hệ marker: mặt phẳng bảng là mặt đất (z=0), +Y là một cạnh, +X nằm **bên phải của +Y khi nhìn từ trên xuống**.
- **Giao tia–đất**: `dir = Rᵀ · ray_cam`, `s = −C.z / dir.z`, hợp lệ khi `s>0` và `dir.z` không ≈ 0 (điểm trời/chân trời bị bỏ và đếm trong `dropped_points`).
- **Hướng la bàn**: gọi β = phương vị (0°=Bắc, 90°=Đông) của trục +Y của bảng. `E = x·cosβ + y·sinβ`, `N = −x·sinβ + y·cosβ`. (β=0 ⇒ +X=Đông, +Y=Bắc.)
- **Mét → lat/lon**: xấp xỉ mặt phẳng quanh bảng (`dlat = N/R`, `dlon = E/(R·cos lat)`), đủ cho vài trăm mét.
- **Diện tích**: mask → **biên pixel** (mỗi pixel là ô vuông, tâm ở toạ độ nguyên; hỗ trợ lỗ) rồi chiếu từng đỉnh; diện tích đa giác trên ảnh = số pixel của mask chính xác (đường `findContours` đi qua tâm pixel biên nên co ~0.5 px → diện tích hụt 4–7% ở vật nhỏ, v2 đã bỏ). Có khoá **tỉ lệ khung hình** (lệch > 1% so với ảnh hiệu chỉnh ⇒ từ chối, vì khác tỉ lệ thường là crop và làm méo fx/fy).
- **Footprint** (`ground_footprint_polygon`): phần mặt đất camera nhìn thấy (cắt ở `max_range_m`, mặc định 12 m) — dùng để người đặt bảng đối chiếu bằng mắt.

### 6.4 Quy tắc chất lượng hiệu chỉnh (đã chốt với người dùng; **không thêm cờ/điều kiện mới**)
- **Cạnh ngắn nhất của bảng trên ảnh < 50 px ⇒ CHẶN, không lưu hiệu chỉnh** (CLI exit 3; webtest trả 422). ≥ 50 px cho qua. Không có cờ ghi đè. Muốn đạt: chụp gần hơn hoặc **dùng bảng lớn hơn** (cỡ bảng chọn theo từng camera).
- Công thức cỡ bảng: `S ≥ N·D / (616·cosθ)` với `N=50`, S = cạnh bảng (mm... cùng đơn vị D), D = khoảng cách camera→bảng, θ = góc giữa hướng nhìn và pháp tuyến bảng; hằng 616 ≈ f (px) của camera 640×480 FOV 66°. Ví dụ bảng 250 mm đạt 50 px tới ~2,2 m ở 45° và ~2,9 m ở 20°; bảng A4 150 mm tới ~1,3 m ở 45°, ~1,8 m nhìn thẳng.
- Chỉ **cảnh báo** (không chặn): ảnh mờ (độ nét chuẩn hoá < 0.35), JPEG chất lượng thấp, **nghi lật nghiệm** (tỉ lệ sai số hai nghiệm IPPE < 3), độ cao camera nhập tay lệch > 20%.
- **Nghiệm lật:** IPPE trả hai nghiệm phản chiếu **cùng độ cao** → độ cao camera **không** chọn được nghiệm đúng (đã chứng minh sai giả thuyết ban đầu, có test) — chỉ kiểm tra chéo. Lời giải theo quyết định người dùng: bảng đủ lớn (≥ 50 px) + người kiểm bằng mắt ở bước xem trước (footprint + vị trí camera có hợp lý không).
- Con số duy nhất người dùng nhập tay: **cạnh thật của bảng (mm), đo bằng thước sau khi in** (không nhập số lý thuyết).

### 6.5 Số đo đã có (ảnh GIẢ LẬP — mặt đất phẳng lý tưởng, không méo, mask hoàn hảo)
- `stress_test/REPORT.md` (marker 200 mm, JPEG q20–30 ≈ ESP32): điểm gãy là **độ chính xác pose**, không phải khả năng dò; mờ lấy nét là nhiễu nguy hiểm nhất; sai số reprojection **không** phân biệt pose đúng/sai/lật (nên không dùng làm ngưỡng); lỗi lật chiếm ~13–15% mẫu dò được, tập trung ở marker nhỏ (< 25 px). SUBPIX (biến thể B) đẩy điểm "an toàn" ra 2–3 m (so với 1–2 m của code cũ).
- `size_test/REPORT.md` (số của **hành vi cũ** `legacy=True`, tiêu chí đặt trước): diện tích T1/T2 **KHÔNG ĐẠT** (vật ≥ 0.3 m ở 1–3 m sai ≤ 7.5%, 5 m ≤ 20.6%, 8 m ≤ 34%); vị trí T3 **ĐẠT** (≤ 0.067 m ở 1–3 m); đường lat/lon ↔ mét khớp 1e-6%. Nguyên nhân: sai số pose từ marker nhỏ ở xa; JPEG q12 lật pose 3/10 biến thể. Sau sửa v2 (SUBPIX + IPPE + biên pixel): vật 0,3 m trong 2 m lệch tâm 0,2–1,4 cm, diện tích +4…+11% (điều kiện lý tưởng).
- **Vật có chiều cao** bị vẽ phóng to/kéo dài ra xa camera (mô hình chỉ biết mặt đất): hộp 0,3×0,3×0,2 m ở 1–8 m phóng +32% → +177%; mép gần (chân vật) vẫn đúng ≤ 3 cm. Quy ước: vị trí theo mép gần, m² coi là "vết chiếu trên ảnh".
- Model trên ảnh thật: bỏ sót rác ở 2/3 ảnh đường phố thử; suy luận CPU ≈ 0.55 s/ảnh (12 nhân).

---

## 7. `research/exp02_ve_rac_len_ban_do/webtest/` — trang thử nghiệm (dùng được bằng điện thoại)

Mục đích: người dùng tự kiểm xem luồng "ảnh có bảng → hiệu chỉnh → ảnh có rác → vùng rác trên bản đồ" có khả thi và đúng không, bằng **ảnh điện thoại thật**. Độc lập hoàn toàn với hệ thống chính và `ssc-v2`.

### 7.1 Thành phần
```
webtest/
  server.py          FastAPI (uvicorn). Toàn bộ API + phục vụ file tĩnh
  store.py           Lưu trữ file (ghi nguyên tử: file tạm + os.replace). Đường dẫn đọc từ env mỗi lần gọi (test đổi được)
  imaging.py         Giải mã/tiền xử lý ảnh dùng chung cho calibrate và observe; vẽ overlay; mã hoá base64
  test_server.py     Test tự chạy (python -B test_server.py; không cần pytest). 171 kiểm tra đạt khi viết tài liệu
  run_tailscale.ps1  Khởi động server chỉ nghe địa chỉ Tailscale + in 2 đường dẫn kèm mã
  web/index.html     Trang laptop: Leaflet, 4 bước, bản đồ tự cập nhật
  web/phone.html     Trang điện thoại: 2 nút chụp, tiến độ, kết quả
  data/              (sinh ra lúc chạy) pending/, inbox/, observations.json, access_code.txt
```
Hiệu chỉnh đã lưu: `exp02/calibration/WEB-DEMO.json` (camera cố định mã `WEB-DEMO`; **một camera, một hiệu chỉnh tại một thời điểm**).

### 7.2 Tiền xử lý ảnh (`imaging.decode_upload`) — quan trọng cho hiểu logic
Giải mã bằng PIL (chỉ JPEG/PNG; kiểm bằng giải mã thật), **đọc `FocalLengthIn35mmFilm` từ EXIF TRƯỚC khi xoay**, áp EXIF orientation, đổi BGR, nếu cạnh dài > 2048 px thì thu nhỏ giữ tỉ lệ (INTER_AREA). Chặn ảnh > 120 MP (decompression bomb), tải lên tối đa 25 MB. `image_size` mọi nơi là kích thước **sau** xử lý. Ảnh gửi qua Zalo/Messenger bị nén và mất EXIF → rơi về FOV mặc định → vị trí/kích thước lệch. iPhone: ảnh HEIC không dùng được, cần "Tương thích nhất" (JPEG).

### 7.3 API (mọi lỗi dạng `{"ok":false,"error":"<tiếng Việt>"}`)
Mọi `/api/*` (trừ `/api/health`) cần header **`X-Access-Code: <mã 6 số>`** (so sánh hằng thời gian; thiếu/sai → 401; sai quá 10 lần/60 s từ một địa chỉ → 429 trong 60 s). Không cần mã: `GET /`, `GET /phone`, `GET /web/*`, `GET /api/health`. `/docs`, `/openapi.json` đã tắt.

| Endpoint | Tác dụng |
|---|---|
| `GET /api/health` | `model_loaded`, `calibrated` |
| `GET /api/status` | `calibrated`, `observation_count`, `latest_observation_id`, `inbox_count`, `latest_inbox_id` (rẻ; trang gọi mỗi 3 s) |
| `POST /api/inbox` (multipart `photo`) | **Điện thoại gửi ảnh có bảng**; lưu **nguyên bytes gốc** (giữ EXIF) ở `data/inbox/<id>.bin`+`.json`; trả `inbox_id`, `has_focal`, `image_size`… Giữ tối đa 10, xoá sau 24 h |
| `GET /api/inbox` | Danh sách ảnh chờ + thumbnail 240 px |
| `POST /api/calibrate` | Dò bảng: nhận **đúng một** trong `photo` hoặc `inbox_id`; `marker_size_mm` (mặc định 250; 10–5000), `fov_deg` (tuỳ chọn; 1–179). Trả `calibration_id` (kết quả **chưa lưu**, lưu ở `data/pending/`), `side_px_min`, `fov_deg`/`fov_source` (`input|exif|default`), cảnh báo, ảnh overlay (viền bảng xanh lá, +Y xanh dương, +X đỏ). Bảng < 50 px ⇒ 422 kèm ảnh overlay |
| `GET /api/footprint` | Vùng mặt đất camera thấy + điểm bảng + điểm camera (theo `calibration_id` chưa lưu + `lat,lon,azimuth_deg`, hoặc theo hiệu chỉnh đã lưu) |
| `POST /api/calibration/save` | Lưu hiệu chỉnh từ `calibration_id` + `lat/lon/azimuth_deg` |
| `GET /api/calibration` | Hiệu chỉnh đã lưu (để tải lại trang vẫn vẽ lại được) |
| `POST /api/observe` (multipart `photo`) | Ảnh có rác: **409 nếu chưa hiệu chỉnh**; **422 nếu khác tỉ lệ khung** (>1%) ảnh hiệu chỉnh. Chạy YOLO (chỉ lớp Trash), mask → biên pixel → làm gọn (`approxPolyDP`, eps = max(1 px, 0.2% chu vi); bỏ vùng < 0.05% ảnh) → chiếu → GeoJSON. Trả `regions` (FeatureCollection; mỗi feature `area_m2`, `area_px`, `confidence` TB, `kind:"trash"`), `total_area_m2`, `n_instances`, ảnh model đã khoanh (`annotated_jpg_b64`), `inference_ms`, `warnings`, `dropped_points`; lưu vào `observations.json` (tối đa 50) |
| `GET/DELETE /api/observations` | Lịch sử các lần gửi / xoá hết |

Model nạp lười + làm nóng khi khởi động; trọng số lấy từ `WEBTEST_MODEL_PATH` hoặc đường dẫn mặc định (mục 3.3).

### 7.4 Luồng sử dụng thực tế
1. **In bảng** (A3 250 mm, hoặc A4 150 mm dự phòng: `outputs/marker_A4_150mm.pdf`), in 100% tắt "Fit to page", **đo cạnh vùng mã bằng thước**, dán lên tấm cứng, đặt **nằm phẳng trên sàn**.
2. Laptop chạy `run_tailscale.ps1` (server nghe duy nhất IP Tailscale, KHÔNG nghe `0.0.0.0`/Wi-Fi nhà). Điện thoại bật Tailscale (cùng tài khoản), mở `http://<ip-tailscale>:8120/phone#<mã>`.
3. Điện thoại **cố định trên giá**, ống kính chính 1×, không zoom, giữ nguyên hướng dọc/ngang. Bấm "Chụp ảnh hiệu chỉnh" → ảnh vào `inbox`.
4. Laptop `http://<ip>:8120/#<mã>`: **Bước 1** chọn ảnh từ điện thoại (hoặc chọn tệp từ máy) + cạnh bảng đo được (+ FOV nếu EXIF không có) → "Dò bảng". **Bước 2** chấm vị trí bảng trên bản đồ, kéo mũi tên cho đúng hướng +Y (la bàn). **Bước 3** xem vùng xanh (mặt đất camera thấy) có khớp thực tế không → "Lưu hiệu chỉnh". Bước 4 chỉ mở sau khi lưu.
5. Điện thoại "Chụp ảnh rác" (cùng vị trí, cùng hướng) hoặc laptop chọn tệp ở Bước 4. Bản đồ laptop **tự cập nhật ~3 s** (poll `/api/status`; khi `latest_observation_id` đổi mới tải `/api/observations`). Vùng rác: **đỏ = lần mới nhất, vàng hổ phách = các lần cũ**; bấm vào vùng xem m² + độ tin cậy.
6. Kiểm độ đúng: đặt vật ở các điểm đo sẵn (0,5 m, 1 m từ tâm bảng theo +Y, +X), so với vị trí vẽ. **Tiêu chí khả thi đặt trước:** lệch ≤ ~0,2 m trong ~2 m quanh bảng = đạt; 0,2–0,4 m tạm chấp nhận; > 0,4 m = chưa đạt.

### 7.5 Giao diện
- **Trang laptop (`web/index.html`)**: một file HTML+CSS+JS thuần; Leaflet 1.9.4 từ CDN `unpkg` (cần Internet; nền OSM, `maxZoom 24`, `maxNativeZoom 19`). Thanh trên cùng: trạng thái Máy chủ / Hiệu chỉnh / Model AI. Bản đồ + bảng điều khiển 4 bước (bước chưa mở bị làm mờ, `pointer-events:none`). Lớp bản đồ: footprint (xanh), điểm bảng, điểm camera, mũi tên hướng (kéo được), lớp rác theo lần gửi. Khối "Ảnh từ điện thoại" ở Bước 1 (thumbnail, giờ, có/không thông tin ống kính). Toast "Có ảnh mới từ điện thoại". Hộp nhập mã khi thiếu/sai.
- **Trang điện thoại (`web/phone.html`)**: nút lớn "Chụp ảnh hiệu chỉnh (có bảng)" và "Chụp ảnh rác" (`<input type=file accept="image/*" capture="environment">` → mở **camera gốc của máy**, không dùng `getUserMedia`; kèm liên kết "chọn ảnh có sẵn"), thanh tiến độ tải lên (XHR, timeout 120 s), dòng trạng thái "Laptop: đã hiệu chỉnh / CHƯA hiệu chỉnh", hiển thị ảnh model đã khoanh + số vùng + tổng m² + cảnh báo. **Không có bản đồ** (bản đồ xem trên laptop).
- Mã truy cập: lấy từ `#<6 số>` trên URL (rồi xoá khỏi URL), hoặc `localStorage["webtest_code"]`, hoặc hộp nhập.

### 7.6 Bảo mật & mạng (đặt cho mạng Tailscale riêng)
Mạng Tailscale (tailnet) chỉ gồm laptop + điện thoại của chủ. Lớp bảo vệ: chỉ nghe IP Tailscale, mã 6 số (tự sinh, lưu `data/access_code.txt`), giới hạn dò mã, giới hạn kích thước/số lượng, regex 16-hex cho mọi id (chống path traversal), bắt lỗi đường dẫn lạ. `auditor` đã kiểm: không lộ file ngoài `web/`, mã không lọt vào log/URL gửi lên máy chủ. Giới hạn đã biết: gửi ảnh lớn kèm mã sai có thể thấy lỗi mạng thay vì 401 (kết nối bị đóng trước khi đọc hết body); `/api/status` parse JSON mỗi lần (rẻ với dữ liệu thực); trang tải Leaflet từ CDN.

---

## 8. Logic hợp nhất (hệ thống chính + ssc-v2 + exp02) — hướng tích hợp (CHƯA làm)

- exp02 hiện **chỉ có trong `research/`**; chưa gắn vào backend/frontend của `ssc-v2`. Điểm gắn dự kiến: worker (`analysis.py`) đã sinh mask Trash; thêm bước chiếu bằng `project_mask` nếu camera có hiệu chỉnh (`calibration/<camera_id>.json`), và frontend vẽ GeoJSON lên bản đồ hiện có. Quyết định thiết kế của người dùng: **chứng minh khả thi bằng webtest trước, tích hợp sau**.
- Mô hình "1 camera = 1 cống" của v2 và "1 camera cố định + bảng" của exp02 cùng yêu cầu **camera đứng yên sau hiệu chỉnh**. Nếu camera bị xê dịch, hiệu chỉnh sai mà hệ thống **không tự phát hiện** (không có cách tự kiểm; chỉ có kiểm bằng mắt ở lúc hiệu chỉnh).

---

## 9. Trạng thái đánh giá (trung thực)

| Hạng mục | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|
| Che cống bằng ROI cố định | **Đạt** trên dữ liệu thử | exp01 REPORT; mẫu nhỏ, ROI từ GT là cận trên |
| Làm mượt trung vị + trễ | **Giảm nhấp nháy** rõ (84→2 lần đổi); **không kết luận** về MAE | exp01 REPORT |
| Hợp đồng/logic ssc-v2 | Backend + worker chạy thông, test đạt; **frontend chưa hiển thị `drain_state`** | 39 test Node + 19 test Python khi kiểm; chạy end-to-end với ROI giả |
| Hiệu chỉnh bằng ArUco, chiếu lên bản đồ | **Đúng trên ảnh giả lập** (lệch tâm cm, diện tích +4…+11%) | stress_test, size_test, test tự động |
| Độ chính xác trên **ảnh thật** | **CHƯA đo** | Có một lần chạy thử của người dùng trên webtest (1 hiệu chỉnh, 1 lần gửi, model khoanh 2 vùng ≈ 0,16 m²); đó là smoke test, **không có** bảng sai số so với vị trí đo bằng thước. Hiệu chỉnh đó dùng FOV mặc định 66° và toạ độ/hướng mặc định → không phải phép đo |
| Luồng điện thoại → laptop (Tailscale, 4G) | Kết nối **đã thử thông** (người dùng xác nhận mở được trang qua 4G); trang `/phone` đã qua test tự động + kiểm trình duyệt ngầm; **chưa có báo cáo chụp thật đầy đủ** | test_server 171 kiểm tra đạt; auditor kiểm HTTP thật + Chrome |
| Chất lượng nhận diện rác của model | **Yếu** | R=0.44, bỏ sót ở 2/3 ảnh đường phố thử; cải thiện model là việc người dùng tự làm |

---

## 10. Giới hạn đã biết & rủi ro (đừng quên khi dùng số liệu)

1. **Mặt đất phẳng tuyệt đối.** Vật cao bị phóng to/kéo dài ra xa camera; diện tích là "vết chiếu trên ảnh", không phải diện tích thật.
2. **Camera phải đứng yên** từ ảnh hiệu chỉnh tới mọi ảnh sau; ảnh khác tỉ lệ khung bị từ chối.
3. **FOV là điểm yếu số 1 nếu thiếu EXIF** (mặc định 66° là của ESP32 OV2640; điện thoại 70–85°). Sai FOV ⇒ sai vị trí/kích thước. Camera thật cần calibrate checkerboard.
4. **Hướng bảng và vị trí bảng do người đặt bằng mắt trên bản đồ**; độ chính xác tuyệt đối trên bản đồ phụ thuộc cách đặt. Cái kiểm được là **khoảng cách tương đối quanh bảng**.
5. **Bảng nhỏ ⇒ pose kém tin cậy và có thể lật.** Chặn < 50 px; sai số reprojection không phát hiện được ca hỏng.
6. **Lệch miền ESP32**: model train trên ảnh điện thoại chất lượng cao; ảnh ESP32 640×480 nén nặng.
7. **Ngoài phạm vi**: ban đêm, mưa/phản chiếu, nhiều camera/cống trên cùng ảnh, camera đặt xa (cần bảng lớn hơn nhiều), mặt đường dốc/lồi lõm.
8. **Tồn đọng bảo mật chưa quyết (hệ thống chính, ngoài phạm vi R&D):** dev server Vite của hệ thống chính chạy `--host 0.0.0.0` (lộ LAN) và CORS phản chiếu origin; `ssc-v2` chưa đổi. Người dùng chưa trả lời.
9. **Tài liệu cũ cần biết:** `ssc-road-alerts/docs/BUOC1-GIAI-PHAU-HE-THONG.md` (tổng hợp MAX — thực tế là TRUNG BÌNH; ngưỡng 20/50/70/90 cũng cũ), `exp02/docs/HUONG_DAN_THU_O_NHA.md` (luồng chép ảnh sang laptop — chưa cập nhật cho điện thoại). Giải pháp Homography đo m² bằng điểm tay từng bị hoãn (2026-09-21) và được thay bằng hướng ArUco của exp02.

---

## 11. Cách chạy nhanh

```powershell
# Test logic exp02 (từ research\exp02_ve_rac_len_ban_do)
..\..\.venv\Scripts\python.exe -B tests\test_logic.py
# Webtest (từ research\exp02_ve_rac_len_ban_do\webtest)
..\..\..\.venv\Scripts\python.exe -B test_server.py        # test
.\run_tailscale.ps1                                         # chạy thật qua Tailscale (in đường dẫn kèm mã)
# hoặc cục bộ: ..\..\..\.venv\Scripts\python.exe -B -m uvicorn server:app --host 127.0.0.1 --port 8120
# ssc-v2 (từ ssc-v2\ssc-road-alerts)
npm run backend    # 8010      |   npm run dev   # 5174   |   npm test
# ssc-v2 worker (từ ssc-v2\inference)
..\..\.venv\Scripts\python.exe -B ai_worker.py
```
Luôn dùng `.venv` của gốc và cờ `-B` (không sinh `__pycache__`). Windows console cp1252 có thể lỗi tiếng Việt: đặt `PYTHONIOENCODING=utf-8` khi chạy script tạm.

In bảng: `generate_marker.py` (mặc định A3 250 mm → `outputs/marker_A3.*`; `--size-mm 150` → `outputs/marker_A4_150mm.*`; tự chọn khổ giấy nhỏ nhất đủ chứa bảng + lề trắng + thước + ô điền số đo).

---

## 12. Quy tắc làm việc với dự án (bắt buộc với AI tiếp quản)

- **Không sửa hệ thống chính** (`ssc-road-alerts/`, `inference/`, `test-WebUI-modelAI/`, trọng số `runs/`). Mọi R&D làm trên bản sao/thư mục riêng, **cổng khác**. Chỉ khi đạt mới đổi hướng sang bản mới.
- **Giữ hệ thống đơn giản.** Người dùng đã nhiều lần nói "đừng thêm bất cứ gì nữa": không thêm cờ/điều kiện/ngoại lệ mới khi chưa được yêu cầu. Nhập tay đúng **một con số** (cạnh bảng, mm).
- **Điểm chưa chắc về lý thuyết/logic ⇒ hỏi người dùng trước**, không tự chốt vào kế hoạch.
- **Trung thực:** trình bày cả giới hạn; không tuyên bố "dự báo ngập" hay "thời gian thực"; báo rõ kết quả thất bại; tiêu chí đo đặt trước khi chạy, không chỉnh sau.
- `.claude/CLAUDE.md`: vai "AI Tech Lead", trả lời task theo 3 bước (Phân tích → Blueprint → Xin duyệt), **không sửa file hoặc giao sub-agent khi chưa có "Approved"**. Sub-agent ở `.claude/agents/`: `researcher` (chỉ đọc), `builder` (cài đặt), `auditor` (kiểm toán, chạy test). Khi giao việc song song: định nghĩa hợp đồng trước, phân file không chồng nhau, mỗi agent một nhóm file.
- Ngôn ngữ giao diện/lỗi/tài liệu: **tiếng Việt**.

---

## 13. Bảng tra nhanh khái niệm

| Thuật ngữ | Nghĩa |
|---|---|
| Hiệu chỉnh (calibration) | Giải pose camera so với bảng ArUco từ một ảnh; lưu `R,t,K, image_size, marker_latlon, azimuth_deg, FOV` |
| Pose lật / nghiệm lật | Hai nghiệm phản chiếu của bài toán PnP cho mặt phẳng; cùng độ cao, lệch hướng |
| ROI (cống) | Đa giác chuẩn hoá 0..1 trên ảnh camera, cố định theo camera, đánh dấu miệng cống |
| `drain_state` | Trạng thái cống đã làm mượt: `clear` (thông) / `watch` (theo dõi) / `clean` (cần dọn) / `unknown` |
| `usable` | Ảnh có đủ điều kiện (đủ sáng…) để tính chỉ số; `false` ⇒ không gửi phần trăm |
| certainty | Độ tin cậy **chỉ làm nhãn**, tính theo pixel trong ROI; khác `confidence` cũ (min) |
| footprint | Vùng mặt đất camera nhìn thấy, vẽ để người đặt bảng đối chiếu |
| inbox | Hộp ảnh điện thoại gửi chờ laptop dùng ở Bước 1 |
| observation | Một lần gửi ảnh rác: vùng + tổng m² + thời điểm |
| tailnet | Mạng riêng Tailscale gồm các thiết bị cùng tài khoản |

---

## 14. Việc còn mở (không tự làm khi chưa được duyệt)

1. Chụp thật bằng điện thoại và **lập bảng sai số vị trí** (0,5 m/1 m quanh bảng, tiêu chí ở 7.4) — việc quan trọng nhất để kết luận khả thi.
2. Cập nhật `exp02/docs/HUONG_DAN_THU_O_NHA.md` cho luồng điện thoại + Tailscale.
3. (Tuỳ chọn) chọn nhiều ảnh một lượt ở Bước 4 của trang laptop.
4. Tích hợp lớp bản đồ vào `ssc-v2` sau khi webtest đạt.
5. Cải thiện model (người dùng tự làm); hiệu chỉnh ống kính camera thật (checkerboard).
6. Quyết định bảo mật dev server của hệ thống chính (mục 10.8).
7. Hosting công khai cho link thi (chưa quyết; Tailscale Funnel đang dùng cổng 8443/8444 cho hệ thống chính/demo giám khảo).
