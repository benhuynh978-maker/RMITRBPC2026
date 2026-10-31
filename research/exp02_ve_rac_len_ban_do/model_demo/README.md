# exp02 / model_demo — Vẽ rác lên bản đồ bằng KẾT QUẢ MODEL AI thật

Bản mở rộng của demo `run_demo_vehtruong.py`: thay polygon **nhãn tay** bằng mask do model
YOLO26s-seg (`baseline_v1_rev2/weights/best.pt`) dự đoán, rồi chiếu lên bản đồ qua
calibration `DEMO-CAM`. Polygon nhãn tay của cùng ảnh cũng được chiếu song song để so sánh.

> **DEMO — pose giả lập không khớp vật lý với ảnh, chỉ thử luồng.** Pose `DEMO-CAM` lấy từ
> ảnh giả lập (`make_synthetic_test.py`), toạ độ marker (10.7769, 106.7009) là giả định.
> Ảnh Try1 không được chụp bằng camera đó, nên toạ độ trên bản đồ KHÔNG phải vị trí rác thật.

Toàn bộ file của thư mục này nằm trong `model_demo/`. Script chỉ **đọc** các file dùng chung
(`config.py`, `project_mask.py`, `calibration/DEMO-CAM.json`), dataset và weights, và chỉ ghi
vào `model_demo/outputs/`.

## Cấu trúc

```
model_demo/
  run_demo_model.py    Chọn ảnh -> suy luận model -> union mask Trash -> vùng biên pixel -> chiếu -> GeoJSON
  test_model_demo.py   Test nhanh (CPU, không GPU) chuỗi mask -> vùng -> GeoJSON + chọn ảnh bằng nhãn
  viewer.html          Trang Leaflet: lớp model (đỏ) / nhãn tay (xanh), dropdown chọn ảnh, điểm
                       "Bảng đánh dấu" + "Camera (tính từ hiệu chỉnh)"
  outputs/             Sinh ra lúc chạy (xoá an toàn, chạy lại sẽ tạo lại)
    <id>_model.geojson   FeatureCollection polygon từ model (source "model")
    <id>_label.geojson   FeatureCollection polygon nhãn tay (source "label")
    marker.geojson       Point vị trí BẢNG ĐÁNH DẤU (marker_latlon)
    camera_position.geojson  Point vị trí camera tính từ R, t của hiệu chỉnh
    index.json           Danh sách ảnh + tên 2 file điểm cho viewer
    summary.json         Tham số, thời gian, bảng so sánh, cảnh báo chiếu
```

## Cách chạy

Chạy từ thư mục `research/exp02_ve_rac_len_ban_do/`, luôn dùng venv của project kèm `-B`.
Cần có sẵn `calibration/DEMO-CAM.json` (tạo bởi `run_demo_vehtruong.py`; script này KHÔNG tự
tạo lại hay ghi đè).

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B model_demo/test_model_demo.py
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B model_demo/run_demo_model.py
```

Script dùng GPU nếu có (CUDA), nếu không sẽ chạy CPU (chậm hơn). Không gọi `model.val`,
không `save=True` nên không sinh thư mục `runs/`.

Xem bản đồ (server phải chạy tại thư mục exp02 để đường dẫn `./outputs/` đúng):

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B -m http.server 8772
```

Mở `http://localhost:8772/model_demo/viewer.html`, xem xong thì dừng server.

## Tham số

| Bước | Tham số |
|---|---|
| Suy luận (giống production `inference/analysis.py`, chỉ tham khảo, không import) | `imgsz=1024`, `conf=0.25`, `retina_masks=True`, mask `> 0.5`, chỉ lớp 0 (Trash) |
| Gộp mask | union (OR) mọi instance Trash ở độ phân giải ảnh gốc |
| Tách vùng | `project_mask.mask_to_pixel_boundary_polygons` (BIÊN PIXEL: diện tích đa giác khớp đúng số pixel mask, có lỗ, 4-liên thông) |
| Bỏ vùng nhỏ | diện tích viền ngoài `< 0.05%` diện tích ảnh (`MIN_AREA_FRAC = 0.0005`) |
| Giảm đỉnh | `cv2.approxPolyDP(closed=True)`, `epsilon = max(1.0 px, 0.002 × chu vi viền ngoài)` (làm lệch viền tối đa ~epsilon) |
| Chiếu | `project_mask_to_geojson(mask=..., boundary="pixel", allow_aspect_mismatch=True)`; `allow_aspect_mismatch` CHỈ DÙNG CHO DEMO |
| Pixel -> chuẩn hoá | `x/W, y/H` (cùng quy ước nhãn YOLO), rồi `project_mask.project_mask_to_geojson` |

Thuộc tính mỗi feature: `image`, `contour_idx`, `area_px` (số pixel mask thật của vùng, đã
trừ lỗ), `n_vertices_px`, `n_holes` (model), `source` (`model`/`label`), `confidence` (trung bình confidence các
instance có mask giao vùng đó; `null` với nhãn tay), `camera_id`, `label`.

## Ảnh dùng (chọn tất định, quy tắc mới 2026-10-12)

`select_image_stems()` (chỉ đọc nhãn, không cần GPU):

1. Chỉ xét ảnh trong `datasets/Try1/test` có tên bắt đầu bằng `tphcm` hoặc `ssc` (cảnh đường/cống).
2. Loại ảnh không có polygon Trash hợp lệ (nhãn trống hoặc chỉ có lớp Drain) và ảnh thiếu file `.jpg`.
3. Xếp theo % diện tích ảnh bị phủ bởi HỢP mọi polygon Trash (tô lưới 512x512), giảm dần; hoà thì theo tên.
4. Lấy `N_IMAGES = 3` ảnh đầu. Nếu thiếu thì bổ sung ảnh nguồn khác (g1lop...) theo cùng cách xếp hạng, cuối cùng mới
   tới ảnh demo cũ `config.DEMO_LABELED_IMAGE_STEM`.

Kết quả trên 59 ảnh tphcm/ssc có nhãn Trash: `tphcm2_20260926_181955` (13.52%, 6 polygon),
`ssc6_069` (7.71%, 5 polygon), `tphcm2_20260926_174928` (2.75%, 4 polygon).

## Kết quả (chạy lại 2026-10-13 bằng code mới: biên pixel, ảnh đường/cống; RTX 4050 Laptop GPU)

So sánh trên **ảnh** (pixel, 1024×1024), không phải trên bản đồ:

| Ảnh | Instance Trash (conf) | Polygon model | Polygon nhãn (gốc / sau union) | Diện tích model (%) | Diện tích nhãn (%) | IoU mask |
|---|---|---|---|---|---|---|
| tphcm2_20260926_181955 | 1 (0.67) | 0 | 6 / 5 | 161 px (0.015%) | 140 314 px (13.38%) | **0.000** |
| ssc6_069 | 0 | 0 | 5 / 5 | 0 | 79 494 px (7.58%) | **0.000** |
| tphcm2_20260926_174928 | 7 (0.27–0.56) | 6 | 4 / 3 | 26 895 px (2.565%) | 28 377 px (2.71%) | **0.712** |

**Nhận xét quan trọng:** trên ảnh cảnh đường/cống thật (khác với bộ ảnh g1lop trong nhà dùng ở
lần chạy trước), model **bỏ sót gần hết rác ở 2/3 ảnh** (IoU 0). Ảnh đầu: model chỉ thấy 1 mảnh
rất nhỏ (161 px, dưới ngưỡng 0,05% diện tích ảnh nên bị loại). Ảnh thứ hai: không phát hiện gì.
Chỉ ảnh thứ ba khớp khá (0.71). Đây là giới hạn thật của model (recall thấp trên ảnh thực tế, phù hợp
số đo recall ~0.44 ở thí nghiệm exp01), KHÔNG phải lỗi luồng xử lý. Ảnh ở lần chạy cũ (g1lop)
cho IoU cao hơn vì cảnh chụp gần, rác lớn, rõ.

- "Polygon nhãn gốc" = số polygon Trash trong file nhãn. "Sau union" = số contour khi tô các
  polygon nhãn rồi tách bằng cùng quy tắc như model (để so số polygon cho công bằng).
- Thời gian suy luận (GPU, mỗi ảnh chạy 1 lần, số chỉ mang tính tham khảo): nạp model 191 ms;
  warm-up lần đầu 2 047 ms (không tính); 40.6 / 39.6 / 59.5 ms mỗi ảnh (predict + chép mask về CPU).
- Cảnh báo chất lượng hiệu chỉnh của `DEMO-CAM` được in ra theo quy tắc hiện hành. Từ 2026-10-13
  `DEMO-CAM.json` được tạo lại bằng bảng giả lập 400 mm (~59 px, `config.DEMO_MARKER_SIZE_MM`) nên không còn cảnh báo cỡ
  bảng; `run_demo_model.py` đã được chạy lại ngày 2026-10-13 với `DEMO-CAM` mới (số IoU/diện tích trên ảnh không đổi
  vì không phụ thuộc hiệu chỉnh). Hiệu chỉnh demo này chỉ để thử luồng, không dùng để đo.

## Giới hạn

- **Lỗ (holes) được giữ** (bản mới): polygon GeoJSON có vòng trong. Pixel chỉ chạm góc được coi là tách rời
  (4-liên thông). Đoạn `approxPolyDP` rút gọn làm diện tích polygon lệch nhẹ so với `area_px`.
- **Pose không khớp ảnh.** Như cảnh báo ở đầu trang, ảnh Try1 không chụp bằng camera
  `DEMO-CAM`.
- **Tỉ lệ khung hình khác lúc hiệu chỉnh.** Calibration tạo ở 640×480 (4:3), ảnh Try1 là 1024×1024 (1:1).
  `project_mask` mặc định báo `ValueError` khi lệch tỉ lệ > 1%. Demo này bật `allow_aspect_mismatch=True`
  (CHỈ DEMO): dùng 1 hệ số co giãn chung cho fx, fy (giữ góc mở đường chéo, không méo pixel) và in 1 cảnh báo
  mỗi tiến trình (gom trong `summary.json > projection_warnings`). Không đúng với camera vật lý thật.
- `approxPolyDP` làm viền polygon lệch tối đa khoảng `epsilon` pixel so với mask gốc.
- IoU, diện tích và số polygon được tính trên ảnh, không phải m² thật (homography/đo m² thật
  đang tạm gác).
- Chỉ có 3 ảnh, mỗi ảnh chạy 1 lần, nên đây không phải đánh giá model. Cả 3 ảnh hiện thuộc nguồn
  đường/cống (`tphcm2_*`, `ssc6_*`), nhưng vẫn là ảnh chụp tay từ nhiều góc, không phải camera cố định.
- `marker.geojson` là vị trí **bảng đánh dấu** (`marker_latlon`); `camera_position.geojson` là vị trí camera
  tính từ R, t (`project_mask.camera_position_geojson`). `camera_point_geojson` cũ chỉ còn là alias của marker.

## Dọn dẹp

```
rm -rf model_demo/outputs
```
