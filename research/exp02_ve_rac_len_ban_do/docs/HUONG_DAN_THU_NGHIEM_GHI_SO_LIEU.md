# Hướng dẫn thử nghiệm và ghi số liệu làm bằng chứng

**Luồng được thử:** điện thoại chụp → gửi về máy chủ (backend) → AI xử lý → vùng rác hiện lên bản đồ (WebUI) trên laptop.

Mục đích: tạo **bằng chứng có số liệu** để bảo vệ sản phẩm/công nghệ, và điền vào mục 5.7 của báo cáo "III. Sản phẩm và công nghệ".

> **Lần đầu làm: đọc mục 8 "Một buổi làm thật" trước** — nó kể lại từng bước theo đúng thứ tự, kèm ví dụ ghi số.
>
> Tài liệu này thay cho `HUONG_DAN_THU_O_NHA.md` (bản cũ, chép ảnh thủ công sang laptop). Hướng dẫn in bảng chi tiết vẫn ở `HUONG_DAN_IN_BANG.md`.

---

## 0. Quy tắc vàng của bằng chứng (đọc trước)

1. **Đặt tiêu chí TRƯỚC khi đo.** Đọc mục 3, chốt các ngưỡng, ghi ngày chốt vào ô "Ngày chốt tiêu chí". Không sửa ngưỡng sau khi thấy kết quả.
2. **Ghi tất cả, kể cả lần hỏng.** Lần gửi lỗi, lần model không nhận ra cũng là số liệu. Không xoá, không chọn lọc.
3. **Mỗi số liệu phải truy được về ảnh gốc.** Đặt tên ảnh theo quy ước ở mục 2.3, ghi tên ảnh vào bảng.
4. **Sao lưu file của máy sau mỗi buổi** (mục 2.4). Đó là bằng chứng do máy tạo ra, mạnh hơn số ghi tay.
5. **Không để mặt người và biển số xe lọt vào khung hình** (cơ chế che mờ chưa có). Thử ở sân nhà, hành lang, vỉa hè lúc vắng; nếu có người lọt vào thì xoá ảnh đó và ghi chú.

---

## 1. Chuẩn bị

### 1.1 Dụng cụ

| Dụng cụ | Ghi chú |
|---|---|
| Bảng ArUco đã in | A3 (`outputs/marker_A3.pdf`) hoặc A4 dự phòng (`outputs/marker_A4_150mm.pdf`), in 100%, **đo cạnh vùng mã bằng thước và ghi lại** |
| Tấm cứng phẳng | Bìa dày, ván, foam board để dán bảng |
| Giá đỡ / chân máy điện thoại | Phải giữ điện thoại **đứng yên hoàn toàn** suốt buổi |
| Thước cuộn ≥ 3 m | Đo vị trí vật và độ cao điện thoại |
| Băng dính màu | Đánh dấu điểm trên sàn |
| "Rác" thử | **Vật dẹt** dễ thấy: túi nilon trải phẳng, giấy báo, bìa carton dẹt, vỏ hộp ép dẹt. Thêm 2–3 vật thường (chai, lon) để thử phát hiện |
| Laptop đang chạy máy chủ | Cắm sạc, tắt chế độ ngủ |

### 1.2 Thiết lập máy (mỗi buổi)

1. Laptop: mở PowerShell
   ```powershell
   cd C:\Users\ASUS\Desktop\SSC\research\exp02_ve_rac_len_ban_do\webtest
   .\run_tailscale.ps1
   ```
   Giữ cửa sổ này mở. Script in ra hai đường dẫn (laptop và điện thoại) đã kèm mã truy cập.
2. Laptop mở đường dẫn **Laptop**. Thanh trên cùng: "Máy chủ" xanh, "Model AI" đã nạp.
3. Điện thoại bật Tailscale, mở đường dẫn **Điện thoại** (`.../phone#<mã>`).
4. Điện thoại: **Cài đặt camera** — ống kính chính 1×, tắt HDR, tắt chế độ chân dung/làm đẹp. iPhone: Cài đặt → Camera → Định dạng → **Tương thích nhất** (JPEG).

### 1.3 Dựng cảnh

1. Dán bảng lên tấm cứng, đặt **nằm phẳng** trên mặt đất, giữa vùng thử.
2. Kẹp điện thoại lên giá, nhìn xiên xuống bảng (khoảng 45°), cách bảng **1–2 m** (A3) hoặc **1–1,3 m** (A4). Bảng và khoảng sàn quanh bảng (≈ 1–1,5 m mỗi phía) phải nằm trong khung.
3. Chọn một hướng **dọc hoặc ngang** và giữ suốt buổi.
4. **Đo bằng thước và ghi lại:** độ cao ống kính điện thoại so với mặt đất (m); khoảng cách theo mặt đất từ chân giá tới tâm bảng (m).
5. Dùng băng dính đánh dấu trên sàn (gốc là **tâm bảng**; xem hướng +Y/+X ở bước hiệu chỉnh):
   - +Y: 0,5 m; 1,0 m; 1,5 m
   - +X: 0,5 m; 1,0 m
   - chéo: (+Y 1,0 m; +X 0,5 m) và (+Y 1,0 m; −X 0,5 m)
   Ghi toạ độ thật từng điểm theo dạng (dọc +Y, dọc +X), mét.

> Mẹo chống xê dịch: mỗi lần bấm chụp có thể làm điện thoại rung. Dùng **hẹn giờ 2–3 giây** của camera hoặc tai nghe/nút bấm Bluetooth làm nút chụp. Cuối buổi chụp lại một **ảnh kiểm tra trôi** (mục 4, TN3 bước 6).

---

## 2. Hiệu chỉnh và quy ước ghi chép

### 2.1 Hiệu chỉnh (đầu mỗi buổi, sau khi dựng cảnh xong)

1. Bỏ hết vật khỏi sàn (chỉ còn bảng). Trên điện thoại bấm **"Chụp ảnh hiệu chỉnh (có bảng)"**.
2. Laptop, **Bước 1**: chọn ảnh vừa gửi trong "Ảnh từ điện thoại", nhập **cạnh bảng đo được (mm)**, bấm **Dò bảng**.
   - Ghi lại: **số px của bảng**, **nguồn góc mở** ("đọc từ ảnh" hay "mặc định 66°"), mọi cảnh báo vàng.
   - Nếu nguồn là "mặc định 66°": nhập góc mở thật của điện thoại vào ô "Góc mở ống kính" rồi dò lại. Tra **tiêu cự tương đương 35 mm** của camera chính (thông số máy): 24 mm → 84°; 26 mm → 79,5°; 28 mm → 75,4° (công thức: 2·atan(43,267 / (2·f))).
   - Xem ảnh dò: mũi tên **+Y xanh dương**, **+X đỏ**. Đối chiếu ngoài đời và xác nhận các điểm băng dính đã đánh dấu đúng hướng +Y/+X (nếu sai thì dán lại).
3. **Bước 2**: bấm một điểm trên bản đồ làm vị trí bảng. **Để mũi tên chỉ đúng hướng Bắc (0°)**. Quy ước này giúp đọc số: trên bản đồ, **lên trên = +Y, sang phải = +X**. (Thử nghiệm đo độ đúng *tương đối* quanh bảng, không cần đúng hướng la bàn thật.)
4. **Bước 3**: xem vùng xanh (mặt đất camera thấy) và điểm camera có hợp lý không, bấm **Lưu hiệu chỉnh**.
5. **Ngay sau khi lưu**: sao chép file `research\exp02_ve_rac_len_ban_do\calibration\WEB-DEMO.json` vào thư mục bằng chứng của buổi (mục 2.4). Trong file có `camera_height_m_est` — độ cao camera do **máy tự ước lượng** từ bảng (dùng cho TN2).

### 2.2 Đọc vị trí vùng rác trên bản đồ

- **Cách chính: script `doc_so_lieu.py`** — máy in thẳng vị trí tâm (Y, X, mét) và diện tích từng vùng rác, đọc từ đúng dữ liệu máy chủ đã vẽ. Xem mục 8.6.
- Cách dự phòng (khi không chạy được script): phóng to quanh bảng, dùng **thanh tỉ lệ** góc dưới trái và **mũi tên +Y dài 2 m** làm thước; khoảng lên trên = +Y, sang phải = +X (sang trái là âm). Ghi chú "đọc tay".
- Chụp màn hình laptop (Win + Shift + S) cho **mỗi lần gửi**, thấy rõ vùng đỏ, bảng, thanh tỉ lệ.

### 2.3 Đặt tên ảnh và ảnh chụp màn hình

`B<buổi>_TN<số>_L<lần>_<mô tả>.jpg`, ví dụ `B01_TN3_L04_tui_Y1.0_X0.jpg`, ảnh màn hình thêm hậu tố `_man_hinh.png`. Ảnh gốc giữ trong điện thoại, cuối buổi chép sang laptop bằng **cáp hoặc tải bản gốc** (không gửi qua Zalo/Messenger vì bị nén).

### 2.4 Thư mục bằng chứng và sao lưu (cuối mỗi buổi)

```
bang_chung\
  B01_2026-10-xx\
    anh_goc\           ảnh gốc từ điện thoại
    man_hinh\          ảnh chụp màn hình laptop/điện thoại
    may_tao\           WEB-DEMO.json + observations.json (sao chép từ máy)
    bang_ghi\          file Excel đã điền (mục 5)
    ghi_chu.txt        thời tiết/ánh sáng, nơi thử, sự cố
```

File cần sao chép vào `may_tao\`:
- `research\exp02_ve_rac_len_ban_do\calibration\WEB-DEMO.json` (hiệu chỉnh)
- `research\exp02_ve_rac_len_ban_do\webtest\data\observations.json` (mọi lần gửi: thời điểm, số vùng, diện tích, toạ độ vùng rác)

> **Cẩn thận:** máy chỉ giữ **50 lần gửi gần nhất**, nút **"Xoá tất cả"** xoá sạch lịch sử, và hiệu chỉnh mới sẽ ghi đè file cũ. Luôn sao chép **trước** khi bấm "Xoá tất cả" hoặc hiệu chỉnh lại.

---

## 3. Tiêu chí (chốt trước khi đo)

Ngày chốt tiêu chí: `____/____/2026`. Các ngưỡng dưới là đề xuất; sửa nếu muốn **trước** buổi đo đầu tiên, sau đó giữ nguyên.

| Mã | Đại lượng | Ngưỡng đạt (đề xuất) |
|---|---|---|
| C1 | Tỉ lệ lần gửi thành công (ảnh tới máy chủ và hiện trên bản đồ) | ≥ 90% |
| C2 | Thời gian từ lúc bấm gửi tới lúc vùng rác hiện trên laptop (trung vị, qua 4G) | ≤ 20 giây |
| C3 | Quy tắc 50 px: bảng < 50 px bị từ chối, ≥ 50 px được chấp nhận | 100% đúng |
| C4 | Sai lệch độ cao camera máy ước lượng so với đo bằng thước | ≤ 10% |
| C5 | Sai lệch vị trí tâm vùng rác so với vị trí thật, trong 2 m quanh bảng | ≤ 0,20 m (đạt); 0,20–0,40 m (tạm chấp nhận); > 0,40 m (chưa đạt) |
| C6 | Sai số diện tích vật dẹt so với đo bằng thước | ≤ 25% |
| C7 | Độ lặp lại: 5 ảnh cùng cảnh, độ lệch vị trí lớn nhất giữa các lần | ≤ 0,05 m |
| — | Tỉ lệ vật được model nhận ra (TN5) | Không đặt ngưỡng, chỉ báo cáo |

---

## 4. Các thử nghiệm

Gợi ý chia buổi: **Buổi 1** (≈ 1,5 giờ) TN1 + TN2. **Buổi 2** (≈ 2 giờ) TN3 → TN6. Có thể lặp lại buổi 2 ở nơi khác (trong nhà / ngoài sân) để thêm bằng chứng.

### TN1. Luồng đầu-cuối và thời gian phản hồi (C1, C2)

**Mục tiêu:** chứng minh ảnh chụp bằng điện thoại qua 4G về được máy chủ, AI xử lý xong và có kết quả; đo mất bao lâu.

**Mỗi lần chụp bạn chỉ ghi đúng 2 thứ:** (1) thời gian, (2) kết quả OK/LỖI. Không cần đồng hồ bấm tay — máy tự đo. Mọi thứ còn lại máy đã lưu sẵn.

1. Điện thoại tắt Wi-Fi, chỉ dùng **4G** (ghi "4G" một lần ở trang Thông tin buổi).
2. Đặt 1–2 vật trong khung. Bấm **"Chụp ảnh rác"**, chụp, xác nhận. Đợi tới khi điện thoại hiện kết quả.
3. Trên điện thoại có dòng **"⏱ Thời gian: 6,4 s (tải lên … + chờ kết quả …; máy chủ xử lý …)"**. Chép **số in đậm (6,4)** vào cột *Thời gian trên điện thoại* của trang `TN1 Luồng`. Đây là thời gian đo bằng đồng hồ của chính điện thoại, từ lúc bắt đầu gửi tới lúc nhận kết quả.
4. Cột *Kết quả*: **OK** nếu điện thoại hiện kết quả (và laptop có ảnh mới); **LỖI** nếu điện thoại báo lỗi — chép nguyên văn lỗi vào cột *Ghi chú*.
5. Lặp **10–20 lần**, đổi vị trí vật giữa các lần.

**Kết quả (Excel tự tính):** tỉ lệ OK (C1), thời gian trung vị và lớn nhất (C2).

**Những thứ KHÔNG cần ghi tay:**

| Thông tin | Lấy ở đâu |
|---|---|
| Số vùng rác, diện tích, thời gian máy chủ xử lý, giờ gửi | Cuối TN1, chạy `doc_so_lieu.py` (mục 8.6) — tuỳ chọn, chỉ để minh hoạ |
| Giờ gửi, mạng 4G | Trang Thông tin buổi (ghi một lần) |
| "Hiện trên bản đồ sau … s" ở laptop | Tuỳ chọn, bỏ qua được. Bản đồ laptop tự cập nhật mỗi 3 giây nên chậm hơn số trên điện thoại tối đa khoảng 3 giây; nếu cần nêu trong báo cáo thì viết "thời gian đo trên điện thoại, bản đồ laptop thêm tối đa 3 giây" |

> Bản đồ laptop tự cập nhật **kể cả khi cửa sổ bị che hoặc thu nhỏ**.

### TN2. Hiệu chỉnh: quy tắc 50 px và độ cao camera (C3, C4)

**Mục tiêu:** chứng minh hệ thống tự từ chối ảnh hiệu chỉnh không đủ tin cậy và tự ước lượng đúng độ cao camera.

**Làm TN2 TRƯỚC hiệu chỉnh chính của buổi** (vì phải dời điện thoại). Ở đây chỉ bấm **Dò bảng**, **không bấm Lưu** → không đụng tới hiệu chỉnh đã lưu.

1. Đặt điện thoại cách bảng lần lượt **1 m; 1,5 m; 2 m; 3 m; 4 m; 5 m** (xa để cố ý vượt ngưỡng 50 px). Khoảng cách đã điền sẵn ở trang TN2.
2. Mỗi khoảng cách: đo độ cao ống kính bằng thước → cột *Độ cao đo bằng thước*. Bấm "Chụp ảnh hiệu chỉnh", ở laptop Bước 1 chọn ảnh, nhập cạnh bảng, bấm **Dò bảng**.
3. **Màn hình Bước 1 hiện sẵn cả 3 số cần chép** (không phải mở file nào):
   - dòng **"Bảng chiếm … px"** → cột *Số px*;
   - nhãn xanh "đủ lớn" → cột *Hệ thống* chọn **Chấp nhận**; báo "quá nhỏ" hoặc "không tìm thấy bảng" → chọn **Từ chối**;
   - dòng **"Độ cao camera máy ước lượng … m"** → cột *Độ cao máy ước lượng* (chỉ có khi được chấp nhận).
4. Excel tự tính "Đúng quy tắc 50 px?" và sai lệch độ cao (%).
5. Xong 6 khoảng cách: dựng lại cảnh chuẩn (mục 1.3) rồi làm hiệu chỉnh chính (mục 2.1).

**Kết quả cần báo:** bảng khoảng cách → px → chấp nhận/từ chối; sai lệch độ cao từng lần.

### TN3. Độ chính xác vị trí trên bản đồ (C5) — thử nghiệm quan trọng nhất

**Mục tiêu:** chứng minh vùng rác được vẽ đúng chỗ trên bản đồ.

**Y và X được đọc thẳng trên trang sau mỗi lần gửi — không cần chạy Python:**

1. Điện thoại đã hiệu chỉnh, **không chạm giá nữa**. Với mỗi dòng của trang TN3 (vị trí thật đã điền sẵn): đặt **một vật dẹt**, tâm vật trùng điểm băng dính → chụp (hẹn giờ) → gửi.
2. Sau khi gửi, **điện thoại hiện sẵn** dưới "Tổng diện tích":
   *Vị trí so với tâm bảng (lên = +Y, phải = +X)*
   *Vùng 1: Y = **1,08** m; X = **−0,03** m · 0,128 m²*
   Laptop (Bước 4) hiện **đúng dòng này**; bấm vào vùng đỏ **đánh số** trên bản đồ cũng hiện cửa sổ có Y, X và diện tích.
3. Gõ Y vào cột *Y đọc trên trang*, X vào cột *X đọc trên trang* của dòng đó. Excel tự tính độ lệch và mức đạt.
4. **Tờ bảng vẫn hiện trong danh sách** như một vùng (model hay khoanh nhầm tờ bảng thành rác); đó là vùng có **Y, X gần 0** (khoảng ±0,3 m). Bỏ qua vùng này, chỉ đọc vùng của **vật** (gần điểm đặt, đối chiếu số thứ tự trên bản đồ). Ảnh còn thêm mảnh rác lạ: chọn vùng của vật và ghi chú "có mảnh lạ"; tốt nhất là dọn mảnh lạ rồi chụp lại.
5. Lần nào không thấy vùng nào trên vật: cột *Model nhận ra?* chọn **Không**, để trống Y, X.
6. **Cuối TN3:** bỏ vật, chụp **ảnh kiểm tra trôi** (như mục 8.7).

**Cách thay thế khi đã chụp hết cả loạt** (nhanh nếu không muốn gõ từng lần): ở PowerShell thứ hai chạy
`..\..\..\.venv\Scripts\python.exe -B doc_so_lieu.py --last 14 --dan yx --copy` rồi bấm ô *Y đọc trên trang* dòng 1 → **Ctrl+V**. Cách này lấy dòng "gộp" (cộng mọi vùng, **kể cả tờ bảng**), nên **không dùng được cho TN3** nếu model khoanh cả tờ bảng; khi đó đọc từng vùng trên trang như ở trên.

**Kết quả cần báo:** số lần đạt / tạm chấp nhận / chưa đạt; trung vị và lớn nhất của độ lệch; độ lệch theo khoảng cách tới bảng (Excel tự chia gần / giữa / xa).

### TN4. Độ chính xác diện tích (C6)

1. Chọn **3–4 vật dẹt**, đo dài × rộng bằng thước (mét) → trang `TN4 Diện tích` (vật tròn xem ghi chú trong trang). Mỗi vật đo ở **2 vị trí** khác nhau (2 dòng). Diện tích thật tự tính.
2. **Diện tích nền của tờ bảng:** trước khi đặt vật, chụp một ảnh **chỉ có bảng** và gửi (nút "Chụp ảnh rác"). Nếu model khoanh tờ bảng, "Tổng diện tích" lúc đó chính là **diện tích nền** (ví dụ 0,153 m²); ghi số này lại. Nên đo nền 2–3 ảnh và lấy trung bình, vì diện tích tờ bảng có thể dao động nhẹ giữa các ảnh.
3. Đặt vật, chụp, gửi. Diện tích vật đọc theo một trong hai cách:
   - **Chính xác hơn:** đọc thẳng dòng của **vùng vật** trên điện thoại (hoặc laptop Bước 4): "Vùng 2: Y = … ; X = … · **0,128 m²**", bỏ qua dòng vùng ở tâm bảng. Không phải trừ gì.
   - **Nhanh:** lấy **Tổng diện tích − diện tích nền** (ví dụ 0,281 − 0,153 = 0,128). Dễ sai nếu nền dao động, vật đặt sát tờ bảng, hoặc ảnh có mảnh lạ.
   Gõ kết quả vào cột *Diện tích máy báo*. Một vật bị chia 2 vùng sát nhau: cộng hai diện tích và ghi chú.

Sai số % và ĐẠT/KHÔNG tự tính. Lưu ý: vật có chiều cao bị phóng to — chỉ dùng vật dẹt.

### TN5. Khả năng nhận ra rác của model trong cảnh thật (chỉ báo cáo)

Phần duy nhất **phải ghi tay** (cần mắt người), nhưng chỉ 3 số mỗi ảnh:

1. Mỗi ảnh đặt **3–5 vật** (cả dẹt và có chiều cao), chụp và gửi. Làm **≥ 10 ảnh**, đổi vật và vị trí.
2. Nhìn ảnh model đã khoanh (hiện ngay trên điện thoại), ghi vào trang `TN5 Phát hiện`: **số vật đã đặt**, **số vật có vùng tô bao trùm**, **số vùng tô nhầm** (tô chỗ không có rác; tờ bảng không tính vì máy đã bỏ qua).

**Kết quả cần báo:** tỉ lệ vật được nhận ra = tổng vật được khoanh / tổng vật đặt; số lần khoanh nhầm. Đây là số liệu trung thực về điểm yếu hiện tại của model.

### TN6. Độ lặp lại (C7)

1. Đặt 1 vật dẹt cố định, **không thay đổi gì**, gửi **5 ảnh liên tiếp**.
2. Mỗi lần gửi, đọc **Y, X, diện tích** của vùng vật trên trang (điện thoại hoặc laptop Bước 4), gõ vào trang `TN6 Lặp lại`. 

**Kết quả cần báo:** dao động vị trí và diện tích giữa 5 lần (Excel tự tính).

---

## 5. Bảng ghi số liệu

File mẫu: `docs\bang_ghi\BANG_GHI_SO_LIEU.xlsx`. Mỗi buổi chép một bản vào thư mục bằng chứng rồi điền. Mở trang **"Đọc trước"** đầu tiên.

**Mỗi thử nghiệm có một trang riêng**, đọc từ trên xuống gồm ba phần:

1. **Phần trên:** Mục tiêu, Cách làm (từng bước, kèm một dòng ví dụ), Tiêu chí.
2. **Phần giữa, nền xanh lá — KẾT QUẢ CỦA THỬ NGHIỆM NÀY:** máy tự tính ngay khi bạn điền bảng (số lần, trung vị, lớn nhất, ĐẠT / KHÔNG ĐẠT). Ô nền vàng **"Nhận xét của bạn"**: tự viết 1–3 câu khi làm xong.
3. **Phần dưới — BẢNG NHẬP LIỆU:** mỗi lần chụp/gửi là một dòng.

Màu ô: **trắng** = bạn nhập; **xám** = công thức tự tính (đừng gõ đè); **vàng** = bạn tự viết. Các cột "Kết quả", "Hệ thống", "Model nhận ra?" có mũi tên thả xuống — chọn, đừng gõ tay.

| Trang tính | Nội dung |
|---|---|
| `Đọc trước` | Cách dùng file |
| `Thông tin buổi` | Thông tin chung mỗi buổi (ngày, nơi, ánh sáng, điện thoại, cỡ bảng, góc mở, độ cao…) |
| `TN1 Luồng` … `TN6 Lặp lại` | Mỗi thử nghiệm một trang, có khung kết quả riêng |
| `Tổng hợp` | Gom kết quả của cả 6 trang thành một bảng — chép thẳng vào mục 5.7 báo cáo |

---

## 6. Tổng hợp kết quả để đưa vào báo cáo

Sau khi đủ số liệu, lập bảng như sau (điền vào mục 5.7 của báo cáo Word):

| Mã | Tiêu chí | Kết quả đo | Đạt? |
|---|---|---|---|
| C1 | ≥ 90% gửi thành công | …/… lần (…%) | |
| C2 | Trung vị ≤ 20 s | trung vị … s, lớn nhất … s | |
| C3 | 100% đúng quy tắc 50 px | …/… lần đúng | |
| C4 | Sai lệch độ cao ≤ 10% | trung bình …%, lớn nhất …% | |
| C5 | Lệch vị trí ≤ 0,20 m | trung vị … m, lớn nhất … m; …/… lần đạt | |
| C6 | Sai số diện tích ≤ 25% | trung bình …%, lớn nhất …% | |
| C7 | Lặp lại ≤ 0,05 m | lớn nhất … m | |
| — | Tỉ lệ nhận ra vật | …/… vật (…%), … lần khoanh nhầm | — |

Kèm theo: điều kiện thử (nơi, ánh sáng, điện thoại, cỡ bảng, độ cao, khoảng cách), 3–4 ảnh minh hoạ (ảnh đã khoanh + màn hình bản đồ tương ứng), và phần **nhận xét trung thực**: chỗ đạt, chỗ chưa đạt, nguyên nhân dự đoán.

---

## 7. Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Điện thoại không mở được trang | Kiểm tra Tailscale đã bật (biểu tượng chìa khoá), cửa sổ PowerShell còn chạy, đúng địa chỉ `100.107.97.50:8120` |
| "Bảng quá nhỏ trên ảnh" | Đưa điện thoại lại gần bảng, hoặc dùng bảng lớn hơn |
| "Không tìm thấy bảng ArUco" | Ảnh mờ, chói, bảng bị che hoặc thiếu góc — chụp lại rõ hơn |
| "Ảnh phải chụp cùng tỉ lệ khung hình…" | Đã đổi hướng dọc/ngang hoặc chế độ chụp — quay về như lúc hiệu chỉnh |
| "Chưa hiệu chỉnh camera" | Làm lại mục 2.1 đến khi bấm "Lưu hiệu chỉnh" |
| "Model không phát hiện rác" | Không phải lỗi hệ thống; ghi vào TN5. Thử vật màu nổi, dẹt |
| Vùng đỏ dài/to bất thường | Vật có chiều cao (giới hạn đã biết) hoặc điện thoại đã xê dịch — kiểm tra bằng ảnh kiểm tra trôi |
| Hỏi mã truy cập | Nhập mã 6 số in ở cửa sổ PowerShell |

---

## 8. Một buổi làm thật — từ lúc chuẩn bị đến lúc kết thúc

Phần này kể lại **một buổi thử nghiệm điển hình theo đúng thứ tự bạn sẽ làm**: cầm gì, bấm gì, màn hình hiện gì, ghi số nào vào ô nào. Các con số trong ví dụ là **minh hoạ**, không phải kết quả thật.

Buổi mẫu: **Buổi 2** (TN3 → TN6), khoảng 2 giờ, ở sân nhà, bảng A3, điện thoại Android, mạng 4G.

### 8.1 Tối hôm trước (15 phút)

1. Kiểm tra đủ đồ ở mục 1.1. Sạc đầy điện thoại và laptop.
2. In bảng (nếu chưa), đo cạnh vùng mã. Ví dụ đo được **249 mm** → ghi ra giấy.
3. Trên laptop tạo thư mục `bang_chung\B02_2026-10-25\` với 4 thư mục con `anh_goc`, `man_hinh`, `may_tao`, `bang_ghi`.
4. Chép `docs\bang_ghi\BANG_GHI_SO_LIEU.xlsx` vào `bang_ghi\`. Mở file, trang **Thông tin buổi**: điền ngày, nơi, điện thoại, cỡ bảng A3, cạnh 249 mm. Nếu là buổi đầu tiên: điền "Ngày chốt tiêu chí".
5. Trong ứng dụng camera: bật **hẹn giờ 3 giây**, tắt HDR, ống kính 1×.

### 8.2 Đến nơi, dựng cảnh (≈ 20 phút)

1. Chọn chỗ sàn phẳng, đủ sáng, **không có người qua lại** trong khung hình.
2. Dán bảng lên tấm bìa cứng, đặt nằm phẳng giữa khu vực thử.
3. Dựng giá cách tâm bảng khoảng **1,5 m** theo mặt đất, kẹp điện thoại nhìn xiên xuống bảng. Mở camera xem thử: bảng nằm khoảng giữa khung, còn khoảng 1 m sàn mỗi phía.
4. Đo bằng thước: độ cao ống kính so với mặt đất (ví dụ **1,10 m**) và khoảng cách theo mặt đất từ chân giá tới tâm bảng (ví dụ **1,50 m**) → ghi vào **Thông tin buổi**.
5. **Chưa dán băng dính** các điểm đo — phải biết hướng +Y của bảng trước (8.3).

### 8.3 Bật máy và hiệu chỉnh (≈ 15 phút)

1. Laptop: mở PowerShell trong thư mục `webtest`, chạy `.\run_tailscale.ps1`. Màn hình in hai dòng `Laptop: …` và `Điện thoại: …`. **Để nguyên cửa sổ này suốt buổi.**
2. Laptop: mở đường dẫn `Laptop:` bằng trình duyệt. Thanh trên cùng: **Máy chủ** xanh, chờ **Model AI** báo đã nạp.
   Bản đồ tự cập nhật mỗi 3 giây kể cả khi cửa sổ bị che.
3. (Tuỳ chọn) Mở thêm một cửa sổ PowerShell thứ hai ở thư mục `webtest` nếu muốn dùng script dán cả cột (mục 8.6). Không bắt buộc.
4. Điện thoại: tắt Wi-Fi, bật Tailscale (thấy biểu tượng chìa khoá trên thanh trạng thái), mở đường dẫn `Điện thoại:`. Trang báo "Laptop: CHƯA hiệu chỉnh" là bình thường.
5. Sàn chỉ có bảng. Điện thoại bấm **"📷 Chụp ảnh hiệu chỉnh (có bảng)"** → camera mở → bấm chụp (hẹn giờ 3 s) → bấm ✓ dùng ảnh. Điện thoại hiện thanh tiến độ rồi **"Đã gửi"**.
6. Laptop **Bước 1**: trong khung "Ảnh từ điện thoại" có ảnh nhỏ vừa gửi → bấm vào (viền nổi lên). Ô "Cạnh thật của bảng" gõ **249**. Bấm **Dò bảng**.
7. Màn hình hiện ảnh bảng có viền xanh lá, mũi tên **xanh dương (+Y)** và **đỏ (+X)**, các dòng ví dụ "Bảng chiếm **182,4 px** — đủ lớn", "Góc mở ống kính: **79,5°** — đọc từ ảnh" → ghi số px, góc mở, nguồn góc mở và mọi cảnh báo vàng vào **Thông tin buổi**.
   Nếu ghi "mặc định 66°": tra tiêu cự 35 mm của máy (mục 2.1), gõ góc mở vào ô, bấm Dò bảng lại.
8. **Nhìn ảnh dò để biết hướng +Y ngoài đời:** mũi tên xanh dương chỉ về cạnh nào của tờ giấy thì đó là +Y (ví dụ cạnh phía bức tường). Mũi tên đỏ là +X, nằm bên phải +Y khi nhìn từ trên xuống.
9. **Bây giờ mới dán băng dính** (gốc = tâm hình vuông đen):
   - Dọc hướng +Y: 0,5 m — 1,0 m — 1,5 m.
   - Dọc hướng +X: 0,5 m — 1,0 m.
   - Hai điểm chéo: đi +Y 1,0 m rồi sang +X 0,5 m; đi +Y 1,0 m rồi sang −X 0,5 m.
   Viết toạ độ lên băng dính, ví dụ "Y1,0 X0,5". Các toạ độ này **đã điền sẵn** ở cột B, C trang **TN3 Vị trí**.
10. **Bước 2**: bấm một điểm bất kỳ trên bản đồ (đó là vị trí bảng). Kéo đầu mũi tên **thẳng lên trên** tới khi ô "Hướng cạnh +Y" hiện **0°** (dùng ⟲ ⟳ chỉnh từng 1°).
11. **Bước 3**: điểm xanh lá (camera) phải nằm về phía chân giá so với bảng, vùng xanh phủ phần sàn camera nhìn thấy. Đúng thì bấm **Lưu hiệu chỉnh** → Bước 4 mở ra.
12. Màn hình Bước 1 có dòng **"Độ cao camera máy ước lượng: 1,07 m"** → ghi vào Thông tin buổi (không cần mở file nào). Chép `calibration\WEB-DEMO.json` vào `may_tao\`.

Từ đây **không chạm vào giá điện thoại nữa**; chỉ chạm màn hình thật nhẹ khi bấm chụp.

### 8.4 TN3 — cả loạt 14 lần (≈ 45 phút)

Với mỗi dòng của trang TN3 (ví dụ dòng 3: Y thật = 1,0; X thật = 0):

1. Đặt túi nilon trải phẳng sao cho **tâm túi** nằm đúng điểm băng dính "Y1,0 X0".
2. Điện thoại bấm **"📷 Chụp ảnh rác"** → chụp (hẹn giờ, tay rời điện thoại) → ✓.
3. Điện thoại hiện "Đang phân tích…", vài giây sau ra ảnh có vùng tô, và dưới đó:
   ```
   Số vùng rác: 1
   Tổng diện tích: 0,128 m²
   ⏱ Thời gian: 6,4 s (…)
   Vị trí so với tâm bảng (lên = +Y, phải = +X):
   Vùng 1: Y = 1,082 m; X = -0,031 m · 0,128 m²
   ```
   Laptop tự hiện "Có ảnh mới từ điện thoại" và cùng danh sách vùng ở Bước 4; vùng đỏ trên bản đồ có số 1.
4. **Gõ ngay vào Excel**, trang TN3, dòng 3: cột *Model nhận ra?* để **Có**, cột *Y đọc trên trang* = **1,082**, cột *X đọc trên trang* = **−0,031** → ô xám tự hiện Lệch **0,085 m**, Mức **ĐẠT**; khung kết quả xanh lá phía trên tự cập nhật.
5. Lấy túi ra, sang dòng tiếp theo.

Nếu ảnh có **2 vùng** (túi + mảnh lạ): chọn vùng của **túi** (gần điểm đặt; số thứ tự trên điện thoại khớp số in trên vùng đỏ ở bản đồ). Danh sách còn có cả vùng **tờ bảng** (Y, X gần 0), cứ bỏ qua. Model không thấy túi: cột *Model nhận ra?* chọn **Không**, để trống Y, X, ghi chú "không nhận ra"; có thể thử lại bằng vật màu nổi hơn ở một dòng mới.

Thỉnh thoảng chụp màn hình laptop (Win + Shift + S), lưu vào `man_hinh\` làm minh hoạ.

### 8.5 TN4, TN5, TN6 (≈ 40 phút)

- **TN4:** điền tên vật + dài × rộng ở trang TN4 (diện tích thật tự tính). Mỗi lần gửi, đọc diện tích của vùng vật trên điện thoại ("Vùng 1: … · 0,135 m²") và gõ vào cột *Diện tích máy báo*.
- **TN5** (ghi tay, 3 số/ảnh): mỗi ảnh đặt 3–5 vật lẫn lộn, chụp, nhìn ảnh khoanh trên điện thoại, ghi số vật đặt / số vật được tô / số vùng tô nhầm.
- **TN6:** một vật, không đụng gì, chụp 5 lần liên tiếp; mỗi lần đọc Y, X, diện tích của vùng vật trên điện thoại và gõ vào trang TN6.

### 8.6 Lấy vị trí và diện tích vùng rác

**Cách chính: đọc ngay trên trang** (điện thoại, hoặc laptop Bước 4, hoặc bấm vào vùng đỏ trên bản đồ). Máy tính Y, X từ chính toạ độ nó đã vẽ lên bản đồ, đổi ngược về mét quanh bảng, nên khớp 1–1 với những gì bạn thấy. Đã kiểm bằng test: vật đặt biết trước ở (Y = 1,0; X = 0,4) được đọc lại là Y ≈ 1,015; X ≈ 0,403 ở cả hai hướng mũi tên thử.

- Y và X theo hai cạnh của **tờ bảng** (mũi tên xanh dương = +Y, đỏ = +X), không phụ thuộc hướng mũi tên đặt ở Bước 2.
- Máy **không loại vùng nào**. Model hay khoanh luôn **tờ bảng** thành một vùng rác (Y, X gần 0, diện tích cỡ 0,15 m²); vùng đó vẫn có trong danh sách và **trong "Tổng diện tích"**. Khi đọc, bỏ qua vùng ở tâm bảng, chỉ lấy vùng của vật. Muốn dùng "Tổng diện tích" thì trừ **diện tích nền** đo từ ảnh chỉ có bảng (xem TN4).
- Chỉ các lần gửi **sau khi cập nhật** mới có Y, X (đã lưu vào `observations.json`). Các lần gửi cũ chỉ có diện tích.

**Cách thay thế — script `doc_so_lieu.py`** (khi đã chụp hết loạt và muốn dán cả cột; chỉ **đọc** `observations.json`, không chạy lại model):

Chạy trong PowerShell thứ hai, thư mục `webtest` (`PY` = `..\..\..\.venv\Scripts\python.exe -B`):

| Lệnh | Dùng khi |
|---|---|
| `PY doc_so_lieu.py --last 14 --dan yx --copy` | TN3: khối Y, X của 14 lần gửi, tự chép vào clipboard rồi Ctrl+V vào ô đầu cột |
| `PY doc_so_lieu.py --last N --dan a --copy` | TN4: khối diện tích |
| `PY doc_so_lieu.py --last 5 --dan yxa --copy` | TN6: khối Y, X, diện tích |
| `PY doc_so_lieu.py --last 3` | Chỉ xem bảng (không dán) |
| `PY doc_so_lieu.py --calib <thư mục buổi>\may_tao\WEB-DEMO.json --obs <thư mục buổi>\may_tao\observations.json --csv B02_vi_tri.csv` | Đọc lại số liệu của **một buổi cũ** từ bản sao lưu, ghi ra CSV |

Script lấy theo **thứ tự thời gian** (N lần gửi gần nhất), mỗi ảnh một dòng; ảnh nhiều vùng dùng dòng "gộp" (cộng mọi vùng), nên chỉ đúng khi ảnh chỉ có vùng của vật. **Phải dùng đúng file hiệu chỉnh của buổi đó** (`--calib`); script cảnh báo khi một lần gửi dùng hiệu chỉnh khác.

**Cách dự phòng — đọc bằng mắt trên bản đồ** (khi không chạy được script; ghi chú "đọc tay"):

Vì mũi tên đã để **0°**: **lên trên = +Y**, **sang phải = +X**, xuống dưới = −Y, sang trái = −X.

1. Phóng to bản đồ (nút **+** hoặc lăn chuột) tới khi bảng, mũi tên và vùng đỏ chiếm phần lớn màn hình.
2. Xác định **tâm bảng** (gốc của mũi tên xanh) và **tâm vùng đỏ** (điểm giữa vùng đỏ, ước lượng bằng mắt).
3. Chọn thước tham chiếu: **mũi tên xanh dài đúng 2 m** (nửa mũi tên = 1 m, một phần tư = 0,5 m) hoặc **thanh tỉ lệ** góc dưới trái (ví dụ ghi "50 cm").
4. **Chiều dọc:** vùng đỏ ở trên tâm bảng → Y dương; ở dưới → Y âm. Ví dụ cao hơn tâm bảng nhỉnh hơn nửa mũi tên → Y ≈ 1,08 m.
5. **Chiều ngang:** lệch sang phải → X dương; sang trái → X âm. Ví dụ lệch trái rất ít → X ≈ −0,03 m.
6. **Cách đo chính xác hơn:** đặt thước kẻ lên màn hình, đo bằng mm rồi quy đổi:
   **số mét = (mm đo được ÷ mm của thanh tỉ lệ) × độ dài thanh tỉ lệ**.
   Ví dụ thanh "50 cm" dài 24 mm trên màn hình, khoảng dọc đo được 52 mm → Y = 52 ÷ 24 × 0,5 = **1,08 m**.
7. Luôn chụp màn hình để kiểm lại được.

> Đọc bằng mắt sai khoảng vài cm — vẫn dùng được, nhưng ưu tiên số của script. Trong báo cáo ghi rõ vị trí lấy bằng cách nào.

### 8.7 Kết thúc buổi (≈ 15 phút) — đừng bỏ qua

1. Bỏ hết vật, chụp **ảnh kiểm tra trôi** bằng "Chụp ảnh hiệu chỉnh"; laptop chọn ảnh đó, bấm Dò bảng (**không lưu**). So số px với lúc đầu (ví dụ 182,4 → 182,1: không xê dịch). Ghi vào Thông tin buổi. Lệch nhiều (vài px trở lên, hoặc ảnh dò trông khác hẳn) → ghi "có xê dịch" và ghi chú cho số liệu TN3–TN6 của buổi.
2. **Sao lưu ngay** vào `may_tao\`: `webtest\data\observations.json` và `calibration\WEB-DEMO.json`.
3. Chép ảnh gốc từ điện thoại sang `anh_goc\` bằng cáp; đặt tên theo quy ước mục 2.3 (Excel chỉ ghi tên ảnh ở trang TN1 nếu cần).
4. Mở từng trang TN: xem khung kết quả xanh lá, viết **Nhận xét của bạn** (1–3 câu). Ví dụ: "Đạt 12/14 lần; lệch lớn nhất 0,31 m ở điểm chéo xa 1,12 m; các điểm gần bảng lệch dưới 10 cm."
5. Ghi `ghi_chu.txt`: thời tiết, sự cố (mất mạng, model không nhận ra…), điều muốn làm khác lần sau.
6. Tắt máy chủ: **Ctrl+C** trong cửa sổ PowerShell. Tắt Tailscale trên điện thoại nếu không dùng nữa.
7. Chỉ khi đã sao lưu xong mới bấm "Xoá tất cả" trên trang laptop (nếu muốn buổi sau bắt đầu sạch).

### 8.8 Những lúc dễ lúng túng

| Tình huống | Làm gì |
|---|---|
| Laptop không tự hiện ảnh mới sau ~5 giây | Bấm F5 và ghi chú vào TN1 (bản đồ đã được sửa để tự cập nhật cả khi cửa sổ bị che) |
| Script báo "CẢNH BÁO … hiệu chỉnh KHÁC" | Các dòng đó chụp trước lần hiệu chỉnh lại — đọc bằng bản sao lưu `WEB-DEMO.json` cũ qua `--calib` |
| Lỡ chạm làm điện thoại lệch | Dừng. Hiệu chỉnh lại từ 8.3 bước 5 (băng dính giữ nguyên nếu bảng không dịch), ghi chú "hiệu chỉnh lại lúc …" |
| Một vật bị chia thành 2 vùng đỏ | TN3: lấy tâm của cả cụm; TN4: cộng diện tích hai vùng; ghi chú |
| Có vùng đỏ ở chỗ không có rác | Ghi vào TN5 cột "khoanh nhầm"; ở TN3/TN4 bỏ qua vùng đó |
| Điện thoại báo lỗi khi gửi | Chép nguyên văn vào TN1 cột "Thông báo lỗi", Kết quả = LỖI, rồi xử lý theo mục 7 |
| Không chắc đọc vị trí đúng | Ghi số tốt nhất đọc được, ghi chú "khó đọc", giữ ảnh màn hình |

## 9. Chụp ở chỗ khác: chế độ 2 "Tự chọn vị trí"

Ở đầu Bước 1 trên trang laptop có công tắc **Chế độ vị trí bảng**. Mỗi lần mở trang mặc định là **chế độ 1** (như các mục trên).

**Khi nào dùng chế độ 2:** khi bạn đổi chỗ chụp so với lần hiệu chỉnh trước và không muốn bản đồ lấy lại vị trí cũ (hoặc điểm mặc định ở TP.HCM) làm điểm xuất phát.

**Cách làm ở chỗ mới:**
1. Đặt bảng xuống đất ở chỗ cần đo; đặt điện thoại trên chân giá cách bảng vài mét; chụp ảnh có bảng.
2. Trang laptop: chọn **chế độ 2**, bấm "Hiệu chỉnh lại" (nếu đã có hiệu chỉnh), chọn ảnh bảng, bấm **Dò bảng**.
3. Bước 2: bản đồ chưa có vị trí bảng. Phóng bản đồ tới chỗ bạn đặt bảng, **bấm đúng chỗ đó** (nên chọn chỗ có vật dễ nhận trên bản đồ: góc vỉa hè, cột đèn, nắp cống). Kéo núm mũi tên để cạnh +Y trùng hướng thật (canh theo vạch đường hoặc mép nhà).
4. Bước 3: nhìn vùng xanh có khớp mặt đất không, rồi **Lưu hiệu chỉnh**.
5. Bước 4: giữ nguyên điện thoại, đặt rác, gửi ảnh.

**Lưu ý:**
- Vị trí do bấm tay nên **sai số tuyệt đối trên bản đồ khoảng vài mét** (chưa được đo thử); độ chính xác so với bảng (Y, X) không đổi.
- Từ lúc bấm "Dò bảng" mới đến khi bấm "Lưu hiệu chỉnh", ảnh gửi từ điện thoại vẫn được vẽ theo hiệu chỉnh **cũ**. Chỉ gửi ảnh có rác sau khi đã Lưu.
- Các lần chụp cũ vẫn nằm ở chỗ cũ trên bản đồ (mỗi lần gửi lưu toạ độ riêng).
- Không đổi được chế độ khi đã dò bảng mà chưa Lưu.
