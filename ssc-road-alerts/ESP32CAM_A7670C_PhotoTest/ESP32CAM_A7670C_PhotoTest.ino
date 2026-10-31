#include <Arduino.h>
#include "esp_camera.h"
#include "esp_system.h"
#include "root_ca.h"

// AI Thinker ESP32-CAM. Arduino-ESP32 3.x. No microSD.
// ESP IO13 (TX) -> SIM RXD; ESP IO14 (RX) <- SIM TXD; common GND.
HardwareSerial Modem(2);
const char APN[] = "m-wap";
const char API_KEY[] = "123";
const char HOST[] = "laptop-p8gad5f2.tailc4a76e.ts.net";
const char PATH[] = "/api/esp32/cameras/0001/capture";
// TEST DATA ONLY: deliberately NOT the actual capture time.
const char CAPTURED_AT[] = "2026-01-01T00:00:00Z";
// Optional: correct CURRENT modem clock if network time is unavailable.
// Format yy/MM/dd,hh:mm:ss+00 (UTC). Empty means keep network/modem time.
const char MODEM_CLOCK[] = "";
// One capture and ONE POST per reset. No NTP, Wi-Fi or automatic retries.
// TLS verifies a CA; root_ca.h must match the server certificate chain.

String rxLine;
bool desynced = false;

bool readLine(String &out) {
  while (Modem.available()) {
    char c = (char)Modem.read();
    if (c == '\r') continue;
    if (c == '\n') {
      out = rxLine; rxLine = ""; out.trim();
      if (out.length()) return true;
    } else if (rxLine.length() < 1024) {
      rxLine += c;
    } else {
      desynced = true;
      Serial.println("[STOP] Dong UART qua dai/loi. Reset de thu lai.");
      return false;
    }
  }
  return false;
}

// Wait for OK and, when requested, the asynchronous result in either order.
bool command(const String &cmd, String &reply, const char *prefix = "",
             uint32_t timeoutMs = 10000) {
  if (desynced) return false;
  Serial.println("\n> " + cmd);
  Modem.print(cmd); Modem.print('\r');
  reply = "";
  bool gotOK = false, gotResult = !prefix[0];
  uint32_t start = millis();
  while (!desynced && millis() - start < timeoutMs) {
    String s;
    if (!readLine(s)) { delay(1); continue; }
    Serial.println(s);
    if (s.startsWith("*ATREADY:") || s == "RDY") {
      desynced = true;
      Serial.println("[STOP] Modem phat ATREADY trong luc test; co the vua reset.");
      return false;
    }
    if (s == "ERROR" || s.startsWith("+CME ERROR:")) return false;
    if (s == "OK") gotOK = true;
    if (prefix[0]) {
      if (s.startsWith(prefix)) { reply = s; gotResult = true; }
    } else if (reply.length() + s.length() < 4096) {
      reply += s + '\n';
    }
    if (gotOK && gotResult) return true;
  }
  desynced = true;
  Serial.println("[STOP] Timeout/loi UART. Reset ESP32 va modem de thu lai.");
  return false;
}
// Binary transfers wait for '>' before sending; NEVER append a newline to data.
bool prompt(const String &cmd) {
  if (desynced) return false;
  Serial.println("> " + cmd);
  Modem.print(cmd); Modem.print('\r');
  uint32_t start = millis();
  String s;
  while (millis() - start < 15000) {
    if (!Modem.available()) { delay(1); continue; }
    char c = Modem.read();
    if (c == '>') { rxLine = ""; return true; }
    if (c == '\r') continue;
    if (c == '\n') {
      s.trim();
      if (s.length()) Serial.println(s);
      if (s == "ERROR" || s.startsWith("+CME ERROR:")) return false;
      if (s.startsWith("*ATREADY:") || s == "RDY") break;
      s = "";
    } else if (s.length() < 512) s += c;
    else break;
  }
  desynced = true;
  Serial.println("[STOP] Khong nhan prompt / modem reset. Reset ca hai board.");
  return false;
}

bool sendBytes(const uint8_t *data, size_t len) {
  while (len) {
    size_t n = len > 256 ? 256 : len;
    if (Modem.write(data, n) != n) { desynced = true; return false; }
    Modem.flush();
    data += n; len -= n;
    delay(50);  // SIMCom recommendation for CFTRANRX over UART.
  }
  return true;
}

bool transferDone() {
  uint32_t start = millis();
  while (millis() - start < 30000) {
    String s;
    if (!readLine(s)) { delay(1); continue; }
    Serial.println(s);
    if (s == "OK") return true;
    if (s == "ERROR" || s.startsWith("+CME ERROR:")) return false;
    if (s.startsWith("*ATREADY:") || s == "RDY") break;
  }
  desynced = true;
  Serial.println("[STOP] Truyen file mat dong bo; reset ESP va modem.");
  return false;
}

bool initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = 5; c.pin_d1 = 18; c.pin_d2 = 19; c.pin_d3 = 21;
  c.pin_d4 = 36; c.pin_d5 = 39; c.pin_d6 = 34; c.pin_d7 = 35;
  c.pin_xclk = 0; c.pin_pclk = 22; c.pin_vsync = 25; c.pin_href = 23;
  c.pin_sccb_sda = 26; c.pin_sccb_scl = 27;
  c.pin_pwdn = 32; c.pin_reset = -1;
  c.xclk_freq_hz = 20000000; c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = psramFound() ? FRAMESIZE_VGA : FRAMESIZE_QVGA;
  c.jpeg_quality = 15; c.fb_count = 1;
  c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[STOP] Camera init: 0x%x\n", err); return false;
  }
  delay(1000);
  // Discard startup frames so exposure has time to settle.
  for (int i = 0; i < 4; ++i) {
    camera_fb_t *f = esp_camera_fb_get();
    if (!f) return false;
    esp_camera_fb_return(f); delay(150);
  }
  return true;
}

bool initNetworkAndTLS() {
  String r;
  if (!command("AT", r) || !command("ATE0", r) || !command("AT+CMEE=2", r)) return false;
  if (!command("AT+CPIN?", r) || r.indexOf("+CPIN: READY") < 0) return false;
  if (!command("AT+CTZU=1", r)) return false;
  if (!command(String("AT+CGDCONT=1,\"IP\",\"") + APN + "\"", r)) return false;
  uint32_t start = millis(); bool registered = false;
  while (millis() - start < 120000) {
    if (!command("AT+CEREG?", r)) return false;
    int p = r.indexOf("+CEREG:"), mode = -1, state = -1;
    if (p >= 0 && sscanf(r.c_str()+p, "+CEREG: %d,%d", &mode, &state) == 2) {
      if (state == 1 || state == 5) { registered = true; break; }
      if (state == 3) return false;
    }
    delay(2000);
  }
  if (!registered) { Serial.println("[STOP] Chua dang ky LTE."); return false; }
  if (MODEM_CLOCK[0] && !command(String("AT+CCLK=\"") + MODEM_CLOCK + "\"", r)) return false;
  if (!command("AT+CCLK?", r)) return false;
  Serial.println("[TLS] CCLK phai la gio hien tai. Khong su dung CNTP.");
  if (!command("AT+CCERTLIST", r)) return false;
  if (r.indexOf(String("\"") + CA_FILE + "\"") < 0) {
    if (!prompt(String("AT+CCERTDOWN=\"") + CA_FILE + "\"," + String(strlen(ROOT_CA)))) return false;
    if (!sendBytes((const uint8_t *)ROOT_CA, strlen(ROOT_CA)) || !transferDone()) return false;
  }
  if (!command("AT+CSSLCFG=\"sslversion\",0,3", r) ||
      !command("AT+CSSLCFG=\"authmode\",0,1", r) ||
      !command("AT+CSSLCFG=\"ignorelocaltime\",0,0", r) ||
      !command(String("AT+CSSLCFG=\"cacert\",0,\"") + CA_FILE + "\"", r) ||
      !command("AT+CSSLCFG=\"enableSNI\",0,1", r)) return false;
  // HTTPINIT activates PDP itself, as in the successful HTTP GET test.
  command("AT+HTTPTERM", r, "", 120000); // ERROR is normal if no session exists.
  if (desynced || !command("AT+HTTPINIT", r, "", 120000)) return false;
  if (!command(String("AT+HTTPPARA=\"URL\",\"https://") + HOST + PATH + "\"", r) ||
      !command("AT+HTTPPARA=\"SSLCFG\",0", r)) return false;
  return true;
}

void runPhotoTest() {
  if (String(API_KEY) == "DIEN_DEVICE_API_KEY_CUA_BAN" || !API_KEY[0]) {
    Serial.println("[STOP] Dien API_KEY khop backend roi nap lai."); return;
  }
  for (size_t i = 0; i < strlen(API_KEY); ++i) {
    if ((uint8_t)API_KEY[i] < 33 || (uint8_t)API_KEY[i] > 126) {
      Serial.println("[STOP] API key phai la chuoi ASCII khong co xuong dong/khoang trang."); return;
    }
  }
  if (!initNetworkAndTLS()) return;
  // TEST HTTPS: dung tai day, chua chup hay gui anh.
String reply;
bool ok = command(
  "AT+HTTPACTION=0",
  reply,
  "+HTTPACTION:",
  180000
);

Serial.println("\n[HTTPS TEST]");
Serial.println(ok ? reply : "That bai / modem reset");
return;
  if (!initCamera()) return;
  camera_fb_t *f = esp_camera_fb_get();
  if (!f) { Serial.println("[STOP] Khong lay duoc anh."); return; }
  if (f->len < 4 || f->len > 150000 || f->buf[0] != 0xff || f->buf[1] != 0xd8 ||
      f->buf[f->len-2] != 0xff || f->buf[f->len-1] != 0xd9) {
    Serial.println("[STOP] JPEG hong hoac >150KB. Giam frame_size / tang jpeg_quality.");
    esp_camera_fb_return(f); return;
  }
  char id[64];
  uint64_t mac = ESP.getEfuseMac();
  // Hardware RNG supplies a fresh ID on every reset; no fixed IDs / 409 collisions.
  snprintf(id, sizeof(id), "cam0001-%04x%08lx-%08lx%08lx%08lx",
           (unsigned)(mac >> 32), (unsigned long)(mac & 0xffffffffULL),
           (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random());
  String header = String("POST ") + PATH + " HTTP/1.1\r\nHost: " + HOST +
    "\r\nContent-Type: image/jpeg\r\nX-API-Key: " + API_KEY +
    "\r\nX-Observation-Id: " + id + "\r\nX-Captured-At: " + CAPTURED_AT +
    "\r\nContent-Length: " + String(f->len) + "\r\nConnection: close\r\n\r\n";
  Serial.printf("[CAPTURE] %u bytes | %s\n", (unsigned)f->len, id);
  Serial.println(String("[TEST] captured-at mau: ") + CAPTURED_AT);
  // Full HTTP header + raw JPEG in a modem file: avoids USERDATA 256-byte limit
  // and firmware-dependent CR/LF escaping. No SD card is required.
  String r;
  if (!command("AT+FSCD=C:/", r)) { esp_camera_fb_return(f); return; }
  command("AT+FSDEL=cam_request.bin", r); // ERROR if absent is harmless.
  if (desynced || !prompt(String("AT+CFTRANRX=\"C:/cam_request.bin\",") + String(header.length()+f->len))) {
    esp_camera_fb_return(f); return;
  }
  bool written = sendBytes((const uint8_t *)header.c_str(), header.length()) && sendBytes(f->buf, f->len);
  esp_camera_fb_return(f);
  header = "";
  if (!written || !transferDone()) return;
  // path=1: C:/; method=1: POST; send_header=1: file is HTTP headers AND body.
  bool completed = command("AT+HTTPPOSTFILE=\"cam_request.bin\",1,1,1", r, "+HTTPPOSTFILE:", 180000);
  int method = -1, status = -1, bytes = -1;
  if (completed && sscanf(r.c_str(), "+HTTPPOSTFILE: %d,%d,%d", &method, &status, &bytes) == 3 && method == 1 && bytes >= 0) {
    Serial.printf("[RESULT] HTTP=%d, body=%d bytes\n", status, bytes);
    if (status == 200 || status == 202) Serial.println("[PASS] Server da chap nhan request. Kiem tra camera 0001 tren backend.");
    else Serial.println("[FAIL] Xem HTTP status va body ben duoi.");
  } else Serial.println("[FAIL] Khong nhan duoc ket qua POST hop le.");
  if (desynced) return; // Do not issue commands after ambiguous timeout/reset.
  String cleanup;
  command("AT+FSDEL=cam_request.bin", cleanup); // Remove image and API key from modem storage.
  if (desynced) return;
  if (bytes > 0 && status >= 100 && status <= 599) {
    Serial.println("[BODY] Toi da 1024 bytes. Khong go lenh AT trong luc doc.");
    Modem.print("AT+HTTPREAD=0,"); Modem.print(bytes > 1024 ? 1024 : bytes); Modem.print('\r');
    // loop() streams the entire response, including its binary-length framing.
    // No more AT commands follow, so the initial OK cannot terminate body reading.
  }
}

void setup() {
  Serial.begin(115200);
  Modem.setRxBufferSize(4096);
  Modem.begin(115200, SERIAL_8N1, 14, 13);
  delay(1500);
  Serial.println("\n=== ESP32-CAM A7670C: ONE JPEG POST ===");
  Serial.println("Cho modem 15 giay. Serial Monitor: 115200.");
  uint32_t start = millis();
  while (millis() - start < 15000) {
    while (Modem.available()) Serial.write(Modem.read());
    delay(1);
  }
  runPhotoTest();
  Serial.println("\n[INFO] Da ket thuc mot lan test. RST de chup/gia lap lan moi.");
}

void loop() {
  while (Modem.available()) Serial.write(Modem.read());
  delay(1);
}
