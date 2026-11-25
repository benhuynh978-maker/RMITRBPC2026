# Hướng dẫn chụp khảo sát (1 trang)

**Mỗi điểm = 1 ảnh có cả bảng ArUco và rác.** Mỗi điểm khoảng 30–60 giây.

## Chuẩn bị (trước khi ra trường)

- Laptop: mở PowerShell, `cd research\exp03_ban_do_khao_sat_truong`, chạy `.\run_tailscale.ps1`. Giữ cửa sổ đó mở.
- Điện thoại: bật Tailscale, mở đường dẫn `.../phone#<mã>` mà laptop in ra. Thêm vào màn hình chính cho dễ mở.
- Có tờ bảng in (A3, cạnh vùng mã 250 mm, in 100% không "Fit to page"), đặt phẳng, không nhăn.
- Camera điện thoại để chế độ ảnh thường. **Không zoom**: hãy tiến lại gần (zoom có thể làm góc nhìn thật khác góc nhìn ghi trong ảnh, m² sẽ lệch).

## Ngoài hiện trường

1. Chọn chỗ có rác. Đặt bảng **xuống đất ngay cạnh rác**, mặt đất phẳng.
2. Đặt bảng **cùng một hướng ở mọi điểm** (ví dụ cạnh trên của bảng luôn hướng ra phía bạn nhìn khi đứng sau bảng; chọn một mốc như tường/hàng cây). Nhờ vậy tối nay chỉ chỉnh hướng một lần.
3. Đứng sau bảng (phía có chữ), chụp **1 ảnh thấy trọn tờ bảng và đám rác**, chụp hơi chéo xuống đất, không đứng quá xa (bảng phải đủ lớn, ≥ 50 px trên ảnh; ảnh mẫu của repo, bảng ~145 px, chụp từ cao ~1,5 m cách bảng ~1,5 m là đạt).
4. **Nhìn kết quả trên điện thoại ngay:**
   - Thẻ **xanh** "tìm thấy bảng" → xong, qua điểm kế.
   - Thẻ **đỏ** ("không thấy bảng", "bảng quá nhỏ") → chụp lại ngay tại chỗ (ảnh lỗi vẫn được lưu, tối nay xoá sau).
   - Có thể có cảnh báo vàng; "không có thông tin tiêu cự" nghĩa là ảnh bị nén qua ứng dụng khác, m² sẽ lệch.
5. Tránh có người trong khung hình (ảnh sẽ được đưa cho ban giám khảo xem).
6. Nhớ ghi/chụp **tên chỗ** (cổng, căng-tin…) để tối nay đặt tên điểm.

Nếu không có Tailscale/4G: chụp bình thường, rồi chép **ảnh gốc** (cáp USB, Google Drive "tải xuống bản gốc", AirDrop; **không** gửi kiểu "ảnh" qua Zalo/Messenger) vào thư mục `thu_muc_anh`, và bấm "Nạp ảnh từ thư mục" trên laptop.

## Tối nay: rà soát (≈ 10–15 phút)

1. Mở trang laptop. Các điểm hiện ở danh sách bên trái. Điểm chưa đặt vị trí sẽ **tự chờ bạn bấm bản đồ**: bấm đúng chỗ đặt bảng (phóng to đến khi nhìn thấy đường, mái nhà; ô "Đến toạ độ" để dán toạ độ từ Google Maps). Sau mỗi lần bấm tự chuyển sang điểm kế.
2. Chỉnh **hướng chụp chung** (ô trên cùng, 0° = Bắc, 90° = Đông) cho đến khi vùng xanh "camera thấy" (và vùng rác) khớp với mặt đất thật trên bản đồ. Điểm nào đặt khác hướng thì tích "Hướng riêng". Có thể kéo ghim cho đúng vị trí.
3. Đổi tên điểm. Điểm nào AI khoanh sai: bấm vùng đỏ → "Ẩn vùng này". Rác bị sót: "Vẽ thêm vùng", bấm quanh vùng rác, "Xong" (hiện m² ngay, gắn nhãn "vẽ tay").
4. Xoá điểm/ảnh lỗi hoặc ảnh có người ("Xoá điểm"), hoặc bỏ tích "Đưa vào bản trình bày".
5. Xem cảnh báo "chồng nhau" (hai điểm chụp cùng một mảnh đất) và xử lý: xoá bớt hoặc ẩn vùng trùng.
6. Bấm **Xuất bản trình bày** (cần Internet để tải bản đồ nền, một lần). Đợi báo "Xong".

## Trước giờ trình bày

- Mở `data\exports\trinh_bay\index.html` bằng cách bấm đúp, **ngắt Wi-Fi** và kiểm tra: bản đồ nền, vùng đỏ, ảnh bằng chứng đều hiện.
- Chép cả thư mục `trinh_bay` (hoặc `trinh_bay.zip`) sang USB làm dự phòng; chụp màn hình bản đồ (Win+Shift+S) làm bản dự phòng cuối.
- Khi nói: "khảo sát N điểm ngày …, chỉ ở các điểm đã chụp; AI còn bỏ sót rác nên có vùng bổ sung bằng tay (đã đánh dấu); vị trí đặt bằng tay, sai số vài mét". Không nói là "toàn bộ trường" hay "thời gian thực".
