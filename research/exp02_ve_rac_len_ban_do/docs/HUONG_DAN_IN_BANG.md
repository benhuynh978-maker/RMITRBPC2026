# Hướng dẫn in và đặt bảng ArUco (mặc định khổ A3, cỡ khác bằng `--size-mm`)

Bảng ArUco là tờ giấy có hình vuông đen–trắng đặc biệt. Camera nhìn thấy bảng này thì phần mềm biết
camera đang đứng ở đâu và nhìn nghiêng bao nhiêu, từ đó mới chiếu được vùng rác lên bản đồ.
**Bảng in sai kích thước thì mọi số đo sau đó đều sai theo**, nên hãy làm kỹ phần in và phần đo.

File cần in: `outputs/marker_A3.pdf` (khổ A3 dọc, 297 × 420 mm). Cạnh vùng mã đen là **250 mm**.
Nếu file chưa có, chạy: `C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B generate_marker.py`
(trong thư mục `research/exp02_ve_rac_len_ban_do/`). Ảnh xem nhanh: `outputs/marker_A3_preview.png`.

**Chỉ có MỘT con số phải nhập tay: cạnh thật của bảng (mm), đo bằng thước sau khi in.** Khi hiệu chỉnh
nhập số đó bằng `--marker-size-mm <số>`. Quy tắc duy nhất của công cụ: nếu bảng chiếm **dưới 50 px**
(cạnh ngắn nhất, trên ảnh) thì công cụ KHÔNG lưu kết quả và báo lỗi (mã thoát 3). Từ 50 px trở lên thì lưu.

**Cần bảng cỡ khác (xa camera hơn)?** Thêm `--size-mm <cạnh vùng mã, mm>`, máy tự chọn khổ giấy
(A4/A3/A2/A1/A0, lớn hơn nữa thì ra trang khổ lớn/bạt đúng tỉ lệ vật lý):

```
C:/Users/ASUS/Desktop/SSC/.venv/Scripts/python.exe -B generate_marker.py --size-mm 500
```

ra `outputs/marker_A0_500mm.pdf` / `.png`. Tên file có dạng `marker_<khổ>_<cỡ>mm.*` (riêng 250 mm khổ A3 vẫn
là `marker_A3.*`). Khổ chọn theo cạnh bảng (lề trắng mỗi bên tối thiểu 23 mm, bảng lớn hơn 250 mm thì lề = cạnh/6):

| Cạnh bảng | Khổ tự chọn |
|---|---|
| tới ~150 mm | A4 |
| tới 250 mm | A3 (bản mặc định) |
| tới ~315 mm | A2 |
| tới ~445 mm | A1 |
| tới ~630 mm | A0 |
| trên ~630 mm | khổ tuỳ chỉnh "in khổ lớn / bạt" (PDF đúng mm, gửi nơi in bạt, in 100%) |

Mọi trang đều có chữ ghi cỡ vùng mã, thước kiểm tra in kèm (100 mm; 500 mm với bảng từ 500 mm trở lên) và ô điền số đo thật.

## 1. In giấy

1. Mở `marker_A3.pdf` (hoặc file `marker_<khổ>_<cỡ>mm.pdf` của cỡ bạn chọn) bằng trình đọc PDF (Adobe Reader, Edge, Chrome đều được).
2. Chọn máy in có giấy **A3**. Nếu cơ quan không có máy in A3, mang file ra **tiệm photo/in** và dặn
   rõ: "in khổ A3, tỉ lệ 100%, không thu phóng".
3. Trong hộp thoại in:
   - Kích thước trang: chọn **"Kích thước thật" / "Actual size" / "100%"**.
   - **TẮT** "Fit to page / Vừa khít trang / Shrink to fit". Nếu để bật, máy sẽ thu nhỏ bảng và
     kích thước sẽ sai.
   - Khổ giấy: A3, hướng giấy: dọc. Màu: đen trắng là đủ; chất lượng: cao nhất.
4. Dùng giấy trắng, **không bóng loáng** (giấy bóng sẽ chói đèn/nắng, camera không thấy rõ).
   Mực đen phải đen đặc, không bị nhạt hoặc có vệt sọc.

## 2. Kiểm bằng thước (bắt buộc, 1 phút)

Trên tờ in có 2 thứ để kiểm:

- **Thước 100 mm in kèm** (phía dưới bảng; 500 mm với bảng từ 500 mm trở lên): đặt thước thật lên, vạch 0 và
  vạch cuối của thước in phải trùng đúng với thước thật. Lệch hơn 1 mm nghĩa là máy in đã co/giãn giấy.
- **Cạnh vùng mã đen**: dùng thước thật (thước thép/thước cuộn) đo **một cạnh của hình vuông đen lớn**,
  từ mép đen này sang mép đen kia, không tính phần giấy trắng bên ngoài. Kết quả phải là
  **250 mm** (thiết kế 249,94 mm do làm tròn theo ô, sai lệch này không đáng kể).
  Ghi số đo được vào ô "Canh vung ma do duoc = ____ mm" trên tờ giấy.
  Nên đo cả 2 cạnh (ngang và dọc).

Nếu số đo khác 250 mm quá 2 mm: in lại và kiểm tra lại bước 1 (thường là quên tắt "Fit to page").
Nếu vẫn lệch mà không in lại được, **dùng đúng số đo thật bằng thước** làm giá trị `--marker-size-mm`
khi hiệu chỉnh (ví dụ `--marker-size-mm 247`). Đừng dùng tờ in lệch mà vẫn khai 250 mm. Đây là con số
duy nhất phải nhập tay.

## 3. Dán lên bề mặt phẳng cứng

- Dán tờ A3 lên **tấm ván ép, tấm xốp foam board hoặc tấm nhựa/alu cứng** có kích thước tối thiểu
  bằng tờ giấy. Dùng keo xịt hoặc băng keo hai mặt phủ đều toàn bộ mặt sau, ép từ giữa ra mép.
- Bề mặt phải **phẳng tuyệt đối**: không cong, không nhăn, không phồng bóng khí, góc không bị
  vểnh. Giấy cong làm sai số đo mà phần mềm không phát hiện được.
- Không cắt vào phần đen. Phần giấy trắng quanh bảng (khoảng 23 mm với bản A3) **phải giữ nguyên**, vì đó là
  vùng trắng giúp camera nhận ra bảng.
- Nếu để ngoài trời: phủ lớp màng ép nhám (không bóng), chặn gió bằng cách kê/đè bốn góc từ phía
  dưới (không đè lên phần đen).

## 4. Chụp ảnh hiệu chỉnh

Dùng đúng camera sẽ lắp tại hiện trường, ở đúng vị trí và góc nhìn cố định của nó.

1. **Đặt bảng nằm phẳng trên mặt đất** (hoặc mặt phẳng cần đo), trong khoảng nhìn của camera.
   Bảng càng gần camera càng tốt (xem bảng cỡ bên dưới). **Chụp thử ở nhà với bảng A3 250 mm: chụp
   trong khoảng ~2 m** (ở xa hơn, bảng chiếm dưới 50 px và công cụ sẽ từ chối lưu).
2. Camera nên nhìn bảng **hơi xiên, đừng nhìn thẳng góc**. Theo báo cáo stress test, nên để camera nhìn bảng
   nghiêng khoảng 45° so với phương vuông góc với bảng thì cho kết quả tốt nhất ở khoảng cách xa
   (nhìn thẳng góc 90° vào bảng là trường hợp khó nhất để ước lượng độ nghiêng).
3. **4 góc của bảng đều nằm trọn trong khung hình**, không bị cắt, không bị che bởi người, bóng,
   lá cây hay rác.
4. **Đủ sáng, không chói, không có bóng đổ vắt ngang bảng.** Chụp ban ngày. Tránh nắng chiếu
   thẳng làm giấy trắng cháy sáng.
5. **Ảnh phải nét.** Lấy nét ống kính trước khi chụp: báo cáo stress test cho thấy ảnh mờ
   là yếu tố phá hoại nhất (mờ vừa, cỡ 2 px, đã làm mất nhận diện bảng 200 mm từ 2–3 m).
6. Chụp ở **chất lượng JPEG cao nhất** mà camera/firmware cho phép (ESP32: thang chất lượng
   ngược, số nhỏ = chất lượng cao). Không dùng ảnh đã nén thấp từ luồng video.
7. **KHÔNG zoom số.** Zoom số làm đổi thông số camera so với giả định, phần mềm sẽ tính sai.
8. Chụp 2–3 ảnh liên tiếp để chọn ảnh nét nhất.

## 5. Cỡ bảng tối thiểu theo khoảng cách và độ nghiêng (cho >= 50 px)

Công cụ chặn lưu khi cạnh ngắn nhất của bảng trên ảnh **dưới 50 px**. Cạnh bảng trên ảnh (camera 640×480,
góc mở đường chéo 66° giả định, tiêu cự ≈ 616 px) xấp xỉ `616 · S · cos(θ) / D` px, nên để đạt 50 px:

```
S  >=  50 · D / (616 · cos θ)
```

- `S`: cạnh vùng mã của bảng (cùng đơn vị với `D`, ở đây là mét).
- `D`: khoảng cách từ camera tới bảng THEO ĐƯỜNG NHÌN (không phải khoảng cách trên mặt đất).
- `θ`: góc giữa hướng nhìn và pháp tuyến của bảng. Bảng nằm phẳng trên đất thì pháp tuyến là phương
  thẳng đứng: nhìn thẳng từ trên xuống `θ = 0°`, nhìn càng thấp/xa thì `θ` càng lớn.

Cạnh bảng tối thiểu (mm, làm tròn lên 10 mm) để được ≥ 50 px:

| Khoảng cách camera → bảng D | Nhìn gần thẳng (θ = 20°) | Nghiêng vừa (θ = 45°) | Nằm bẹt, nhìn xiên (θ = 65°) |
|---|---|---|---|
| 2 m | 180 mm | 230 mm | 390 mm |
| 3 m | 260 mm | 350 mm | 580 mm |
| 4 m | 350 mm | 460 mm | 770 mm |
| 5 m | 440 mm | 580 mm | 970 mm |
| 6 m | 520 mm | 690 mm | 1160 mm |
| 8 m | 700 mm | 920 mm | 1540 mm |

Đọc ngược lại cho bảng A3 250 mm: đạt 50 px khi `D ≤ 616 · 0,25 · cos θ / 50`, tức **D ≈ 2,2 m ở θ = 45°**,
**≈ 2,9 m ở θ = 20°** (≈ 1,3 m ở θ = 65°). Chụp thử ở nhà với bảng A3 250 mm nên chụp trong khoảng **~2 m**.

Ví dụ lắp thật (bảng nằm phẳng trên đất, camera nhìn xuống bảng, góc nhìn so với phương thẳng đứng ≈ 45° khi
bảng cách chân cột bằng đúng độ cao camera):

- Camera cao 3 m, bảng cách chân cột 3 m: `D = √(3²+3²) ≈ 4,24 m`, `θ = 45°` → cần bảng **≈ 0,5 m** (487 mm).
- Camera cao 6 m, bảng cách chân cột 6 m: `D ≈ 8,49 m`, `θ = 45°` → cần bảng **≈ 1 m** (974 mm).

Bảng 0,5 m tạo bằng `generate_marker.py --size-mm 500` (A0), bảng 1 m ra trang khổ lớn/bạt
(`--size-mm 1000`). Công thức là xấp xỉ theo số đo mô phỏng (`stress_test/REPORT.md`, `size_test/REPORT.md`), chưa
kiểm bằng ảnh thật ngoài hiện trường: nên chọn bảng lớn hơn một chút so với con số tối thiểu, nhất là khi ảnh mờ hoặc nén mạnh.

## 6. Giới hạn và việc cần làm khi đo xa

- Mọi số ở trên đến từ **ảnh giả lập** trên máy tính, chưa kiểm bằng ảnh thật ngoài hiện trường.
  Camera thật có méo ống kính, bụi bẩn, gió làm cong bảng... nên sai số thật có thể lớn hơn.
- Góc mở ống kính 66° là **giả định**, chưa đo camera thật. Nên hiệu chỉnh nội tại camera bằng
  bàn cờ (checkerboard) khi có điều kiện.
- Con số "sai số reprojection" mà công cụ in ra **không cho biết kết quả có đúng hay không** (báo
  cáo stress test mục 4, ý 6: gần như bằng nhau giữa kết quả đúng và kết quả sai/bị lật). Đừng dựa vào nó.
- Khi camera ở xa (bảng nhỏ trên ảnh), tư thế camera có thể bị "lật" sang nghiệm sai (báo cáo ghi
  12–15% ca lật, tập trung ở bảng nhỏ). **Lưu ý: độ cao camera KHÔNG giúp phân biệt nghiệm lật**
  (hai nghiệm là ảnh phản chiếu, cùng độ cao, lệch ~5 m theo phương ngang). Công cụ
  `calibrate_aruco.py` có tuỳ chọn `--camera-height-m` (đo độ cao camera bằng thước/thước laser, mét)
  nhưng chỉ để **kiểm tra chéo** độ cao ước lượng (cảnh báo khi lệch > 20%). Cách phòng thật sự: dùng
  bảng đủ lớn, chụp gần hơn, chụp nét, và đối chiếu vị trí camera mà công cụ tính ra với thực tế
  (camera phải nằm đúng phía của bảng). Khi công cụ cảnh báo "có thể lật", đừng dùng kết quả đó.
- Cạnh thật của bảng (đo bằng thước) là con số duy nhất phải nhập tay: `--marker-size-mm <số>`. Nếu khác 250 mm, phải khai đúng số đo thật.
- Báo cáo liên quan: `stress_test/REPORT.md` (độ bền nhận diện theo khoảng cách/chất lượng ảnh),
  `size_test/REPORT.md` (sai số đo diện tích/vị trí), `model_demo/README.md` (demo dùng kết quả model AI).
