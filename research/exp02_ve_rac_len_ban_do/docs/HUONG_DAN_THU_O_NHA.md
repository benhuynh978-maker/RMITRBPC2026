# Hướng dẫn thử ở nhà: ảnh có rác -> hiện lên bản đồ

Mục đích: tự kiểm xem cách làm này có **khả thi và đúng** không, bằng điện thoại, một tờ bảng in và vài món đồ
ngay trong nhà/sân nhà. Không cần biết kỹ thuật. Làm lần lượt từng phần.

Mẹo chung: cứ chụp **nhiều ảnh dư**, ảnh nào cũng ghi lại (đặt tên file theo thứ tự) để lúc báo kết quả có đủ bằng chứng.

---

## Phần A. Chuẩn bị (làm một lần)

1. **In bảng**: mở file `outputs/marker_A3.pdf` (trong thư mục `research/exp02_ve_rac_len_ban_do/`), in khổ **A3**,
   chọn **100% / Kích thước thật (Actual size)**, **tắt** "Vừa khít trang / Fit to page". Dùng giấy trắng, không bóng.
   (Chi tiết in: `docs/HUONG_DAN_IN_BANG.md`.)
2. **Đo cạnh vùng mã bằng thước**: đo một cạnh của hình vuông đen lớn (từ mép đen này tới mép đen kia, không tính viền trắng).
   Kết quả phải gần **250 mm**. Ghi lại **con số bạn đo được** — số này sẽ nhập vào ô "Cạnh thật của bảng (mm)" ở trang web.
   (Nếu bạn đo ra 247 thì nhập 247, đừng nhập 250.)
3. **Dán** tờ giấy lên mặt phẳng cứng (tấm ván, bìa cứng dày, foam board), không để nhăn/cong/phồng.
   Đặt tấm bảng **NẰM PHẲNG trên sàn** (không dựng đứng, không treo tường).
4. **Bật máy chủ** theo `webtest/README.md` rồi mở http://127.0.0.1:8120/ trên laptop. Thanh trên cùng phải báo
   "Máy chủ: hoạt động".

## Phần B. Dựng điện thoại CỐ ĐỊNH

Điện thoại phải đứng yên suốt cả buổi thử (từ ảnh hiệu chỉnh tới mọi ảnh có rác). Nhích một chút là kết quả sai.

- Kẹp điện thoại vào **giá đỡ / chân máy / kệ chắc**, hướng xuống sàn, nhìn thấy bảng và khoảng sàn xung quanh.
- Dùng **ống kính chính 1×**, **không zoom**, **không dùng góc siêu rộng**, **không dùng chế độ chân dung / chế độ làm đẹp**.
  **Tắt HDR** nếu có.
- **Giữ nguyên hướng ngang hoặc dọc** của điện thoại xuyên suốt (đừng lúc ngang lúc dọc).
- **Khoảng cách**: đặt bảng cách điện thoại **không quá ~2 m** (đo theo đường nhìn). Cạnh bảng trên ảnh phải **>= 50 px**.
  Cách làm: chụp thử một ảnh rồi thử ở bước 1 của trang — trang sẽ báo "Bảng chiếm ... px". Dưới 50 px (nhãn đỏ) thì
  đưa điện thoại lại gần bảng hơn hoặc nâng/hạ cho nhìn rõ hơn rồi chụp lại.
- Nhìn bảng hơi **xiên** (khoảng 45° so với phương thẳng đứng) thì tốt hơn nhìn thẳng từ trên xuống.
- Đủ sáng, không chói, không có bóng đổ vắt ngang bảng. Ảnh phải **nét**, bốn góc bảng nằm trọn trong khung hình.

## Phần C. Chụp ảnh hiệu chỉnh và làm bước 1–3 trên trang

1. Với điện thoại đã cố định, đặt bảng trên sàn, chụp **ảnh hiệu chỉnh** (chỉ có bảng, chưa bày rác). Chuyển ảnh sang laptop.
2. **Bước 1**: chọn ảnh, nhập "Cạnh thật của bảng (mm)" bằng số bạn đo ở Phần A, để trống "Góc mở ống kính"
   (ảnh điện thoại thường có sẵn thông tin), bấm "Dò bảng". Kiểm tra: nhãn xanh "đủ lớn", ảnh có mũi tên +Y (xanh dương) và +X (đỏ). Kết quả dò (ảnh, số px, nguồn góc mở ống kính, cảnh báo vàng) vẫn hiện nguyên ở bước 1 khi bạn làm tiếp bước 2–3; chỉ khi bấm "Lưu hiệu chỉnh" thì bước 1 mới tự thu gọn (bấm vào tiêu đề bước 1 để mở lại xem).
   **Góc mở ống kính**: nếu ảnh không có thông tin ống kính (EXIF), trang dùng góc mở **66°** (của camera ESP32).
   Điện thoại thường khoảng **70–85°**, nên **hãy nhập góc mở vào ô "Góc mở ống kính" nếu bạn biết**; nếu không, kích thước và vị trí
   vùng đỏ có thể bị lệch. Trang cho biết nguồn góc mở ("đọc từ ảnh" hay "mặc định 66°") ngay dưới ảnh dò bảng.
   Ghi lại xem trục +Y của bảng chỉ về phía nào trong phòng (ví dụ "chỉ về phía cửa sổ").
3. **Bước 2**: trên bản đồ, bấm vị trí đặt bảng (đặt ở đâu cũng được, bản đồ chỉ là nền), rồi **kéo đầu mũi tên** cho
   mũi tên chỉ cùng hướng với trục +Y ngoài đời. Muốn đúng hướng la bàn thật thì dùng la bàn điện thoại; để thử độ đúng
   tương đối thì chỉ cần nhất quán.
4. **Bước 3**: nhìn vùng xanh trên bản đồ: nó có đúng hình dạng và nằm đúng chỗ so với mặt sàn mà camera thấy không?
   Điểm xanh lá (camera) có nằm đúng phía so với bảng không (đúng chỗ đặt điện thoại)? Nhích/xoay cho khớp rồi bấm "Lưu hiệu chỉnh".
   Nếu vùng xanh trông sai hẳn (camera nằm phía đối diện, vùng lật ngược), chụp lại ảnh hiệu chỉnh gần hơn/nét hơn.

## Phần D. Bày "rác" và chụp, mà KHÔNG xê dịch điện thoại

1. Bày vài món (chai, túi, hộp...) lên sàn trong vùng camera thấy. **Không chạm vào điện thoại.**
2. Chụp ảnh (cùng hướng ngang/dọc, cùng cài đặt). Chuyển sang laptop, vào **Bước 4**, chọn ảnh, bấm "Gửi và vẽ lên bản đồ".
3. Vùng đỏ hiện trên bản đồ; bấm vào vùng để xem diện tích (m²) và độ tin cậy trung bình của ảnh.
4. Chụp nhiều lần, thay đổi vị trí đồ vật giữa các lần. Mỗi lần gửi được lưu trong "Lịch sử các lần gửi"
   (lần mới nhất đỏ, các lần cũ vàng hổ phách; có thể ẩn/hiện từng lần).

## Phần E. Kiểm độ đúng bằng vật đặt ở vị trí đo sẵn

Đây là phần quan trọng nhất để biết có khả thi hay không.

1. Gốc đo là **tâm bảng** (tâm hình vuông đen lớn). Dùng thước cuộn, đánh dấu (băng dính màu) các điểm trên sàn:
   - **0,5 m** và **1 m** tính từ tâm bảng theo hướng cạnh **+Y** của bảng,
   - **0,5 m** và **1 m** tính từ tâm bảng theo hướng cạnh **+X** của bảng. Quy ước: nhìn từ trên xuống, **+X nằm bên phải của +Y** (ảnh bước 1: đỏ = +X, xanh dương = +Y).
   Thêm một điểm tuỳ ý trong khoảng 2 m quanh bảng nếu muốn (đo bằng thước từ tâm bảng, ghi lại 2 số: dọc +Y và dọc +X).
2. Đặt **2–3 vật dễ thấy** (ví dụ chai nước, túi nilon màu, hộp) lên các điểm đó, **tâm vật trùng điểm đánh dấu**.
   Mỗi lần chụp nên chỉ đặt 1–2 vật để dễ đọc kết quả.
3. Chụp (vẫn KHÔNG xê dịch điện thoại), gửi ở bước 4.
4. **Đọc kết quả**: trên bản đồ, vùng đỏ của vật phải nằm đúng chỗ so với bảng. Mũi tên xanh +Y dài **2 m** và thanh tỉ lệ
   ở góc dưới bên trái bản đồ cho bạn thước đo ngay trên màn hình: 0,5 m bằng 1/4 mũi tên, 1 m bằng 1/2 mũi tên theo hướng +Y.
   Phóng to bản đồ (nút +) để đọc rõ. Ước lượng khoảng cách (cm) từ **tâm vùng đỏ** tới **vị trí thật** (điểm bạn đo)
   bằng thanh tỉ lệ. Ghi vào bảng bên dưới.
   Lưu ý: vật đặt bên phải của +Y mà vùng đỏ hiện bên trái mũi tên (hoặc ngược lại) nghĩa là bị đảo trái-phải — hãy ghi rõ, đó là một kết quả cần báo.

### Bảng ghi sai số (điền tay)

| Lần | Vật | Vị trí thật (dọc +Y, dọc +X, m) | Vị trí trang vẽ (dọc +Y, dọc +X, m) | Lệch bao nhiêu (cm) | Ghi chú (trong khung ảnh? model có khoanh không?) |
|---|---|---|---|---|---|
| 1 | chai nước | (0,5 ; 0) | | | |
| 2 | túi | (1,0 ; 0) | | | |
| 3 | hộp | (0 ; 0,5) | | | |
| 4 | | | | | |
| 5 | | | | | |

### Tiêu chí khả thi

- **Đạt** nếu vị trí vẽ lệch **không quá khoảng 0,2 m (20 cm)** so với vị trí thật, trong khoảng **2 m quanh bảng**.
- Lệch 20–40 cm: tạm chấp nhận, cần nêu rõ điều kiện (xa bảng, ảnh mờ...).
- Lệch hơn 40 cm, hoặc vùng xanh ở bước 3 trông sai hẳn: ghi nhận "chưa đạt" kèm ảnh.
- Kết quả "không đạt" cũng có giá trị — nó cho biết chính xác chỗ nào chưa ổn.

## Phần F. Lưu ý khi model không nhận ra đồ

- Model AI được huấn luyện cho rác ngoài đường, **có thể bỏ sót đồ trong nhà** hoặc nhận nhầm. Trang sẽ báo
  "Model không phát hiện rác trong ảnh" — đó là bình thường, không phải lỗi hệ thống.
- Khi đó **vẫn đối chiếu được** vị trí bảng và camera (vùng xanh ở bước 3, điểm xanh lá) với thực tế để kiểm phần hình học.
- Thử dùng vật có **màu tương phản mạnh** với sàn (cam, đỏ, xanh) chỉ để xem model **khoanh cái gì**.
  Nếu vẫn không ra, ghi nhận và xem ảnh đã khoanh (ảnh nhỏ ở bước 4, bấm để phóng to) để biết model nhìn thấy gì.
- Vật cao (chai đứng, hộp cao) bị vẽ **phóng to/kéo dài** về phía xa camera — đó là giới hạn đã biết của cách tính
  (chỉ biết mặt đất). Vật dẹt (túi, giấy) cho kết quả đúng nhất.

## Phần G. Gửi lại cho Tech Lead

Gửi một thư mục gồm:

1. Ảnh hiệu chỉnh gốc và ảnh có rác gốc (đủ các lần chụp).
2. Ảnh chụp màn hình bước 1 (ảnh dò bảng, số px, nguồn góc mở ống kính) và màn hình bản đồ sau mỗi lần gửi
   (thấy vùng đỏ, bảng, mũi tên, thanh tỉ lệ).
3. **Bảng sai số** đã điền (Phần E), kèm số đo cạnh bảng thật và điện thoại/kiểu máy, khoảng cách điện thoại tới bảng (ước lượng).
4. Ghi chú: model có nhận ra đồ không, có hiện cảnh báo vàng nào không, có lệch/đảo hướng bất thường không.
