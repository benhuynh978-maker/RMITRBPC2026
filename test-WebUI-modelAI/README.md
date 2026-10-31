# Site thử model cho giám khảo

Site để người ngoài tải ảnh lên và nhận về ảnh đã khoanh vùng rác + 2 chỉ số.

## Vì sao tách làm 2 phần

Model cần PyTorch + GPU nên **không chạy được trên Netlify**. Vì vậy:

| Phần | Chạy ở đâu |
|---|---|
| Giao diện (`web/`) | Netlify — chỉ là HTML tĩnh |
| Model (`server/`) | Laptop của bạn, mở ra ngoài qua Tailscale Funnel |

Site này **hoàn toàn tách biệt** với `ssc-road-alerts`: không ghi `cameras.json`, không cần `camera_id`, chỉ dùng lại đúng hàm `analyze()` trong `inference/analysis.py` để không nhân bản logic model.

```
test-WebUI-modelAI/
  server/app.py      # FastAPI: nhận ảnh → chạy model → trả kết quả. Chặn spam theo IP.
  web/index.html     # Trang giao diện (deploy lên Netlify)
  web/config.js      # Địa chỉ máy chủ model — sửa 1 dòng trước khi deploy
  uploads/           # Ảnh gốc người dùng tải lên (chưa vẽ mask), tự tạo
```

---

## Bước 1 — Chạy service model trên laptop

```powershell
cd C:\Users\ASUS\Desktop\SSC\test-WebUI-modelAI\server
..\..\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8100
```

Chờ tới khi thấy `[startup] model da san sang` (mất ~5–20 giây để nạp model). Kiểm tra:

```powershell
curl.exe http://127.0.0.1:8100/api/health
```

## Bước 2 — Xem thử giao diện tại chỗ

Mở thẳng `web\index.html` bằng trình duyệt (bấm đúp vào file). Lúc này `config.js` đang trỏ `127.0.0.1:8100` nên thử được ngay mà chưa cần Netlify.

## Bước 3 — Mở service ra Internet bằng Tailscale Funnel

```powershell
tailscale funnel --bg --https=8443 http://localhost:8100
```

Tailscale sẽ in ra địa chỉ dạng `https://<tên-máy>.<đuôi>.ts.net`. Ghi lại địa chỉ này.

> Dùng cổng 8443 riêng cho site demo để không đụng cổng ESP32 đang dùng. Nếu cổng đã bận, đổi sang `--https=8444`.

## Bước 4 — Deploy giao diện lên Netlify

1. Sửa `web/config.js`, thay bằng địa chỉ Funnel ở bước 3:
   ```js
   window.SSC_API_URL = "https://ten-may.duoi.ts.net";
   ```
2. Vào [app.netlify.com](https://app.netlify.com) → **Add new site** → **Deploy manually** → kéo thả **thư mục `web`** vào.
3. Netlify trả về link dạng `https://ten-ngau-nhien.netlify.app` — đổi tên trong **Site settings → Change site name** nếu muốn.

## Bước 5 — Khóa CORS lại cho an toàn

Sau khi có link Netlify, dừng service rồi chạy lại với biến môi trường giới hạn đúng tên miền đó:

```powershell
$env:DEMO_ALLOWED_ORIGINS="https://ten-site.netlify.app"
..\..\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8100
```

Nếu bỏ qua bước này, bất kỳ trang web nào cũng gọi được API model của bạn.

---

## Chặn spam

Mặc định **5 ảnh/phút** và **50 ảnh/giờ** cho mỗi địa chỉ IP. Vượt quá sẽ nhận HTTP 429 kèm thông báo tiếng Việt và số giây phải chờ.

Đổi mức chặn bằng biến môi trường:

```powershell
$env:DEMO_RATE_PER_MINUTE="3"
$env:DEMO_RATE_PER_HOUR="20"
```

Các biến khác: `DEMO_MAX_UPLOAD_BYTES` (mặc định 8MB), `DEMO_UPLOAD_DIR`.

**Lưu ý:** IP thật được đọc từ header `X-Forwarded-For` do Tailscale Funnel gắn vào. Chỉ tin header này khi service nằm **sau** tunnel — nếu mở thẳng cổng 8100 ra Internet thì header này giả mạo được và cơ chế chặn sẽ vô hiệu.

Ngoài ra chỉ chạy được **một suy luận tại một thời điểm** (có khóa GPU), nhiều người gửi cùng lúc sẽ tự xếp hàng chứ không làm tràn bộ nhớ GPU.

## Ảnh người dùng tải lên

Lưu **bản gốc chưa vẽ mask** vào `uploads/`, đặt tên theo thời gian: `20260924-011223-652477e6.jpg`. Ảnh đã vẽ mask không lưu (trả thẳng về trình duyệt).

Đây là nguồn ảnh thực tế quý giá để đánh giá/huấn luyện lại model sau này — nhớ sao lưu thư mục này, và cân nhắc nói rõ với người dùng (trang đã có dòng ghi chú ở cuối).

## Giới hạn cần biết

- **Laptop phải bật và service phải chạy** thì giám khảo mới dùng được. Tắt máy là site báo lỗi kết nối.
- Ngưỡng mức độ rác (1/5/10/20%) trong `server/app.py` phải khớp với `ssc-road-alerts/server/config.js`. Sửa một bên thì sửa cả bên kia.
