# Mô tả sản phẩm — hệ thống giám sát rác đường phố và miệng cống (HV Tech, SSC 2026)

Tài liệu này dành cho một AI/session khác đọc để **hình dung sản phẩm, công nghệ và giải pháp** ở trạng thái hoàn chỉnh. Nó mô tả kết quả cuối, không đi vào từng bước làm. Cần chi tiết hơn thì xem `research/TAI_LIEU_HE_THONG_RD.md` (tài liệu kỹ thuật dài, có cả lịch sử thử nghiệm). Tên sản phẩm chưa được ghi ở đây.

---

## 1. Sản phẩm là gì

Một hệ thống dùng **camera cố định + AI** để theo dõi **rác trên đường phố** và **tình trạng miệng cống**, rồi cho người quản lý xem trên **bản đồ web** và cảnh báo sớm khi có nguy cơ **ngập cục bộ** do rác che cống.

- Khách hàng hướng tới: công ty môi trường / đơn vị quản lý đô thị. Họ cần thứ **đơn giản, dễ hiểu, dùng được ngay** — không phải một bảng con số khó giải thích.
- Phạm vi: ban ngày, thời tiết tốt, **một camera theo dõi một miệng cống** cùng khu vực quanh nó.
- Đội thi: HV Tech (THPT chuyên Hùng Vương, TP.HCM), cuộc thi Sustainable Society Challenge 2026 (SDG 11).
- Không tuyên bố "dự báo ngập" hay "thời gian thực": camera chụp định kỳ (khoảng 1 phút một ảnh) và trạng thái cống được làm mượt nên có độ trễ nhỏ.

Hệ thống trả lời được ba câu hỏi:
1. **Miệng cống đang bị che nhiều hay ít?** (mức che miệng cống, chia 3 trạng thái)
2. **Xung quanh có bao nhiêu rác?** (mật độ rác của khu vực, chia mức)
3. **Rác nằm ở đâu, rộng bao nhiêu?** (vùng rác vẽ thẳng lên bản đồ thật, có diện tích m²)

---

## 2. Cách hệ thống hoạt động (nhìn tổng thể)

```
Camera ESP32-CAM (chụp ~60 s/ảnh, gửi qua 4G)        Điện thoại (kênh chụp thay thế/thử nghiệm)
            │                                                   │
            └──────────────►  Backend Node (lưu JSON, hàng chờ job) ◄──────────┘
                                   │  job ảnh mới
                                   ▼
                       AI worker Python (YOLO26s-seg)
                       ├─ nhận ra vùng "Rác" và "Cống" trong ảnh
                       ├─ tính mức rác và mức che miệng cống
                       └─ (nếu camera đã hiệu chỉnh) chiếu vùng rác lên bản đồ
                                   │ kết quả
                                   ▼
                 Backend: gộp theo tuyến đường, làm mượt, chấm mức cảnh báo (+ yếu tố mưa)
                                   ▼
                 Web React + Leaflet: bản đồ, mức cảnh báo, vùng rác, trạng thái cống
```

Ý chính: **AI chạy trên ảnh gốc, rồi mới "dịch" kết quả ra con số và ra bản đồ.** Phần "dịch" là giá trị khác biệt của sản phẩm.

---

## 3. Các thành phần

| Thành phần | Làm gì | Công nghệ |
|---|---|---|
| Camera | Chụp định kỳ, gửi ảnh có mã quan sát để không bị trùng khi gửi lại | ESP32-CAM + modem 4G A7670C, đi qua Tailscale Funnel |
| Backend | Nhận ảnh, giữ hàng chờ job, lưu kết quả, gộp theo tuyến, tính mức cảnh báo, lấy mưa | Node.js (không framework, lưu JSON ghi nguyên tử) |
| AI worker | Nhận job → chạy model → ra chỉ số + ảnh đã khoanh → trả kết quả | Python, YOLO26s-seg (2 lớp: Rác, Cống) |
| Web | Bản đồ + mức cảnh báo + chi tiết từng camera | React 19, TypeScript, Vite, React-Leaflet |
| Lớp "bản đồ rác" | Vẽ vùng rác thật lên bản đồ, đo diện tích | Python (OpenCV, ArUco) + Leaflet |
| Mưa | Đẩy cảnh báo lên một bậc khi sắp/đang mưa | Open-Meteo |

---

## 4. Giải pháp lõi thứ nhất: chỉ số che miệng cống đáng tin

**Vấn đề của cách làm cũ:** chỉ số tính từ vùng "cống" mà model nhìn thấy. Nhưng khi rác che kín cống thì model **không còn thấy cống** → ra "không có giá trị" đúng lúc nguy hiểm nhất. Ngoài ra con số nhảy lên xuống từng ảnh khiến cảnh báo nhấp nháy.

**Giải pháp:**
1. **Vùng miệng cống cố định theo camera (ROI).** Vì camera đứng yên, người cài đặt khoanh một lần vùng miệng cống trên ảnh sạch (AI đề xuất, người xem rồi mới chấp nhận). Mức che = phần rác nằm **trong vùng đó** / diện tích vùng đó. Cống bị che kín vẫn đo được.
2. **Làm mượt theo thời gian.** Lấy **trung vị của 5 lần đo gần nhất**, rồi chuyển trạng thái bằng **ngưỡng có trễ** (vào mức cao khó hơn thoát ra) → ba trạng thái dễ hiểu: **thấp / theo dõi / cần dọn**. Cần ít nhất 3 lần đo mới kết luận; dữ liệu quá 15 phút thì hiển thị "chưa rõ" thay vì giả vờ còn đúng.
3. **Không dùng độ tin cậy của model để loại ảnh** (độ tin cậy cũ phản trực giác: càng nhiều rác càng thấp). Chỉ giữ như nhãn tham khảo. Ảnh quá tối bị đánh dấu "không dùng được" thay vì cho ra con số sai.

Đã kiểm trên dữ liệu thử: cách ROI chính xác hơn rõ cách cũ và không bao giờ "thiếu giá trị"; làm mượt giảm số lần đổi trạng thái khoảng 40 lần (84 → 2 trên chuỗi mô phỏng).

---

## 5. Giải pháp lõi thứ hai: vẽ vùng rác lên bản đồ thật

**Ý tưởng:** biến "rác nằm ở đâu trong ảnh" thành "rác nằm ở đâu trên bản đồ, rộng bao nhiêu m²".

**Cách làm (đơn giản về mặt người dùng):**
1. Lúc lắp camera, đặt **một bảng đánh dấu ArUco** (một tờ giấy in, kích thước thật biết trước — A3, vùng mã 250 mm; có bản A4 dự phòng) **nằm phẳng trên mặt đất** trong tầm nhìn, chụp **một ảnh hiệu chỉnh**.
2. Phần mềm nhìn bảng trong ảnh và **tự tính camera đang đứng ở đâu, nhìn hướng nào, cao bao nhiêu** so với bảng.
3. Người cài đặt chỉ làm thêm hai việc: **nhập một con số** (cạnh thật của bảng, đo bằng thước) và **chấm vị trí + hướng bảng trên bản đồ**. Có bước xem trước (vùng mặt đất camera thấy) để tự kiểm bằng mắt, rồi lưu.
4. Từ đó mọi ảnh sau **tự động**: mỗi điểm ảnh được "bắn" thành một tia xuống mặt đất, giao điểm cho ra toạ độ mét quanh bảng, xoay theo hướng la bàn rồi đổi sang kinh/vĩ độ. Vùng rác (mặt nạ do model khoanh) thành **đa giác trên bản đồ có diện tích m²**.

**Quy tắc đã chốt:** nếu bảng trên ảnh nhỏ hơn **50 pixel** (chụp quá xa hoặc bảng quá nhỏ) thì **từ chối hiệu chỉnh** — muốn đạt thì chụp gần hơn hoặc dùng bảng lớn hơn. Không có ngoại lệ hay cờ ghi đè, để hệ thống đơn giản và dễ quản lý. Bảng A3 dùng tốt tới khoảng 2–3 m; camera đặt xa hơn cần bảng lớn hơn (công cụ in có thể sinh bảng cỡ bất kỳ).

**Vì sao chọn bảng đánh dấu** (so với chấm điểm tay hay cảm biến): làm một lần lúc lắp, các lần sau tự động, sai số thấp nhất trong các cách đã cân nhắc, và không cần thêm cảm biến phức tạp.

---

## 6. Giao diện

- **Web chính (React + Leaflet):** bản đồ tuyến đường với mức cảnh báo, chi tiết từng camera (ảnh đã khoanh, mức che miệng cống, mức rác, trạng thái cống đã làm mượt), vùng rác vẽ trên bản đồ (lần mới nhất đỏ, các lần cũ vàng, bấm vào xem m²). Nhãn hiển thị cho người dùng là "Mức che miệng cống" (không dùng "Tỉ lệ ngập" gây hiểu nhầm).
- **Trang thiết lập/thử (chạy riêng, dùng cho hiệu chỉnh và kiểm chứng):** laptop có 4 bước (dò bảng → đặt bảng lên bản đồ → xem trước & lưu → gửi ảnh có rác), bản đồ tự cập nhật khi có ảnh mới. **Trang điện thoại** có hai nút lớn "Chụp ảnh hiệu chỉnh" và "Chụp ảnh rác" mở camera gốc của máy, gửi về laptop qua mạng riêng Tailscale, bảo vệ bằng mã 6 số. Điện thoại là cách chụp thay thế/thử nghiệm; camera chính thức vẫn là ESP32.

---

## 7. Công nghệ gói gọn

- **AI:** YOLO26s-seg (ultralytics), 2 lớp Rác/Cống, ảnh vào 1024 px; dữ liệu train `Try1` chia theo nhóm để tránh rò rỉ.
- **Hình học:** OpenCV (dò ArUco, giải vị trí camera bằng PnP), mô hình camera pinhole; góc mở ống kính đọc từ thông tin ảnh (EXIF) nếu có, mặc định 66° (ESP32).
- **Backend:** Node.js thuần, lưu JSON ghi nguyên tử, API khoá theo vai (admin/thiết bị/AI). **Bản thiết lập/thử:** FastAPI.
- **Frontend:** React 19, TypeScript, Vite, Leaflet (nền OpenStreetMap).
- **Mạng:** Tailscale (Funnel cho thiết bị, mạng riêng cho thử nghiệm).

---

## 8. Quyết định thiết kế quan trọng (để hiểu "tại sao")

1. **AI chạy trên ảnh gốc**, không nắn/biến đổi ảnh trước — vì model chỉ được huấn luyện trên ảnh thường; phép chiếu chỉ áp lên **kết quả** (mặt nạ).
2. **Camera cố định + hiệu chỉnh một lần** thay vì tính lại mỗi ảnh — đơn giản, ổn định, sai số thấp.
3. **Một camera = một miệng cống**, cộng rác khu vực xung quanh.
4. **Làm mượt có trễ** để cảnh báo không nhấp nháy; thà báo "chưa rõ" còn hơn báo sai.
5. **Nhập tay đúng một số** (cạnh bảng) và **chặn khi bảng < 50 px**: ít thao tác, ít chỗ sai.
6. **Phát triển trên bản sao** (`ssc-v2`, cổng riêng), không sửa hệ thống đang chạy; chứng minh khả thi xong mới chuyển hướng sang.

---

## 9. Hạn chế và phạm vi áp dụng (đọc kỹ)

- Chỉ **ban ngày, thời tiết tốt**; đêm/mưa lớn/phản chiếu nằm ngoài phạm vi.
- **Camera phải đứng yên** sau hiệu chỉnh; nếu bị xê dịch, bản đồ sẽ sai mà hệ thống không tự biết.
- **Mặt đất coi như phẳng.** Vật cao (chai đứng, đống rác cao) bị vẽ phóng to/kéo dài ra xa camera; m² là "vết chiếu trên ảnh", vật dẹt cho kết quả đúng nhất.
- **Độ chính xác bản đồ** phụ thuộc cỡ bảng trên ảnh, góc mở ống kính (sai góc mở → sai vị trí/kích thước), và cách người cài đặt chấm vị trí/hướng bảng.
- **Model còn yếu:** bỏ sót khá nhiều rác (độ phủ khoảng 44% trên tập kiểm; bỏ sót ở khoảng 2/3 ảnh đường phố thử). Cải thiện model là hướng phát triển tiếp theo; các cơ chế trên (ROI, làm mượt) được thiết kế để chịu được model chưa hoàn hảo.
- Ảnh ESP32 640×480 nén nặng khác ảnh train (ảnh điện thoại chất lượng cao) — rủi ro lệch miền.

---

## 10. Số liệu đã đo (để biết cái gì đã có bằng chứng)

- **Che cống (ROI vs cũ):** trên 76 cống thử, cách cũ thiếu giá trị ở 47 cống (trong đó 16/18 cống bị che nặng), cách ROI không thiếu cống nào; sai số trung bình trên cùng tập: 6.0 điểm % (ROI) so với 8.4 (cũ). Mẫu nhỏ, ROI lấy từ nhãn chuẩn nên là cận trên.
- **Làm mượt:** số lần đổi trạng thái giảm 84 → 2 trên chuỗi mô phỏng, độ trễ khi nhảy bậc 3 khung. Không kết luận được về sai số trung bình.
- **Vẽ lên bản đồ (ảnh giả lập, điều kiện lý tưởng):** vật 0,3 m trong khoảng 2 m quanh bảng lệch tâm vài cm, diện tích sai khoảng +4…+11%; bảng 250 mm nhận diện ổn tới vài mét, độ chính xác tư thế là điểm yếu khi bảng nhỏ trên ảnh.
- **Chưa có:** sai số vị trí vẽ trên bản đồ đo bằng **ảnh thật ngoài hiện trường** → *[điền sau khi đo thực địa]*. Tiêu chí khả thi đặt trước: lệch ≤ ~0,2 m trong khoảng 2 m quanh bảng.

---

## 11. Mã nguồn nằm ở đâu (để đọc tiếp)

- Hệ thống chính (**không sửa**): `ssc-road-alerts/` (backend Node + web React), `inference/` (worker), `test-WebUI-modelAI/` (demo giám khảo). Trọng số model: `runs/segment/runs/train/baseline_v1_rev2/weights/best.pt`.
- Bản phát triển: `ssc-v2/` (bản sao + logic che cống mới; xem `README-V2.md`).
- Vẽ rác lên bản đồ: `research/exp02_ve_rac_len_ban_do/` (lõi: `calibrate_aruco.py`, `project_mask.py`; trang thiết lập/thử: `webtest/`).
- Thí nghiệm che cống: `research/exp01_chi_so_che_cong/` (có `REPORT.md`).
- Tài liệu kỹ thuật dài: `research/TAI_LIEU_HE_THONG_RD.md`.

## 12. Cách làm việc với dự án này

- Không sửa hệ thống chính; thử nghiệm trên bản sao/thư mục riêng, cổng khác.
- Giữ hệ thống **đơn giản**; không tự thêm cờ/điều kiện mới khi người dùng chưa yêu cầu.
- Điểm nào chưa chắc về lý thuyết hay logic thì **hỏi người dùng trước**, đừng tự chốt.
- Báo cáo trung thực, kể cả hạn chế và kết quả không đạt; tiêu chí đo đặt trước khi chạy.
- Ngôn ngữ giao diện, lỗi và tài liệu: **tiếng Việt**.
