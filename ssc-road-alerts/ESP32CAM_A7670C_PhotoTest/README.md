# ESP32-CAM + A7670C: chụp một ảnh, POST về camera 0001

## Chạy

1. Giải nén. Mở `ESP32CAM_A7670C_PhotoTest.ino` trong thư mục cùng tên. Giữ `root_ca.h` cùng thư mục. Không bỏ các sketch test cũ vào thư mục này vì sẽ trùng setup()/loop().
2. Arduino IDE: cài board package **esp32 by Espressif Systems**, bản 3.x; chọn **AI Thinker ESP32-CAM**. Camera dùng thư viện có sẵn trong board package.
3. Thay `DIEN_DEVICE_API_KEY_CUA_BAN` bằng DEVICE_API_KEY backend (hoặc ADMIN_API_KEY nếu backend không đặt key riêng). Không cần gửi key cho người khác.
4. Nạp code, bỏ nối IO0–GND nếu đã dùng để nạp, rồi reset để chạy. Serial Monitor **115200 baud**.
5. Code chờ modem 15 giây, đợi mạng, cấu hình HTTPS, chụp một ảnh rồi POST một lần. Bấm RST sẽ chụp ảnh mới, ID mới. Không có lịch chụp tự động hay retry.

## Dây hiện tại

| ESP32-CAM | A7670C breakout |
|---|---|
| IO13 (TX) | RXD |
| IO14 (RX) | TXD |
| GND | GND |

Giữ nguồn phù hợp với board đang test HTTP thành công. Không dùng microSD vì IO13/IO14 dành cho UART. Đây là sơ đồ cho breakout có mức UART tương thích ESP32, không phải hướng dẫn nối trực tiếp module trần.

## Request

URL: `https://worrier-zoom-laboring.ngrok-free.dev/api/esp32/cameras/0001/capture`

- Body: JPEG nhị phân thô, VGA khi có PSRAM, QVGA khi không có PSRAM.
- Content-Type: `image/jpeg`.
- X-API-Key: key bạn điền.
- X-Observation-Id: MAC + số ngẫu nhiên, tự tạo mới mỗi lần chạy.
- X-Captured-At: **dữ liệu test cố định `2026-01-01T00:00:00Z`, không phải giờ chụp thật**, theo yêu cầu chỉ thử gửi ảnh. Với quy tắc backend bạn cung cấp, thời điểm cũ không vi phạm giới hạn tương lai. Không dùng bản này để đánh giá thời gian quan sát thực tế.

HTTP 202 = ảnh mới được xếp hàng; HTTP 200 = backend chấp nhận (theo hợp đồng endpoint). HTTP 401/403: kiểm tra key; 404: đường dẫn/camera/backend; 409: ID trùng nội dung khác; 413: kích thước; 415: Content-Type. Xem body phản hồi để biết chính xác; mã 200 từ trang ngrok/HTML không chứng minh đã lưu ảnh, hãy đối chiếu observation trên backend.

## Vì sao dùng HTTPPOSTFILE

Vẫn dùng bộ HTTP tích hợp của modem giống test HTTPACTION thành công. `AT+HTTPPOSTFILE="cam_request.bin",1,1,1` gửi toàn bộ HTTP header + body trong file nội bộ modem, tránh giới hạn USERDATA 256 byte và khác biệt cách escape xuống dòng giữa firmware. Không phải multipart và không cần thẻ nhớ. Request có Content-Length chính xác bằng số byte JPEG, không tính phần header.

File tạm chứa ảnh và key, được xóa sau khi nhận kết quả POST. Nếu mất điện/UART timeout giữa chừng thì file có thể còn; lần chạy sau sẽ xóa trước khi tạo lại. Đây là bản test một lần, không thích hợp chụp liên tục lâu dài vì ghi flash modem mỗi lần. Bản này giới hạn ảnh 150KB để truyền UART thuận lợi (backend vẫn có giới hạn riêng 5MB).

## HTTPS và thời gian

HTTP GET example.com thành công chưa xác nhận HTTPS ngrok hoạt động. Bản này không chạy CNTP, không tắt kiểm tra chứng chỉ, và không đổi sang HTTP khi HTTPS lỗi.

`AT+CCLK?` in giờ modem; giờ này phải đúng hiện tại để xác thực hạn chứng chỉ. Nếu mạng chưa cấp giờ, điền `MODEM_CLOCK` theo giờ UTC hiện tại trước khi nạp, ví dụ định dạng `26/09/16,14:05:00+00` (đây chỉ là ví dụ, phải thay bằng giờ lúc bạn test). MODEM_CLOCK để rỗng sẽ giữ giờ modem. Giá trị captured-at mẫu không được dùng làm đồng hồ TLS.

`root_ca.h` chứa ISRG Root X1, là CA ứng viên từ bản trước. **Chưa xác minh trực tiếp được chuỗi chứng chỉ hiện tại của domain ngrok của bạn**; nếu server dùng root khác, thay ROOT_CA bằng PEM của root đúng và đổi CA_FILE sang tên mới để modem nạp lại. Xem chuỗi chứng chỉ trong trình duyệt ở domain ngrok. Không thay authmode thành 0 để gửi key. SNI được bật. Việc kiểm tra tên miền phụ thuộc TLS implementation của firmware modem; chưa xác minh riêng hành vi này trên V11.0.01.

Nếu HTTPPOSTFILE báo ERROR ngay: gửi log và kết quả `AT+HTTPPOSTFILE=?` từ sketch đọc AT; cần xác nhận firmware này hỗ trợ send_header=1. Nếu lỗi nội bộ modem 6xx/7xx hoặc reset: giữ nguyên log từ CCLK đến HTTPPOSTFILE để phân biệt lỗi TLS/mạng/UART. Không thể kết luận lỗi nguồn chỉ từ GET/POST thất bại.

## Phạm vi kiểm tra

Đã đối chiếu cú pháp AT với tài liệu SIMCom và rà soát cách ghép request. Chưa biên dịch bằng ESP32 board package trong môi trường này, chưa chạy bản chụp/POST mới trên phần cứng của bạn. GET HTTP là phần bạn đã xác nhận chạy thành công, không phải kết quả của sketch này.

Tài liệu: [SIMCom A76XX AT Command Manual V1.09](https://files.waveshare.com/wiki/A7670E-Cat-1-GNSS-HAT/A76XX_Series_AT_Command_Manual_V1.09.pdf), mục 13.2.1 (CFTRANRX), 16.2.8 (HTTPPOSTFILE), 19 (TLS). Pin camera: [Espressif CameraWebServer](https://github.com/espressif/arduino-esp32/blob/master/libraries/ESP32/examples/Camera/CameraWebServer/camera_pins.h).
