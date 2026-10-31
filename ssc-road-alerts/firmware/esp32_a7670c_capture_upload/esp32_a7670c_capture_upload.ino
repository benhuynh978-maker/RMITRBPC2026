/*
  ESP32-CAM (AI-Thinker) + SIMCom A7670C — Chup anh that va gui len backend
  ------------------------------------------------------------------------
  CHAY TRUOC: esp32_a7670c_diagnostics.ino — chi chuyen sang sketch nay khi
  ca 8 buoc chan doan da bao [OK], dac biet la buoc lay gio mang va HTTPS.

  Luong hoat dong:
    1. Khoi tao camera OV2640 (chan AI-Thinker chuan)
    2. Ket noi A7670C vao mang di dong (APN)
    3. Chup 1 anh JPEG
    4. Gui anh qua HTTPS (TLS qua modem) toi
       POST /api/esp32/cameras/{cameraId}/capture
    5. In phan hoi tu backend ra Serial Monitor

  Thu vien can cai: "TinyGSM" by Volodymyr Shymanskyy (qua Library Manager)
  Board: Tools > Board > ESP32 Arduino > "AI Thinker ESP32-CAM"
*/

#define TINY_GSM_MODEM_SIM7600
#include <TinyGsmClient.h>
#include "esp_camera.h"

// ==================== MANG / A7670C — CHINH THEO PHAN CUNG THAT ====================
#define MODEM_RX_PIN 14   // ESP32 GPIO nhan  <- chan TX cua A7670C
#define MODEM_TX_PIN 15   // ESP32 GPIO gui   -> chan RX cua A7670C
#define MODEM_BAUD   115200

const char apn[]      = "v-internet";  // APN nha mang cua SIM
const char gprsUser[] = "";
const char gprsPass[] = "";
// =====================================================================================

// ==================== BACKEND — CHINH SAU KHI DA TAO CAMERA THAT ====================
const char server[]    = "worrier-zoom-laboring.ngrok-free.dev"; // domain ngrok hien tai
const int  port        = 443;
const char cameraId[]  = "CAM-DEMO-001";  // PHAI trung camera_id da dang ky tren backend
const char deviceKey[] = "123";           // PHAI trung DEVICE_API_KEY dang cau hinh o backend
// =====================================================================================

// ==================== CHAN CAMERA — CHUAN AI-THINKER ESP32-CAM ====================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
// =====================================================================================

HardwareSerial SerialAT(2);
TinyGsm modem(SerialAT);
TinyGsmClientSecure client(modem);

unsigned long captureCounter = 0;

bool initCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM; config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM; config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM; config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size   = FRAMESIZE_SVGA; // 800x600 — can bang chat luong / dung luong goi tin
    config.jpeg_quality = 12;             // so nho hon = chat luong cao hon, file nang hon
    config.fb_count      = 2;
  } else {
    config.frame_size   = FRAMESIZE_CIF;  // 400x296 — an toan khi khong co PSRAM
    config.jpeg_quality = 15;
    config.fb_count      = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[LOI] Khoi tao camera that bai: 0x%x\n", err);
    return false;
  }
  return true;
}

bool connectNetwork() {
  SerialAT.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  delay(3000);

  if (!modem.testAT(10000)) { Serial.println("[LOI] Modem khong phan hoi AT"); return false; }
  modem.restart();

  if (modem.getSimStatus() != SIM_READY) { Serial.println("[LOI] SIM chua san sang"); return false; }
  if (!modem.waitForNetwork(60000L))     { Serial.println("[LOI] Khong dang ky duoc mang"); return false; }
  if (!modem.gprsConnect(apn, gprsUser, gprsPass)) { Serial.println("[LOI] Khong ket noi duoc APN"); return false; }

  Serial.print("[OK] Da ket noi mang, IP: ");
  Serial.println(modem.getLocalIP());
  return true;
}

// Tra ve chuoi rong "" neu khong lay duoc gio — noi goi phai tu kiem tra.
String isoTimeNow() {
  int year, month, day, hour, minute, second;
  float tz;
  if (modem.getNetworkTime(&year, &month, &day, &hour, &minute, &second, &tz)) {
    char buf[25];
    snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02dZ", year, month, day, hour, minute, second);
    return String(buf);
  }
  return "";
}

bool uploadFrame(camera_fb_t* fb) {
  String capturedAt = isoTimeNow();
  if (capturedAt == "") {
    Serial.println("[LOI] Khong lay duoc thoi gian tu mang, huy gui anh (backend se tu choi timestamp thieu).");
    return false;
  }

  captureCounter++;
  String observationId = "ESP32-" + String((uint32_t)millis()) + "-" + String(captureCounter);

  Serial.print("Dang ket noi TLS toi server...");
  if (!client.connect(server, port)) {
    Serial.println(" THAT BAI");
    return false;
  }
  Serial.println(" OK");

  String path = String("/api/esp32/cameras/") + cameraId + "/capture";

  client.print(String("POST ") + path + " HTTP/1.1\r\n");
  client.print(String("Host: ") + server + "\r\n");
  client.print("Content-Type: image/jpeg\r\n");
  client.print(String("Content-Length: ") + fb->len + "\r\n");
  client.print(String("X-API-Key: ") + deviceKey + "\r\n");
  client.print(String("X-Observation-Id: ") + observationId + "\r\n");
  client.print(String("X-Captured-At: ") + capturedAt + "\r\n");
  client.print("ngrok-skip-browser-warning: true\r\n");
  client.print("Connection: close\r\n\r\n");

  size_t sent = client.write(fb->buf, fb->len);
  Serial.printf("Da gui %u / %u byte anh (observation_id=%s, captured_at=%s)\n",
                (unsigned)sent, (unsigned)fb->len, observationId.c_str(), capturedAt.c_str());

  String response = "";
  unsigned long timeoutStart = millis();
  while (client.connected() && millis() - timeoutStart < 15000) {
    while (client.available()) {
      response += (char)client.read();
      timeoutStart = millis();
    }
  }
  client.stop();

  Serial.println("--- Phan hoi tu backend ---");
  Serial.println(response);
  Serial.println("--- Het phan hoi ---");

  bool ok = response.indexOf("HTTP/1.1 200") >= 0 || response.indexOf("HTTP/1.1 202") >= 0;
  Serial.println(ok ? "[OK] Gui anh thanh cong" : "[LOI] Backend tu choi anh, xem noi dung phan hoi o tren de biet ly do");
  return ok;
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println();
  Serial.println("===== ESP32-CAM: CHUP ANH & GUI QUA A7670C =====");

  if (!initCamera()) {
    Serial.println("Dung lai vi camera loi. Kiem tra day cap camera (FPC) da cam chat chua.");
    while (true) delay(1000);
  }
  Serial.println("[OK] Camera san sang");

  // Anh dau tien sau khi khoi tao thuong bi lech mau/hong — chup bo qua 1 lan.
  camera_fb_t* warmup = esp_camera_fb_get();
  if (warmup) esp_camera_fb_return(warmup);

  if (!connectNetwork()) {
    Serial.println("Dung lai vi khong co mang. Chay lai sketch chan doan (esp32_a7670c_diagnostics.ino) de xem chi tiet loi o buoc nao.");
    while (true) delay(1000);
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[LOI] Chup anh that bai (frame buffer rong)");
    while (true) delay(1000);
  }
  Serial.printf("[OK] Da chup anh: %u byte\n", (unsigned)fb->len);

  uploadFrame(fb);
  esp_camera_fb_return(fb);

  Serial.println("===== HOAN TAT MOT LAN CHUP =====");
}

void loop() {
  // Sketch nay chi chup + gui 1 lan de test cho de doc log.
  // Khi da chay on dinh, chuyen doan "chup + uploadFrame" vao loop() kem delay()
  // (vi du delay(5UL*60UL*1000UL) de chup moi 5 phut) va nen goi lai connectNetwork()
  // dinh ky de xu ly truong hop mat song/rot mang.
}
