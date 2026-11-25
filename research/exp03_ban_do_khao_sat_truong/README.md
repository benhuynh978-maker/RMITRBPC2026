# Công cụ khảo sát rác khu vực trường (exp03)

Chụp nhanh nhiều điểm trong khuôn viên, AI khoanh rác, bạn chỉ chỉnh nhẹ, rồi xuất **một thư mục mở bằng cách bấm đúp** (không cần mạng, không cần máy chủ) để trình bày bản đồ rác: diện tích (m²), vùng, vị trí, kèm ảnh bằng chứng và giờ chụp.

Chạy **riêng** (cổng 8130, dữ liệu trong `data/` của thư mục này). **Không sửa** hệ thống chính (`ssc-road-alerts/`, `inference/`, `test-WebUI-modelAI/`, `runs/`) và không sửa webtest; chỉ **đọc** mã hình học của `exp02_ve_rac_len_ban_do` để dùng lại. Có thể chạy song song với webtest (cổng 8120) và dashboard demo (Funnel 10000).

> Đây là công cụ khảo sát thử nghiệm, **không phải** hệ thống giám sát và không phải dữ liệu thời gian thực.

## Khác webtest ở đâu

| | webtest | công cụ này |
|---|---|---|
| Mỗi điểm | chụp bảng → Detect → bấm vị trí → kéo hướng → Save → chụp rác (~5 bước tay) | **1 ảnh** có cả bảng và rác; tự dò bảng, tự hiệu chỉnh từ chính ảnh đó, tự chạy AI |
| Nhiều điểm | một hiệu chỉnh tại một thời điểm | một bản đồ chung: tên điểm, m² từng điểm, tổng, giờ chụp |
| Sửa | không | ẩn vùng AI sai, vẽ bù vùng bị sót (nhãn "vẽ tay"), kéo ghim, chỉnh hướng |
| Trình bày | cần máy chủ + Internet | thư mục offline (ảnh bằng chứng đã bỏ GPS, bản đồ nền tải sẵn) |

Phép chiếu rác lên mặt đất **dùng nguyên** `calibrate_aruco`, `project_mask`, `camera_model` của exp02 (không nhân bản logic). `test_survey.py` còn đối chiếu trực tiếp với `webtest/server.py`: cùng mask, cùng hiệu chỉnh, cùng vị trí/hướng cho ra cùng m² và cùng toạ độ từng đỉnh (3 ca, kể cả xoay 37,5° và 200°).

## Chạy

```powershell
cd research\exp03_ban_do_khao_sat_truong
.\run_tailscale.ps1
```

Script in hai đường dẫn: **laptop** (`http://<ip>:8130/#<mã>`) và **điện thoại** (`.../phone#<mã>`). Mã 6 số tự sinh một lần, lưu ở `data/access_code.txt` (không nằm trong Git). Máy chủ chỉ nghe địa chỉ Tailscale. Điện thoại cần bật Tailscale (hoặc dùng cách chép file).

Hai cách đưa ảnh vào:
1. **Trang `/phone`** (như webtest): chụp bằng camera hoặc chọn nhiều ảnh trong thư viện; thấy kết quả ngay ("tìm thấy bảng, N vùng, X m²" hoặc "bảng quá nhỏ, chụp lại").
2. **Chép file**: thả **ảnh gốc** (không nén qua Zalo/Messenger, vì sẽ mất tiêu cự camera) vào `thu_muc_anh/`, rồi bấm "Nạp ảnh từ thư mục" trên laptop. Ảnh đã nạp (so theo nội dung) bị bỏ qua, không nạp trùng.

Quy trình chụp và rà soát: xem [`HUONG_DAN_CHUP.md`](HUONG_DAN_CHUP.md).

## Cách tính

1. Giải ảnh (xoay theo EXIF, tối đa 2048 px), đọc **tiêu cự 35 mm** từ EXIF để dựng góc nhìn; không có EXIF thì dùng 66° mặc định và **cảnh báo** (m² có thể lệch).
2. Dò bảng ArUco (DICT_4X4_50, id 0, cạnh vùng mã 250 mm), giải vị trí camera bằng solvePnP. Bảng < 50 px hoặc không thấy → điểm "lỗi" có lý do bằng tiếng Việt; ảnh vẫn được lưu.
3. YOLO26s-seg (`baseline_v1_rev2`, cùng model webtest) khoanh rác; **bỏ phần tờ giấy bảng** khỏi mask (model hay khoanh nhầm tờ bảng thành rác).
4. Chiếu viền vùng xuống mặt phẳng bảng (giả định mặt đất phẳng), tính m² từ viền pixel chính xác. Vùng lưu trong **hệ toạ độ bảng** (mét, gốc tại tâm bảng), nên đổi vị trí/hướng điểm chỉ là tịnh tiến + xoay, không chạy lại AI.
5. Vị trí và hướng bạn đặt trên bản đồ (bấm chuột; kéo ghim; hướng chung + hướng riêng từng điểm) quyết định lat/lon cuối.
6. Tổng m² = tổng các vùng đang hiện ở các điểm đã đặt vị trí và "đưa vào bản trình bày". Hai điểm chụp trùng một mảnh đất được **cảnh báo** (cùng mảnh đất có thể bị tính hai lần), tổng không tự trừ.

## Bản trình bày xuất ra (`data/exports/trinh_bay/`, kèm `trinh_bay.zip`)

`index.html` (bấm đúp), `data.js`, `viewer.js/css`, `leaflet/`, `tiles/` (ô bản đồ nền), `photos/` (ảnh bằng chứng + ảnh có vùng AI + ảnh thu nhỏ; **đã bỏ EXIF/GPS**, giờ chụp lấy từ EXIF ghi trong `data.js`). Mở từ `file://` không gọi máy chủ nào. Trang ghi sẵn các dòng trung thực (chỉ các điểm đã chụp; AI còn bỏ sót; vị trí đặt bằng tay sai số vài mét; số vùng vẽ tay; ảnh dùng góc nhìn mặc định nếu có; điểm chồng nhau).

Bản đồ nền tải từ OpenStreetMap France (cùng nguồn webtest) **một lần khi xuất**: tối đa 500 ô, zoom 16 đến tối đa 20, cách nhau ≥ 0,7 s, có User-Agent mô tả; ô đã tải được giữ ở `data/tiles/` nên xuất lại không tải lại. Nếu có ô tải lỗi, hộp thoại báo số ô lỗi (có ô trống khi phóng to). Khi lúc trình bày **có mạng**, trang tự lấy thêm ô trực tuyến lấp chỗ trống; không có mạng vẫn chạy.

## Kiểm thử

```powershell
..\..\.venv\Scripts\python.exe -B test_survey.py     # 108 kiểm tra; SURVEY_SKIP_MODEL=1 để bỏ phần model thật
```

Đã kiểm trong môi trường làm việc (Linux):
- Hình học: hình vuông 0,3×0,3 m dựng trên mặt đất ra ≈ 0,09 m² (±6%) và đúng toạ độ; trùng webtest đến ≤ 2 mm (xem trên).
- AI giả (xác định) cho API: mã truy cập, từ chối dữ liệu sai, ảnh trùng, ảnh lỗi, ẩn/hiện vùng, vẽ tay, tổng hợp, chồng nhau, nạp thư mục, chạy lại, EXIF (giờ, tiêu cự, GPS bị bỏ khỏi ảnh hiển thị/xuất), xuất (ô bản đồ tải từ máy chủ ô giả, tải lỗi, xuất lần 2 không tải lại).
- Model YOLO thật trên ảnh mẫu của repo: ảnh có bảng → có vùng, không vùng nào nằm trong tờ bảng; ảnh không có bảng → báo lỗi, không chạy AI.
- Trình duyệt thật (Chromium, Playwright, 51 kiểm tra): trang điện thoại 390 px (gửi nhiều ảnh, ảnh lỗi, ảnh trùng), trang rà soát (đặt vị trí liên tiếp, ẩn vùng qua nút và qua popup, vẽ tay có diện tích khớp hình học bản đồ ±4%, kéo ghim, hướng chung/riêng, xem ảnh có/không vùng AI), xuất, và mở bản xuất qua `file://` **khi ngắt mạng**: bản đồ nền offline hiện, không có yêu cầu mạng nào, không lỗi console, không tràn ngang ở 390 px.

**Chưa kiểm** (ghi rõ để khỏi hiểu nhầm):
- `run_tailscale.ps1` chưa chạy trên Windows.
- Chưa gửi ảnh từ điện thoại thật qua Tailscale; chưa tải ô bản đồ thật từ OpenStreetMap France (chỉ thử với máy chủ ô giả).
- **Sai số m² với ảnh điện thoại thật chưa đo.** Đã kiểm hình học nội tại và độ khớp với webtest, chưa đo bằng vật thể có kích thước biết trước, chưa đo ảnh từ iPhone/Android thật.
- Tỉ lệ AI bỏ sót rác chưa đo ở công cụ này (webtest ghi recall ≈ 0,44 trên tập kiểm định). Ảnh mẫu `board-trash.jpg` của repo không được dò thấy bảng dù trông rõ; vì thế ngoài hiện trường cần xem phản hồi "tìm thấy bảng" trên điện thoại sau mỗi ảnh.
- Chưa thử với hàng chục điểm ngoài hiện trường (tối đa 300 điểm).

## Giới hạn cần biết

- Chỉ vài điểm ban ngày → **không** gọi là "bản đồ cả trường"; số liệu chỉ ở các điểm đã chụp.
- Model bỏ sót rác nhiều; vùng vẽ tay có thể chiếm tỉ lệ đáng kể và luôn được ghi nhãn "vẽ tay" kèm m² riêng.
- Chỉ đúng khi mặt đất phẳng, bảng ≥ 50 px, ảnh gồm cả bảng; rác xa bảng hoặc chụp xiên kém chính xác hơn. Vật cao bị vẽ phình ra (như webtest).
- Vị trí tuyệt đối do bạn đặt bằng mắt: sai số vài mét; chính xác tương đối quanh bảng tốt hơn.
- Vùng rác chỉ vài chục cm nên ở mức thu nhỏ chỉ là vài điểm ảnh: bản đồ vẽ thêm vòng tròn nhỏ (cỡ cố định) cho dễ thấy; ở mức 21 trở lên thấy đa giác thật (bản đồ nền chỉ có ô gốc đến mức 20, phóng thêm sẽ mờ).
- Ở mức 20 trở lên ghim thu thành chấm 12 px; rác nằm sát bảng (< ~1 m) bị chấm che một phần, hãy bấm vào mép vòng.

## Tệp

| Tệp | Việc |
|---|---|
| `svy_core.py` | lõi: xử lý một ảnh, vùng ở hệ toạ độ bảng, ảnh overlay, vẽ tay, tổng hợp, chồng nhau |
| `svy_store.py` | lưu trữ (`data/`), mã truy cập |
| `svy_server.py` | API FastAPI, trang tĩnh |
| `svy_export.py` | xuất bản trình bày, tải ô bản đồ |
| `web/index.html`, `web/phone.html` | trang rà soát (laptop) và trang chụp (điện thoại) |
| `web/vendor/leaflet/` | Leaflet 1.9.4 (BSD-2, `LICENSE`) dùng cục bộ, không tải CDN |
| `viewer/` | trang xem của bản trình bày |
| `run_tailscale.ps1`, `test_survey.py`, `HUONG_DAN_CHUP.md` | chạy, kiểm thử, hướng dẫn chụp |
