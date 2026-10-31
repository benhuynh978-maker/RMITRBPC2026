# exp02 — Vẽ vùng rác lên bản đồ (hiệu chỉnh bằng marker ArUco)

## Mục tiêu

Thử nghiệm chạy THÔNG cả luồng: lấy vùng rác (polygon mask, từ model YOLO26s-seg hoặc —
như demo này — từ nhãn tay) trên ảnh camera cố định, rồi "chiếu" nó lên bản đồ thật
(kinh độ/vĩ độ) bằng cách hiệu chỉnh vị trí + góc nhìn camera qua 1 bảng đánh dấu ArUco
đặt tại hiện trường.

Giai đoạn này **KHÔNG** đặt mục tiêu chính xác tuyệt đối (xem mục Giới hạn bên dưới) —
mục tiêu là có một luồng xử lý chạy được đầu-cuối, vẽ ra bản đồ để xem thử, và chuẩn bị
sẵn công cụ (`calibrate_aruco.py`, `project_mask.py`) để dùng ngay khi có ảnh bảng ArUco
chụp thật tại hiện trường.

Vì **chưa có ảnh bảng thật**, repo này tự tạo ảnh giả lập
(`make_synthetic_test.py`) để kiểm thử toàn luồng ngay bây giờ.

## Cấu trúc thư mục

```
exp02_ve_rac_len_ban_do/
  config.py              Cấu hình: đường dẫn, marker, camera giả định, toạ độ demo
  camera_model.py         Mô hình camera pinhole: camera_matrix, pixel_to_ray, góc marker
  generate_marker.py      Tạo trang in ArUco (mặc định A3 250 mm -> outputs/marker_A3.*; --size-mm: cỡ khác, tự chọn khổ giấy); --legacy-a4: bản cũ
  calibrate_aruco.py      Dò marker (SUBPIX) + IPPE_SQUARE ra pose camera, khối quality + cảnh báo, lưu calibration/
  calib_quality.py        Quy tắc cảnh báo chất lượng hiệu chỉnh (cỡ bảng 50 px, mơ hồ/lật, độ nét, JPEG)
  project_mask.py         Core: chiếu polygon/mask -> GeoJSON (lon,lat) và mét; biên pixel (`boundary`),
                          khoá tỉ lệ khung hình (`allow_aspect_mismatch` chỉ cho demo), vị trí camera/bảng
  make_synthetic_test.py  Tự tạo ảnh giả lập (mặt đất caro + marker ở pose biết trước; cỡ bảng là tham số)
  run_demo_vehtruong.py   Demo cuối: chạy hết luồng, xuất outputs/demo_*.geojson
  viewer/index.html       Trang Leaflet độc lập, xem thử kết quả trên bản đồ OSM
  tests/test_logic.py     Test thuần hình học, không cần ảnh/model
  tests/test_calibration_v2.py  Test hiệu chỉnh v2: cảnh báo, nghiệm lật, độ cao chỉ kiểm tra chéo, legacy, CLI
  tests/test_projection_v2.py   Test biên pixel/diện tích, khoá tỉ lệ khung, vị trí camera, parse nhãn
  tests/test_marker_print.py  Test trang in A3 + ca --size-mm 500/1000 (thư mục tạm): px/PDF, DPI, phát hiện marker, lề trắng
  docs/HUONG_DAN_IN_BANG.md   Hướng dẫn từng bước: in A3, kiểm bằng thước, dán, chụp ảnh, cỡ bảng theo khoảng cách
  stress_test/            Báo cáo độ bền nhận diện/pose theo khoảng cách, góc, chất lượng JPEG (REPORT.md)
  size_test/              Báo cáo sai số đo diện tích/vị trí rác giả lập (REPORT.md)
  model_demo/             Demo chiếu mask do model YOLO thật lên bản đồ (README.md)
  webtest/                Trang thử nghiệm: tải ảnh hiệu chỉnh + ảnh có rác, vẽ vùng rác lên bản đồ (server.py FastAPI cổng 8120,
                          web/index.html Leaflet; xem webtest/README.md)
  docs/HUONG_DAN_THU_O_NHA.md  Hướng dẫn thử bằng điện thoại cố định ở nhà (kèm bảng ghi sai số)
  tests/test_azimuth_fov.py    Test hướng bảng (azimuth), góc mở ống kính (FOV), vùng camera nhìn thấy
  outputs/                Sinh ra lúc chạy (ảnh, geojson, pose đáp án) - KHÔNG commit nội dung giả
  calibration/            Sinh ra lúc chạy (file hiệu chỉnh từng camera, dạng <camera_id>.json)
```

## Cách chạy từng bước

Luôn dùng đúng venv của project, kèm `-B` (không sinh `__pycache__`):

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B <script>.py
```

Chạy từ bên trong thư mục `research/exp02_ve_rac_len_ban_do/`.

### 1) Test logic thuần (không cần ảnh)

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B tests/test_logic.py
```

Kiểm tra `pixel_to_ray`, giao tia với mặt đất phẳng, và quy tắc đổi mét→lat/lon.

### 2) Tạo marker để in ra giấy (A3 mặc định, cỡ khác bằng `--size-mm`)

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B generate_marker.py
```

Ra `outputs/marker_A3.pdf` (khổ A3 dọc, 297×420 mm), `outputs/marker_A3.png` (300 dpi,
3508×4961 px) và `outputs/marker_A3_preview.png` (ảnh xem nhanh). Marker ArUco `DICT_4X4_50`
id=0, **cạnh vùng mã đen 250 mm** (`config.PRINT_MARKER_SIZE_MM`), đặt giữa trang, giấy trắng
quanh bảng làm vùng yên tĩnh. Dưới bảng có dòng nhắc in 100%, thước chuẩn 100 mm và ô ghi số đo tay.

- Mỗi module marker là số nguyên pixel (492 px = 41,66 mm) nên cạnh vùng mã thực sau làm tròn là
  2952 px = **249,94 mm** (lệch −0,06 mm so với 250 mm, nhỏ hơn 1 pixel in).
- **In đúng "Kích thước thật / 100% / Actual size", tắt "Fit to page"; đo lại bằng thước sau khi in**
  (cạnh vùng mã phải ≈ 250 mm, thước in kèm phải đúng 100 mm). Chi tiết từng bước (in, dán lên
  tấm cứng, chụp ảnh hiệu chỉnh, cỡ bảng tối thiểu theo khoảng cách): `docs/HUONG_DAN_IN_BANG.md`.
- `config.MARKER_SIZE_MM = 200` vẫn là cỡ bảng trong ảnh GIẢ LẬP (`make_synthetic_test.py`) mà các
  test cũ dựa vào. Khi hiệu chỉnh bằng ảnh THẬT của bảng A3, phải khai kích thước thật của bảng
  (250 mm, hoặc số đo bằng thước nếu khác), không dùng mặc định 200 mm.
- **Cỡ bảng khác**: `generate_marker.py --size-mm <cạnh vùng mã, mm>` (mặc định 250). Máy tự chọn khổ
  giấy dọc nhỏ nhất trong A4/A3/A2/A1/A0 đủ chứa bảng + lề trắng (≥ 23 mm mỗi bên; bảng > 250 mm thì
  lề = cạnh/6) + chữ/thước/ô điền; lớn hơn A0 (bảng ≳ 630 mm) thì sinh trang khổ lớn/bạt đúng tỉ lệ vật lý
  (PDF MediaBox đúng mm). Tên file `outputs/marker_<khổ>_<cỡ>mm.pdf/.png` (250 mm khổ A3 vẫn là
  `marker_A3.*`, nội dung không đổi). Ví dụ `--size-mm 500` → `marker_A0_500mm.*`, `--size-mm 1000` →
  `marker_Custom_1000mm.*`. Trang ghi cỡ vùng mã, thước kiểm tra (100 mm; 500 mm với bảng ≥ 500 mm) và ô điền
  số đo thật; module làm tròn xuống số nguyên pixel (cạnh thực sau làm tròn in ra và ghi trên trang).
- Bản cũ (tương thích): `generate_marker.py --legacy-a4` ra `outputs/marker_to_print.png`
  (vùng mã 200 mm; cả tờ ~267 mm nên thực ra không vừa A4).
- Test: `python -B tests/test_marker_print.py`.

### 3) Tạo ảnh giả lập (khi chưa có ảnh thật)

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B make_synthetic_test.py
```

Ra `outputs/synthetic_scene.png` (ảnh mặt đất caro + marker, bảng 200 mm) và
`outputs/pose_su_thuc.json` (đáp án pose camera đã dùng để vẽ ảnh — dùng để đối chiếu; có `marker_size_mm`
đúng cỡ đã vẽ). Hai file này được các test cũ đọc làm đáp án nên giữ bảng 200 mm.
Tham số: `--marker-size-mm <mm>` (mặc định 200) và `--demo` (bảng 400 mm = `config.DEMO_MARKER_SIZE_MM`,
ghi vào TÊN FILE RIÊNG `outputs/demo_scene.png` + `outputs/demo_pose_su_thuc.json`, không đụng hai file trên).

### 4) Hiệu chỉnh camera bằng marker (ảnh giả lập hoặc ảnh thật)

**Chỉ cần nhập MỘT con số: cạnh thật của bảng (mm), đo bằng thước: `--marker-size-mm <số>`.**

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B calibrate_aruco.py ^
  --image outputs/demo_scene.png --camera-id DEMO-CAM ^
  --lat 10.7769 --lon 106.7009 --source synthetic ^
  --marker-size-mm 400
```

**Quy tắc chặn duy nhất: cạnh ngắn nhất của bảng trên ảnh < 50 px thì công cụ KHÔNG lưu file hiệu chỉnh**,
in lỗi "Bảng chỉ chiếm X px (<50 px): không đủ tin cậy, hãy dùng bảng lớn hơn hoặc chụp gần hơn" và thoát mã 3.
Từ 50 px trở lên: lưu bình thường (mã 0). Không còn mức 30 px và không còn cờ ghi đè. (Dùng như thư viện thì
`detect_and_solve_pnp` không raise vì bảng nhỏ, chỉ thêm cảnh báo; việc chặn nằm ở CLI.) Các cảnh báo khác (ảnh mờ,
nghi lật, JPEG thấp, độ cao kiểm tra chéo) giữ nguyên, chỉ cảnh báo, không chặn.

Ảnh giả lập cũ `outputs/synthetic_scene.png` dùng bảng 200 mm chỉ rộng ~30 px, nên bị chặn (mã 3) —
đúng chủ ý; để hiệu chỉnh demo dùng ảnh bảng 400 mm (`outputs/demo_scene.png`, ~59 px) như trên.

Khi có ảnh THẬT chụp bảng A3 tại hiện trường, đổi `--image` sang ảnh đó, `--camera-id` sang mã camera thật,
`--lat/--lon` sang toạ độ ĐO THẬT của marker, `--source aruco`, `--marker-size-mm` sang cạnh thật đo bằng
thước (mặc định `config.PRINT_MARKER_SIZE_MM` = 250 mm). Bảng cần lớn tới đâu để đạt ≥ 50 px: công thức
`S ≥ 50·D / (616·cos θ)` (D: khoảng cách camera→bảng theo đường nhìn, θ: góc giữa hướng nhìn và pháp tuyến
bảng):

| D | θ = 20° | θ = 45° | θ = 65° |
|---|---|---|---|
| 2 m | 180 mm | 230 mm | 390 mm |
| 3 m | 260 mm | 350 mm | 580 mm |
| 4 m | 350 mm | 460 mm | 770 mm |
| 5 m | 440 mm | 580 mm | 970 mm |
| 6 m | 520 mm | 690 mm | 1160 mm |
| 8 m | 700 mm | 920 mm | 1540 mm |

Ví dụ: bảng 250 mm đạt 50 px tới **D ≈ 2,2 m ở 45°**, **≈ 2,9 m ở 20°**; camera cao 3 m, bảng cách chân cột
3 m (θ = 45°, D ≈ 4,2 m) cần bảng ≈ 0,5 m; camera cao 6 m, bảng cách chân cột 6 m cần ≈ 1 m. Chụp thử ở nhà
với bảng A3 250 mm nên chụp trong khoảng **~2 m**.

Kết quả lưu vào `calibration/<camera_id>.json`, kèm sai số reprojection (pixel) in ra
màn hình — càng nhỏ càng tốt, chưa yêu cầu ngưỡng cụ thể ở giai đoạn thử nghiệm này.

### 5) Chạy demo cuối (toàn bộ luồng)

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B run_demo_vehtruong.py
```

Script này tự làm lại bước 3+4 cho `DEMO-CAM` với bảng **400 mm** (`config.DEMO_MARKER_SIZE_MM`; cạnh bảng
trên ảnh demo ≈ 59 px ≥ 50 px nên `DEMO-CAM.json` không còn cảnh báo cỡ bảng; ảnh/đáp án ghi vào
`outputs/demo_scene.png` + `outputs/demo_pose_su_thuc.json`, KHÔNG ghi đè `synthetic_scene.png`/`pose_su_thuc.json`
200 mm mà các test khác đọc). Sau đó lấy 1 ảnh thật có nhãn tay lớp
"Trash" từ `datasets/Try1/test` (chỉ đọc, không sửa), chiếu polygon đó qua calibration
của `DEMO-CAM`, và xuất:
- `outputs/demo_rac.geojson` — vùng rác (MultiPolygon, toạ độ lon/lat; đọc đủ mọi polygon Trash của ảnh)
- `outputs/demo_marker.geojson` — vị trí bảng đánh dấu (Point)
- `outputs/demo_camera_position.geojson` — vị trí camera tính từ hiệu chỉnh (Point)
- `calibration/DEMO-CAM.json` — hiệu chỉnh demo (`model_demo/run_demo_model.py` đọc file này; đã chạy lại
  model_demo ngày 2026-10-13 sau khi đổi bảng demo sang 400 mm; xem `model_demo/README.md`)
- (`outputs/demo_camera.geojson` là file cũ của lần chạy đầu, không còn được ghi; viewer chỉ dùng làm dự phòng)

Cuối cùng in ra bảng toạ độ các đỉnh polygon để kiểm tra bằng mắt (không ở giữa Thái
Bình Dương, không quá xa camera).

### 6) Xem thử trên bản đồ

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B -m http.server 8765
```

Chạy lệnh trên **tại thư mục `exp02_ve_rac_len_ban_do/`** (không phải trong `viewer/`),
rồi mở trình duyệt: `http://localhost:8765/viewer/index.html`.

Nhớ dừng server (Ctrl+C, hoặc kill tiến trình đang lắng nghe cổng 8765) sau khi xem xong.

## Giới hạn (đọc kỹ trước khi dùng số liệu)

- **Camera chưa calibrate thật**: `camera_matrix` suy từ góc mở ống kính GIẢ ĐỊNH
  (`config.DIAGONAL_FOV_DEG = 66°`, tham khảo thông số OV2640 — không phải số đo thật).
  Khi có camera thật, nên calibrate bằng checkerboard chuẩn để có số chính xác hơn.
- **Mặt đất coi như phẳng tuyệt đối**, không có số đo độ cao vật thể — mọi điểm mask được
  coi như nằm trên cùng mặt phẳng chứa marker. Rác chất đống cao sẽ bị tính sai vị trí.
- **Không có compass thật**: quy ước trục X marker ≈ hướng Đông, trục Y marker ≈ hướng Bắc
  là ĐƠN GIẢN HOÁ cho demo, không đo hướng la bàn thật tại hiện trường. Khi triển khai thật,
  cần đo hướng marker thật (hoặc gắn thêm la bàn/GPS) để quy đổi đúng hướng.
- **Đổi mét→độ dùng công thức xấp xỉ mặt phẳng**, chỉ đúng tốt trong phạm vi vài trăm mét
  quanh marker — không dùng cho khoảng cách lớn.
- **Toạ độ demo (10.7769, 106.7009) là GIẢ ĐỊNH**, không phải vị trí thật của bất kỳ cống/
  camera nào trong project — không tìm thấy GPS thật nào được ghi lại tại thời điểm viết
  exp02 này.
- **Ảnh/pose trong `run_demo_vehtruong.py` không khớp vật lý với nhau**: polygon rác lấy
  từ 1 ảnh thật (dataset Try1), nhưng pose camera lấy từ ảnh giả lập (`DEMO-CAM`) — hai thứ
  không liên quan về mặt hình học thật. Mục đích demo chỉ là kiểm tra luồng xử lý chạy
  thông + toạ độ ra hợp lý (gần camera), KHÔNG phải vị trí rác thật ngoài đời.
- **Bảng A3 250 mm chỉ đủ cho camera ở gần** (≥ 50 px tới ~2,2 m ở 45°, ~2,9 m ở 20°; xem bảng cỡ bảng ở
  mục 4 và `docs/HUONG_DAN_IN_BANG.md`). Theo `stress_test/REPORT.md` (ảnh giả lập kiểu ESP32 q20–30, code có
  SUBPIX), bảng 250 mm ở 5 m chỉ đạt "an toàn" 27–47% số lần chụp. Camera xa hơn cần bảng lớn hơn: in cỡ khác bằng
  `generate_marker.py --size-mm <mm>` (bảng ≳ 630 mm ra trang khổ lớn/bạt).
- **Độ chính xác pose phụ thuộc kích thước bảng trên ảnh** (`stress_test/REPORT.md`,
  `size_test/REPORT.md`): sai số xoay/vị trí hiệu chỉnh là nguồn sai số lớn nhất khi vật ở xa; sai số
  reprojection KHÔNG phân biệt được pose đúng/sai/lật. Công cụ hiệu chỉnh đã có tuỳ chọn
  `--camera-height-m`, NHƯNG đã kiểm chứng rằng độ cao KHÔNG phân biệt được hai nghiệm pose
  (hai nghiệm là ảnh phản chiếu, cùng độ cao, lệch ~5 m theo phương ngang); tuỳ chọn này chỉ giúp
  kiểm tra độ cao ước lượng. Cách phân biệt nghiệm lật đang chờ quyết định (giả định camera gắn
  thẳng ngang, hoặc người lắp khai báo camera đứng phía nào của bảng). Mọi số liệu
  này đến từ ảnh GIẢ LẬP, chưa kiểm bằng ảnh thật ngoài hiện trường.
- `model_demo/README.md`: demo chiếu mask model YOLO thật; pose vẫn là pose giả lập `DEMO-CAM`
  nên toạ độ trên bản đồ không phải vị trí rác thật.
- `source` trong file calibration ghi rõ `"aruco"` (ảnh thật) hay `"synthetic"` (ảnh giả
  lập) để không nhầm lẫn khi đọc lại sau này.

## Cách xoá / dọn dẹp

Toàn bộ nội dung sinh ra lúc chạy nằm trong 2 thư mục, xoá an toàn bất kỳ lúc nào (script
sẽ tự tạo lại khi chạy lần sau):

```
rd /s /q outputs
rd /s /q calibration
```

(hoặc trên Git Bash: `rm -rf outputs calibration`)

Không có gì trong exp02 này được ghi ra ngoài thư mục `research/exp02_ve_rac_len_ban_do/`
(trừ việc ĐỌC ảnh/nhãn có sẵn trong `datasets/Try1/test/`, không ghi gì vào đó).
