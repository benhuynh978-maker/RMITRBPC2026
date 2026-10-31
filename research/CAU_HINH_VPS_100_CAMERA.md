# Vì sao thuê VPS 4 vCPU / 8 GB RAM / 100 GB NVMe cho 100 camera

> Ngày: 2026-10-27. Đối tượng: đội kỹ thuật và người quyết định thuê máy chủ.
> Số "đo" lấy từ báo cáo dự án; số "ước lượng" là của người viết và phải đo lại trên VPS thật (mục 6).

## 1. Kết luận

**Thuê VPS 4 vCPU, 8 GB RAM, 100 GB NVMe, chỉ chạy CPU, không cần GPU.** Đây là mức tối thiểu để 100 camera chạy ổn: nhỏ hơn thì hết công suất xử lý, lớn hơn thì chưa cần.

| Thông số | Chọn | Lý do trong một câu |
|---|---|---|
| CPU | 4 vCPU | Chạy 2 worker AI song song, có dư công suất để kịp hạn 15 phút |
| RAM | 8 GB | 2 worker AI + Node + hệ điều hành + cơ sở dữ liệu, còn dư khoảng 2 GB |
| Đĩa | 100 GB NVMe | Giữ 14 ngày ảnh (khoảng 28–56 GB) và còn chỗ cho hệ thống |

## 2. Tải của 100 camera

- 100 camera × 1 ảnh/phút = **1,7 ảnh/giây** (đo: ảnh khoảng 15 KB, nên mạng chỉ cỡ 0,2 Mbps, không đáng kể).
- Phân tích 1 ảnh trên CPU mất **0,55 giây** (đo, báo cáo mục 5.6). Một phút cần 100 × 0,55 = **55 giây CPU**, tức một worker phải chạy khoảng 92% thời gian.
- Kết quả chỉ được dùng nếu ra trong **15 phút** sau khi chụp (đo từ thiết kế hệ thống). Hàng đợi dồn quá 15 phút thì ảnh bị bỏ phí.

## 3. Vì sao 4 vCPU

1. **Một worker không đủ.** Công suất tối đa của một worker là 60 / 0,55 ≈ 109 ảnh/phút, trong khi cần 100. Gần như không còn dư.
2. **vCPU của VPS chậm hơn máy phát triển.** Một vCPU thường là một luồng của nhân vật lý, nên 0,55 s có thể thành 0,8–1 s (ước lượng). Khi đó một worker chỉ xử lý được 60–75 ảnh/phút, **thiếu**.
3. **Cần dư công suất.** Ảnh dồn lại khi mất mạng rồi gửi bù, hoặc khi khởi động lại. Công suất dư giúp hàng đợi tự tiêu hết trong vài phút thay vì trượt hạn 15 phút.
4. **2 worker, mỗi worker 2 vCPU** là cấu hình nhỏ nhất đạt cả ba yêu cầu trên. 2 vCPU thì chỉ chạy được 1 worker, nên không đủ.

## 4. Vì sao 8 GB RAM

Ước lượng: mỗi worker AI (PyTorch + mô hình YOLO26s-seg) khoảng 2 GB × 2 = 4 GB; Node khoảng 0,5 GB; hệ điều hành, reverse proxy và cơ sở dữ liệu khoảng 1 GB. Tổng khoảng 5,5 GB. **4 GB sẽ sát giới hạn và dễ bị hệ điều hành tắt tiến trình**; 8 GB còn dư cho lúc cao điểm.

## 5. Vì sao 100 GB NVMe

- Mỗi ngày: 100 camera × 720 ảnh (12 giờ ban ngày) × 15 KB ≈ **1,1 GB ảnh gốc**. Ảnh khoanh vùng thêm 1–3 GB (ước lượng, chưa đo). Tổng **2–4 GB/ngày**.
- Giữ **14 ngày** ≈ 28–56 GB, cộng hệ điều hành, ứng dụng, mô hình và cơ sở dữ liệu khoảng 15 GB: vừa trong 100 GB, còn dư.
- Giữ 30 ngày (60–120 GB) thì **không đủ**. Cần đặt thời gian giữ ảnh tối đa 14–21 ngày; việc này cũng phục vụ yêu cầu quyền riêng tư.
- **NVMe** vì hệ thống ghi liên tục (1,7 ảnh/giây, mỗi ảnh kèm cập nhật dữ liệu).

## 6. Vì sao không chọn khác

| Phương án | Vì sao không |
|---|---|
| 2 vCPU / 4 GB | Chỉ chạy được 1 worker, không còn công suất dư; RAM sát giới hạn |
| 8 vCPU / 16 GB | Thừa ở mức 100 camera; chỉ cần khi vượt khoảng 200 camera |
| Có GPU | Mỗi ảnh khoảng 0,03 s trên GPU, nhanh hơn rất nhiều, nhưng 100 camera chưa cần và giá thuê cao hơn đáng kể; xem xét lại khi vượt khoảng 500 camera hoặc khi cần huấn luyện lại |

## 7. Điều kiện đi kèm (không thuê máy là đủ)

1. **Cho phép chạy 2 worker AI.** Code hiện tại chỉ hỗ trợ 1 worker. Cần sửa cơ chế nhận job để hai worker không giành cùng một ảnh.
2. **Chuyển kho dữ liệu sang cơ sở dữ liệu** (SQLite hoặc Postgres). Phiên bản hiện tại ghi nguyên cả một file JSON mỗi lượt kết quả, khoảng 72.000 lượt mỗi ngày với 100 camera. Báo cáo (Phụ lục 3) cũng ghi cần chuyển khi mở rộng.
3. **Chạy thử tải trước khi chốt:** 100 camera mô phỏng trên VPS thật, đo thời gian mỗi ảnh, RAM mỗi worker và dung lượng ảnh khoanh vùng, rồi sửa các số ước lượng ở trên. Nếu một ảnh mất quá 1,2 s thì nâng lên 8 vCPU.
4. Hai việc trên làm trong bản sao `ssc-v2`, không sửa hệ thống chính đang chạy.
