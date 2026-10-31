# Inference v2 — chỉ số che cống theo ROI cố định

Phần Python (`ssc-v2/inference/`) của bản v2. Đưa công thức **M1** và **certainty mới** của thí nghiệm `research/exp01_chi_so_che_cong` vào production.

## Thay đổi

| File | Nội dung |
|---|---|
| `analysis.py` | `analyze(jpeg_bytes, roi=None, *, quality_gate=False)`. Có ROI thì độ che cống = phần rác nằm trong ROI cố định của camera. Không có ROI thì dùng công thức cũ (legacy). Thêm `certainty`, cổng độ sáng và vẽ viền ROI lên ảnh phân tích. Các hàm thuần (không cần GPU): `validate_roi_polygon`, `roi_mask`, `blockage_in_roi`, `weighted_certainty`, `brightness_ok`, `draw_roi`. |
| `ai_worker.py` | Đọc `job.drain_roi`, kiểm tra polygon trước khi tải ảnh (sai thì báo fail), gọi `analyze(..., roi, quality_gate=True)`. Payload dựng bằng hàm thuần `build_result_payload()`. Giữ nguyên allowlist SSRF, chặn redirect, timeout, báo fail và tên file ảnh tất định. |
| `calibrate_roi.py` | CLI đề xuất ROI từ một ảnh sạch. Người kiểm tra preview rồi mới chạy `--apply`. |
| `tests/test_analysis_logic.py` | Test logic thuần, không cần GPU. |

`analyze(jpeg_bytes)` gọi kiểu cũ (site demo `test-WebUI-modelAI`) cho **đúng** `waste_coverage_pct`, `drain_blockage_pct` và `confidence` như bản chính. Đã kiểm trên GPU: ảnh phân tích cũng giống từng byte. Kiểu gọi này cũng **không** bật cổng độ sáng.

## Công thức

- `waste_coverage_pct`: không đổi. Bằng hợp (union) mask Trash chia diện tích ảnh, nhân 100.
- **Có ROI** (`blockage_method: "roi"`). ROI được rasterize ở kích thước ảnh gốc (`fillPoly` trên tọa độ chuẩn hóa × [w, h], cùng quy ước với exp01):
  - `drain_blockage_pct = |Trash ∩ ROI| / |ROI| × 100`, làm tròn 2 chữ số.
  - `no_trash_in_roi = (giao = 0)`.
  - `certainty` = trung bình có trọng số của confidence các instance Trash, trọng số là số pixel mask nằm trong ROI. Không có pixel rác nào trong ROI thì `certainty = null`.
  - ROI suy biến (diện tích 0) gây `ValueError`, worker báo fail.
- **Không ROI** (`blockage_method: "legacy"`):
  - Độ che cống tính theo công thức cũ trên mask Drain dự đoán. Không thấy cống thì bỏ trống.
  - `certainty` tính tương tự, trọng số là pixel nằm trong hợp mask Drain dự đoán.
  - `no_trash_in_roi` chỉ có khi đo được độ che cống.
- `confidence`: vẫn tính như cũ, tức min conf, hoặc 0.575 khi không phát hiện gì. exp01 cho thấy chỉ số này phản thông tin, nhưng vẫn gửi để tương thích.
- `certainty` thấp **chỉ là nhãn**, không chặn kết quả.

## Cổng chất lượng ảnh

Trước khi chạy model, worker tính độ sáng trung bình ảnh xám (0..255). Nếu dưới `AI_MIN_BRIGHTNESS` (mặc định **40**) thì ảnh bị loại:

- Kết quả có `usable: false` và `quality_reason: "thieu_sang"`.
- **Không chạy model** và không gửi phần trăm nào.
- `confidence` = 0.575.
- Ảnh phân tích là **ảnh gốc mã hóa lại**, có vẽ viền ROI nếu camera có ROI, để giao diện vẫn hiển thị khung hình bị loại.

Giới hạn `MAX_PIXELS` (24MP) vẫn giữ.

Trên Try1 (valid 552 + test 272 ảnh, ban ngày): **0 ảnh bị loại**. Ảnh tối nhất có độ sáng 49.6.

## Hợp đồng dữ liệu

`GET /api/ai/jobs`: mỗi job có thêm `drain_roi: { polygon: [[x,y],...], version: "<chuỗi>" }` hoặc `null`. Tọa độ chuẩn hóa 0..1, x sang phải, y xuống dưới. Polygon phải có ≥ 3 điểm số trong [0, 1]; `version` phải là chuỗi khác rỗng. Sai định dạng thì worker gọi `POST /api/ai/jobs/fail` và không tải ảnh.

`POST /api/ai/results`:

| Trường | Ảnh dùng được | Ảnh không dùng được |
|---|---|---|
| `camera_id`, `observation_id` | có | có |
| `waste_coverage_pct` | có | **không gửi** |
| `drain_blockage_pct` | có, trừ khi legacy không thấy cống | **không gửi** |
| `confidence` | legacy | 0.575 |
| `usable` | `true` | `false` |
| `quality_reason` | không gửi | `"thieu_sang"` |
| `certainty` | số 0..1 hoặc `null` | không gửi |
| `no_trash_in_roi` | có khi đo được độ che cống | không gửi |
| `blockage_method` | `"roi"` / `"legacy"` | không gửi |
| `roi_version` | `drain_roi.version` hoặc `null` | `drain_roi.version` hoặc `null` |
| `analyzed_url` | khi lưu được ảnh | khi lưu được ảnh |

Payload tất định: gửi lại cùng một job sẽ ra cùng một payload.

## Hiệu chỉnh ROI (`calibrate_roi.py`)

Chạy từ `C:\Users\ASUS\Desktop\SSC\ssc-v2\inference`. Nên chọn ảnh **ban ngày, cống sạch**, thấy rõ toàn bộ miệng cống.

**1. Đề xuất bằng model.** Lệnh dưới chỉ ghi preview, không áp dụng:

```powershell
..\..\.venv\Scripts\python.exe -B calibrate_roi.py --image C:\duong\dan\anh_sach.jpg --camera CAM01
```

Model lấy mask Drain lớn nhất, trích viền ngoài (`approxPolyDP`, epsilon 1% chu vi, tối đa 64 điểm) rồi chuẩn hóa về 0..1. Kết quả ghi vào `calibration\CAM01_<tên ảnh>_preview.jpg`, gồm ảnh có viền xanh và % diện tích ảnh, kèm file `.json` cùng tên. Lệnh in ra polygon và lệnh `--apply` chính xác cần chạy.

Nếu không thấy cống, lệnh thoát với mã 2 và gợi ý dùng `--polygon`.

**2. Nhập tay**, bỏ qua model (`source: "manual"`):

```powershell
..\..\.venv\Scripts\python.exe -B calibrate_roi.py --image C:\duong\dan\anh_sach.jpg --camera CAM01 --polygon "0.10,0.55 0.40,0.55 0.38,0.80 0.08,0.78"
```

**3. Áp dụng sau khi đã xem preview.** Dùng lại đúng lệnh ở bước 1 hoặc 2 và thêm `--apply`:

```powershell
$env:ADMIN_API_KEY = "<khóa admin>"   # nếu backend có đặt khóa
..\..\.venv\Scripts\python.exe -B calibrate_roi.py --image C:\duong\dan\anh_sach.jpg --camera CAM01 --apply
```

Lệnh gửi `PATCH {SSC_API_URL}/api/cameras/<camera_id>`, mặc định tới `http://127.0.0.1:8010`. Header là `X-API-Key: $ADMIN_API_KEY` nếu có đặt khóa. Body: `{"drain_roi": {"polygon": [...], "source": "ai"|"manual"}}`.

`--apply` **từ chối** (mã 4) trong hai trường hợp:

- chưa có preview cho cặp camera + ảnh này;
- polygon tính lại khác polygon trong preview đã xem.

Nhờ vậy chỉ polygon đã được người xem mới được áp dụng. Công cụ không bao giờ tự áp dụng.

Mã thoát của lệnh:

| Mã | Ý nghĩa |
|---|---|
| 0 | OK |
| 2 | Không thấy cống |
| 3 | Đầu vào sai |
| 4 | Áp dụng thất bại hoặc bị từ chối |

## Kiểm thử

```powershell
..\..\.venv\Scripts\python.exe -B tests\test_analysis_logic.py
```

Test không cần GPU, không gọi mạng. Có test thất bại thì mã thoát khác 0.

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `AI_MIN_BRIGHTNESS` | `40` | Ngưỡng độ sáng (0..255) |
| `AI_MODEL_PATH` | | Đường dẫn trọng số model |
| `AI_DETECT_CONF` | | Ngưỡng confidence phát hiện |
| `SSC_API_URL` | `http://127.0.0.1:8010` | Địa chỉ backend |
| `AI_API_KEY` | | Khóa của worker |
| `ADMIN_API_KEY` | | Khóa admin, dùng cho `calibrate_roi --apply` |
| `SSC_IMAGES_DIR` | | Thư mục lưu ảnh |
