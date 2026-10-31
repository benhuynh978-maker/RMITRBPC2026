/*
 CHI DE TEST CAMERA — khong lien quan A7670C/modem/backend gi ca.

 Muc dich: tach rieng camera ra khoi phan modem dang loi, de biet chac
 camera (va chan cam cau hinh) co hoat dong dung khong, truoc khi quay
 lai go loi UART voi A7670C.

 Dung WiFi co san cua chinh ESP32-S3 (khong qua modem) de xem anh truc
 tiep tu trinh duyet may tinh/dien thoai cung mang WiFi.

 Cach dung:
   1. Dien WIFI_SSID / WIFI_PASS ben duoi.
   2. Nap sketch, mo Serial Monitor (115200 baud).
   3. Doi dong "[OK] Mo trinh duyet: http://..." roi mo dung URL do.
   4. Thay anh truc tiep tu camera -> camera va chan cau hinh dung.
      Khong thay / loi -> van de o camera hoac chan, khong phai modem.

 Chan camera: giong het file production (da xac nhan khop 100% voi board).
 Tools > PSRAM phai la "OPI PSRAM" (giong cac file khac).
*/
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"

// ===== DIEN WIFI CUA BAN O DAY =====
const char *WIFI_SSID = "Lau2-5-8";
const char *WIFI_PASS = "Ktxchv@2018";
// =====================================

// ==================== CHAN CAMERA — GIONG FILE PRODUCTION, DA XAC NHAN KHOP BOARD ====================
#define XCLK_GPIO_NUM      15
#define SIOD_GPIO_NUM       4
#define SIOC_GPIO_NUM       5
#define Y9_GPIO_NUM         16
#define Y8_GPIO_NUM         17
#define Y7_GPIO_NUM         18
#define Y6_GPIO_NUM         12
#define Y5_GPIO_NUM         10
#define Y4_GPIO_NUM          8
#define Y3_GPIO_NUM          9
#define Y2_GPIO_NUM         11
#define VSYNC_GPIO_NUM       6
#define HREF_GPIO_NUM        7
#define PCLK_GPIO_NUM       13
#define PWDN_GPIO_NUM       -1
#define RESET_GPIO_NUM      -1
// =====================================================================================

WebServer server(80);

bool initCamera() {
  if (!psramFound()) {
    Serial.println("[LOI] Khong tim thay PSRAM. Kiem tra Tools > PSRAM = \"OPI PSRAM\".");
    return false;
  }
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM; c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sscb_sda = SIOD_GPIO_NUM; c.pin_sscb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  // 20MHz (thay vi 10MHz) — OV5640 chay on dinh toc do nay, anh muot hon.
  c.xclk_freq_hz = 20000000; c.pixel_format = PIXFORMAT_JPEG;
  // UXGA (1600x1200) — gan sat toi da cam bien ho tro on dinh qua JPEG phan cung
  // cua OV5640 (toi da that la QSXGA 2592x1944, nhung de o do stream se rat
  // cham/giat). Muon anh "chup 1 tam" o do phan giai cao nhat, doi FRAMESIZE_UXGA
  // thanh FRAMESIZE_QSXGA ben duoi va dung /capture, khong dung /stream.
  c.frame_size = FRAMESIZE_UXGA;
  c.jpeg_quality = 8; // thang 0-63, SO CANG NHO CHAT LUONG CANG CAO (nguoc truc giac)
  c.fb_count = 2; c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[LOI] Khoi tao camera that bai: 0x%x\n", err);
    return false;
  }

  // Dat lai toan bo can bang trang/phoi sang ve che do TU DONG ngay sau init —
  // day la cach sua pho bien nhat cho loi "anh bi xanh/ngat mau" voi OV5640 +
  // thu vien esp32-camera: trang thai mac dinh cua cam bien sau reset doi luc
  // khong o dung che do AWB tu dong. Neu sua xong van con xanh, xem /control
  // ben duoi de tu chinh tay qua trinh duyet.
  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    s->set_whitebal(s, 1);      // bat can bang trang tu dong (AWB)
    s->set_awb_gain(s, 1);      // bat AWB gain
    s->set_wb_mode(s, 0);       // 0 = Auto (1..4 la cac mode co dinh: Sunny/Cloudy/Office/Home)
    s->set_exposure_ctrl(s, 1); // bat phoi sang tu dong (AEC)
    s->set_aec2(s, 1);          // thuat toan AEC nang cao (on dinh hon voi OV5640)
    s->set_ae_level(s, 0);      // muc bu phoi sang, -2..2, 0 = mac dinh
    s->set_gain_ctrl(s, 1);     // bat tu dong tang ich (AGC)
    s->set_gainceiling(s, (gainceiling_t)0);
    s->set_bpc(s, 1);           // khu diem anh hong (bad pixel correction)
    s->set_wpc(s, 1);           // khu diem anh trang (white pixel correction)
    s->set_lenc(s, 1);          // bu toi vien anh (lens correction)
    s->set_special_effect(s, 0); // 0 = khong hieu ung dac biet
    s->set_saturation(s, 0);    // -2..2, 0 = mac dinh — tang len neu mau nhat
    Serial.println("[OK] Da dat lai AWB/AEC/AGC ve che do tu dong.");
  }

  Serial.println("[OK] Camera khoi tao thanh cong.");
  return true;
}

// Trang chu: hien anh truc tiep (MJPEG) + nut chup 1 tam + vai nut chinh nhanh.
void handleRoot() {
  String html =
      "<html><body style='font-family:sans-serif;text-align:center'>"
      "<h3>Test camera ESP32-S3 (khong qua modem)</h3>"
      "<img src='/stream' style='max-width:95%;border:1px solid #ccc'><br><br>"
      "<a href='/capture'>Chup 1 tam JPEG rieng (xem ro chi tiet hon stream)</a><br><br>"
      "<b>Chinh nhanh:</b><br>"
      "Bao hoa mau: "
      "<a href='/control?var=saturation&val=-2'>-2</a> "
      "<a href='/control?var=saturation&val=0'>0</a> "
      "<a href='/control?var=saturation&val=1'>+1</a> "
      "<a href='/control?var=saturation&val=2'>+2</a><br>"
      "Che do can bang trang: "
      "<a href='/control?var=wb_mode&val=0'>Auto</a> "
      "<a href='/control?var=wb_mode&val=1'>Nang</a> "
      "<a href='/control?var=wb_mode&val=2'>May</a> "
      "<a href='/control?var=wb_mode&val=3'>Van phong</a><br>"
      "Do sang (ae_level): "
      "<a href='/control?var=ae_level&val=-2'>-2</a> "
      "<a href='/control?var=ae_level&val=0'>0</a> "
      "<a href='/control?var=ae_level&val=2'>+2</a><br>"
      "<small>Chinh song URL dang /control?var=TEN&val=SO cho cac thong so khac "
      "(brightness, contrast, quality, framesize...) neu can.</small>"
      "</body></html>";
  server.send(200, "text/html", html);
}

// Chinh thong so cam bien truc tiep qua URL, vi du:
//   /control?var=saturation&val=2
//   /control?var=framesize&val=10   (xem bang FRAMESIZE trong esp_camera.h: 10=UXGA, 13=QSXGA...)
// Khong can nap lai firmware moi lan muon thu mot thong so khac.
void handleControl() {
  sensor_t *s = esp_camera_sensor_get();
  if (!s) { server.send(500, "text/plain", "Chua co sensor"); return; }
  if (!server.hasArg("var") || !server.hasArg("val")) {
    server.send(400, "text/plain", "Can 2 tham so: var va val"); return;
  }
  String var = server.arg("var");
  int val = server.arg("val").toInt();
  int rc = 0;
  if (var == "framesize") rc = s->set_framesize(s, (framesize_t)val);
  else if (var == "quality") rc = s->set_quality(s, val);
  else if (var == "brightness") rc = s->set_brightness(s, val);
  else if (var == "contrast") rc = s->set_contrast(s, val);
  else if (var == "saturation") rc = s->set_saturation(s, val);
  else if (var == "special_effect") rc = s->set_special_effect(s, val);
  else if (var == "wb_mode") rc = s->set_wb_mode(s, val);
  else if (var == "awb") rc = s->set_whitebal(s, val);
  else if (var == "awb_gain") rc = s->set_awb_gain(s, val);
  else if (var == "aec") rc = s->set_exposure_ctrl(s, val);
  else if (var == "aec2") rc = s->set_aec2(s, val);
  else if (var == "ae_level") rc = s->set_ae_level(s, val);
  else if (var == "aec_value") rc = s->set_aec_value(s, val);
  else if (var == "agc") rc = s->set_gain_ctrl(s, val);
  else if (var == "agc_gain") rc = s->set_agc_gain(s, val);
  else if (var == "gainceiling") rc = s->set_gainceiling(s, (gainceiling_t)val);
  else if (var == "hmirror") rc = s->set_hmirror(s, val);
  else if (var == "vflip") rc = s->set_vflip(s, val);
  else { server.send(400, "text/plain", "Khong biet bien: " + var); return; }
  Serial.printf("[CONTROL] %s = %d (rc=%d)\n", var.c_str(), val, rc);
  server.sendHeader("Location", "/");
  server.send(303); // quay lai trang chu de xem ngay ket qua tren /stream
}

// Chup 1 tam, tra ve dung 1 file JPEG — de kiem tra chat luong/mau sac ro hon stream.
void handleCapture() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { server.send(500, "text/plain", "Chup anh that bai"); return; }
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// Stream video truc tiep kieu MJPEG — trinh duyet hien duoc thang nhu video.
void handleStream() {
  WiFiClient client = server.client();
  String boundary = "frame";
  String header = "HTTP/1.1 200 OK\r\n"
                   "Content-Type: multipart/x-mixed-replace; boundary=" + boundary + "\r\n\r\n";
  client.print(header);

  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) { Serial.println("[LOI] Chup frame that bai trong luc stream."); break; }
    client.printf("--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
                  boundary.c_str(), (unsigned)fb->len);
    client.write(fb->buf, fb->len);
    client.print("\r\n");
    esp_camera_fb_return(fb);
    if (!client.connected()) break;
    delay(30); // tam nghi ngan, tranh chiem het CPU khi stream lien tuc
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n===== TEST CAMERA QUA WIFI (khong dung modem) =====");

  if (!initCamera()) {
    Serial.println("Dung lai vi camera loi. Khong nap tiep A7670C cho toi khi camera chay duoc o day.");
    while (true) delay(1000);
  }

  Serial.printf("Dang ket noi WiFi \"%s\"...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(300);
    Serial.print(".");
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[LOI] Khong ket noi duoc WiFi. Kiem tra lai WIFI_SSID/WIFI_PASS.");
    while (true) delay(1000);
  }

  server.on("/", handleRoot);
  server.on("/capture", handleCapture);
  server.on("/stream", handleStream);
  server.on("/control", handleControl);
  server.begin();

  Serial.println("\n[OK] Mo trinh duyet (cung mang WiFi voi may tinh/dien thoai):");
  Serial.print("     http://");
  Serial.println(WiFi.localIP());
}

void loop() {
  server.handleClient();
}
