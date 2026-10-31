/*
 ESP32-CAM Ai-Thinker + A7670C, Arduino-ESP32 3.x.
 Open this sketch with protocol.h and root_ca.h in the SAME folder.
 Edit DEVICE_API_KEY and APN below. No Wi-Fi / TinyGSM required.
 RX GPIO14 <- modem TX; TX GPIO13 -> modem RX; common GND.
 UART voltage must match the board (bare A7670 UART = 1.8V).
 No microSD; power modem separately according to its board specifications.
 Power on modem manually if the board requires PWRKEY.
 Uses documented A76XX CCH TLS commands, not SIM800 HTTPSSL commands.
 Pending frame is kept in RAM only: reset/power loss discards it.
*/
#include <Arduino.h>
#include "esp_camera.h"
#include <Preferences.h>
#include "protocol.h"
#include "root_ca.h"

// ===== CHANGE THESE TWO VALUES =====
const char DEVICE_API_KEY[] = "123";
const char APN[] = "m-wap"; // Use the APN supplied by your SIM operator.
// This sketch assumes an APN that does not require username/password.
const char HOST[] = "worrier-zoom-laboring.ngrok-free.dev";
constexpr uint32_t CAPTURE_INTERVAL_MS = 60000;
constexpr int MODEM_RX = 14, MODEM_TX = 13;
constexpr uint32_t MODEM_BAUD = 115200;
constexpr size_t MAX_IMAGE_BYTES = 5u * 1024 * 1024;

HardwareSerial Modem(2);
Preferences prefs;
String lineBuffer;
bool fatalError = false;
bool ready = false;
camera_fb_t *pending = nullptr;
std::string observationId, capturedAt;
uint32_t nextCapture = 0;
uint32_t retryDelay = 5000;

void failStop(const char *reason) {
  Serial.printf("\n[STOP] %s\n", reason);
  Serial.println("Sua loi roi reset ESP32 va modem. Khong tiep tuc gui AT khi UART mat dong bo.");
  fatalError = true;
}

bool isError(const String &s) {
  return s == "ERROR" || s.startsWith("+CME ERROR:") || s.startsWith("+CMS ERROR:");
}

// Persistent line buffer: handles UART lines split across multiple reads.
bool nextLine(String &out, bool prompt = false) {
  while (Modem.available()) {
    char c = (char)Modem.read();
    if (prompt && c == '>' && lineBuffer.length() == 0) {
      out = ">";
      return true;
    }
    if (c == '\r') continue;
    if (c == '\n') {
      out = lineBuffer;
      lineBuffer = "";
      out.trim();
      if (out.length()) return true;
    } else if (lineBuffer.length() < 1024) {
      lineBuffer += c;
    } else {
      failStop("Dong phan hoi modem qua dai.");
      return false;
    }
  }
  return false;
}

// For asynchronous commands, require BOTH OK and the result URC, in either order.
bool waitReply(const char *prefix, uint32_t timeoutMs, String &matched,
               String &all, bool prompt = false) {
  bool gotOK = false, gotResult = !prefix[0];
  uint32_t start = millis();
  matched = ""; all = "";
  while (!fatalError && millis() - start < timeoutMs) {
    String s;
    if (!nextLine(s, prompt)) { delay(1); continue; }
    if (prompt && s == ">") return true;
    Serial.println(s);
    if (all.length() + s.length() < 4096) all += s + '\n';
    if (isError(s)) return false;
    if (s == "OK") gotOK = true;
    if (prefix[0] && s.startsWith(prefix)) { matched = s; gotResult = true; }
    if (!prompt && gotOK && gotResult) return true;
  }
  failStop("Timeout modem; reset de tranh nham phan hoi cu voi lenh moi.");
  return false;
}

bool command(const String &cmd, String &reply, const char *prefix = "",
             uint32_t timeoutMs = 10000) {
  if (fatalError) return false;
  Serial.println("> " + cmd); // Never pass an API key or raw HTTP headers here.
  Modem.print(cmd); Modem.print('\r');
  String matched, all;
  bool ok = waitReply(prefix, timeoutMs, matched, all);
  reply = prefix[0] ? matched : all;
  return ok;
}

bool at(const String &cmd, uint32_t timeoutMs = 10000) {
  String reply;
  return command(cmd, reply, "", timeoutMs);
}

bool asyncZero(const String &cmd, const char *prefix, bool session,
               uint32_t timeoutMs = 120000) {
  String r;
  if (!command(cmd, r, prefix, timeoutMs)) return false;
  String tail = r.substring(strlen(prefix));
  int id = -1, result = -1;
  if (session) {
    return sscanf(tail.c_str(), " %d,%d", &id, &result) == 2 && id == 0 && result == 0;
  }
  return sscanf(tail.c_str(), " %d", &result) == 1 && result == 0;
}

bool startBinary(const String &cmd) {
  if (fatalError) return false;
  Serial.println("> " + cmd);
  Modem.print(cmd); Modem.print('\r');
  String r, all;
  return waitReply("", 10000, r, all, true);
}

bool writeBytes(const uint8_t *data, size_t length) {
  size_t written = 0;
  uint32_t start = millis();
  while (written < length && millis() - start < 15000) {
    size_t n = length - written;
    if (n > 256) n = 256;
    written += Modem.write(data + written, n);
    delay(1);
  }
  Modem.flush();
  if (written != length) {
    failStop("Chua gui du bytes; modem co the van dang cho du lieu nhi phan.");
    return false;
  }
  return true;
}

bool sendTLS(const uint8_t *data, size_t length) {
  size_t offset = 0;
  while (offset < length && !fatalError) {
    size_t n = length - offset;
    if (n > 1024) n = 1024; // A76XX supports up to 2048 per CCHSEND.
    if (!startBinary("AT+CCHSEND=0," + String((unsigned)n))) return false;
    if (!writeBytes(data + offset, n)) return false;
    String r, all;
    if (!waitReply("+CCHSEND:", 160000, r, all)) return false;
    int session = -1, error = -1;
    if (sscanf(r.c_str(), "+CCHSEND: %d,%d", &session, &error) != 2 ||
        session != 0 || error != 0) return false;
    offset += n;
  }
  return offset == length;
}

bool installCA() {
  String list;
  if (!command("AT+CCERTLIST", list)) return false;
  if (list.indexOf(CA_FILE) >= 0) return true;
  if (!startBinary(String("AT+CCERTDOWN=\"") + CA_FILE + "\"," + String(strlen(ROOT_CA)))) return false;
  if (!writeBytes((const uint8_t *)ROOT_CA, strlen(ROOT_CA))) return false;
  String r, all;
  return waitReply("", 15000, r, all);
}

bool syncClock() {
  // No hardcoded date and no Wi-Fi time. NTP is performed by the cellular modem.
  const char *servers[] = {"time.cloudflare.com", "pool.ntp.org"};
  for (const char *server : servers) {
    if (!at(String("AT+CNTP=\"") + server + "\",0")) return false;
    if (asyncZero("AT+CNTP", "+CNTP:", false, 125000)) return true;
    if (fatalError) return false;
  }
  Serial.println("[TIME] NTP khong thanh cong. Chua chup/gui anh.");
  return false;
}

// Lan dau bat tay AT: modem co the con dang tu in *ATREADY/+CPIN sau khi vua bat nguon,
// day la binh thuong (khac voi ATREADY xuat hien GIUA luc dang chay, do la dau hieu reset that).
bool firstHandshake() {
  for (int attempt = 0; attempt < 8; ++attempt) {
    fatalError = false;
    if (at("AT", 10000)) return true;
    Serial.println("(Modem con dang tu khoi dong, thu lai AT sau 2s...)");
    delay(2000);
  }
  return false;
}

bool initModem() {
  // Boot wait: modem must already be powered on; no guessed PWRKEY wiring.
  delay(5000);
  if (!firstHandshake() || !at("ATE0") || !at("AT+CMEE=2")) return false;
  at("ATI");
  at("AT+CGMR");
  if (fatalError) return false;
  String r;
  if (!command("AT+CPIN?", r, "", 10000) || r.indexOf("+CPIN: READY") < 0) {
    Serial.println("[SIM] SIM chua READY; kiem tra SIM/PIN."); return false;
  }
  if (!at("AT+CFUN=1", 30000) || !at("AT+CTZU=1")) return false;
  // Clear an old session, e.g. after ESP32-only reset. ERROR when not open is normal.
  asyncZero("AT+CCHSTOP", "+CCHSTOP:", false);
  if (fatalError) return false;
  asyncZero("AT+NETCLOSE", "+NETCLOSE:", false);
  if (fatalError) return false;
  if (!at(String("AT+CGDCONT=1,\"IP\",\"") + APN + "\"")) return false;
  uint32_t start = millis(); bool registered = false;
  while (millis() - start < 120000 && !fatalError) {
    if (!command("AT+CEREG?", r)) return false;
    int pos = r.indexOf("+CEREG:");
    int mode = -1, status = -1;
    if (pos >= 0 && sscanf(r.c_str() + pos, "+CEREG: %d,%d", &mode, &status) == 2) {
      if (status == 1 || status == 5) { registered = true; break; }
      if (status == 3) { Serial.println("[SIM] Mang tu choi dang ky."); return false; }
    }
    delay(2000);
  }
  if (!registered) return false;
  if (!at("AT+CSOCKSETPN=1") || !asyncZero("AT+NETOPEN", "+NETOPEN:", false)) return false;
  if (!syncClock() || !installCA()) return false;
  if (!at("AT+CSSLCFG=\"sslversion\",0,3") ||
      !at("AT+CSSLCFG=\"authmode\",0,1") ||
      !at("AT+CSSLCFG=\"ignorelocaltime\",0,0") ||
      !at(String("AT+CSSLCFG=\"cacert\",0,\"") + CA_FILE + "\"") ||
      !at("AT+CSSLCFG=\"enableSNI\",0,1") ||
      !at("AT+CCHMODE=0") || !at("AT+CCHSET=1,1") ||
      !asyncZero("AT+CCHSTART", "+CCHSTART:", false)) return false;
  Serial.println("[MODEM] Mang, gio va TLS da cau hinh.");
  return true;
}

bool initCamera() {
  if (!psramFound()) { failStop("Khong tim thay PSRAM. Chon AI Thinker ESP32-CAM."); return false; }
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = 5; c.pin_d1 = 18; c.pin_d2 = 19; c.pin_d3 = 21;
  c.pin_d4 = 36; c.pin_d5 = 39; c.pin_d6 = 34; c.pin_d7 = 35;
  c.pin_xclk = 0; c.pin_pclk = 22; c.pin_vsync = 25; c.pin_href = 23;
  c.pin_sccb_sda = 26; c.pin_sccb_scl = 27;
  c.pin_pwdn = 32; c.pin_reset = -1;
  c.xclk_freq_hz = 20000000; c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA; c.jpeg_quality = 12;
  c.fb_count = 1; c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) { Serial.printf("Camera error: 0x%x\n", err); return false; }
  delay(1000);
  return true;
}

bool captureImage() {
  if (!syncClock()) return false;
  // Flush old queued frames, and let exposure settle before capturing.
  for (int i = 0; i < 2; ++i) {
    camera_fb_t *old = esp_camera_fb_get();
    if (!old) return false;
    esp_camera_fb_return(old); delay(100);
  }
  String r;
  if (!command("AT+CCLK?", r, "+CCLK:")) return false;
  capturedAt = CaptureProtocol::clockToISO(r.c_str());
  if (capturedAt.empty()) { Serial.println("[TIME] CCLK khong hop le."); return false; }
  // Counter survives restart; persist BEFORE taking a new observation.
  uint64_t sequence = prefs.getULong64("seq", 0) + 1;
  if (sequence == 0 || prefs.putULong64("seq", sequence) != sizeof(sequence)) {
    failStop("Khong luu duoc observation counter vao NVS."); return false;
  }
  char id[81];
  snprintf(id, sizeof(id), "cam0001-%012llx-%llu",
           (unsigned long long)ESP.getEfuseMac(), (unsigned long long)sequence);
  observationId = id;
  // Including capture time also reduces collision risk after a full NVS erase.
  observationId += "-";
  for (char c : capturedAt) if (c >= '0' && c <= '9') observationId += c;
  if (!CaptureProtocol::validId(observationId)) { failStop("Observation ID khong hop le."); return false; }
  pending = esp_camera_fb_get();
  if (!pending) return false;
  if (!CaptureProtocol::jpegOK(pending->buf, pending->len) || pending->len > MAX_IMAGE_BYTES) {
    Serial.println("[CAMERA] JPEG khong hop le/qua lon.");
    esp_camera_fb_return(pending); pending = nullptr; return false;
  }
  Serial.printf("[CAPTURE] %u bytes | %s | %s\n", (unsigned)pending->len,
                observationId.c_str(), capturedAt.c_str());
  return true;
}

bool readBinary(size_t count, std::string &out) {
  uint32_t start = millis();
  while (count && millis() - start < 10000) {
    if (!Modem.available()) { delay(1); continue; }
    char c = (char)Modem.read();
    if (out.size() < 8192) out.push_back(c);
    --count;
  }
  if (count) { failStop("Thieu bytes phan hoi CCHRECV."); return false; }
  return true;
}

// Consume length-framed modem bytes, including embedded CR/LF, before parsing HTTP.
int readHTTPStatus() {
  std::string response;
  uint32_t start = millis();
  while (!fatalError && millis() - start < 90000) {
    String r;
    if (!command("AT+CCHRECV?", r, "+CCHRECV: LEN,")) return -1;
    int available = 0, other = 0;
    if (sscanf(r.c_str(), "+CCHRECV: LEN,%d,%d", &available, &other) != 2) return -1;
    if (available <= 0) { delay(500); continue; }
    int want = available > 2048 ? 2048 : available;
    Modem.print("AT+CCHRECV=0,"); Modem.print(want); Modem.print('\r');
    bool finished = false;
    uint32_t readStart = millis();
    while (!finished && !fatalError && millis() - readStart < 15000) {
      String line;
      if (!nextLine(line)) { delay(1); continue; }
      if (isError(line)) return -1;
      int session = -1, count = -1;
      if (sscanf(line.c_str(), "+CCHRECV: DATA,%d,%d", &session, &count) == 2) {
        if (session != 0 || count < 0 || count > 2048) {
          failStop("CCHRECV DATA sai dinh dang."); return -1;
        }
        if (!readBinary((size_t)count, response)) return -1;
      } else if (sscanf(line.c_str(), "+CCHRECV: %d,%d", &session, &count) == 2) {
        if (session != 0 || count != 0) return -1;
        finished = true;
      }
    }
    if (!finished) { failStop("CCHRECV thieu ket qua cuoi."); return -1; }
    // Ignore interim 1xx headers, if present.
    for (;;) {
      size_t end = response.find("\r\n\r\n");
      if (end == std::string::npos) break;
      int code = CaptureProtocol::statusCode(response);
      if (code >= 100 && code < 200) { response.erase(0, end + 4); continue; }
      std::string lower = response.substr(0, end);
      for (char &c : lower) if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
      if ((code == 200 || code == 202) && lower.find("text/html") != std::string::npos) {
        Serial.println("[HTTP] Nhan HTML thay vi API; kiem tra ngrok/server."); return -1;
      }
      Serial.printf("[HTTP] status=%d\n", code);
      if (response.size() > end + 4) {
        std::string preview = response.substr(end + 4, 512);
        Serial.println(preview.c_str());
      }
      return code;
    }
    if (response.size() >= 8192) { Serial.println("[HTTP] Header qua lon."); return -1; }
  }
  Serial.println("[HTTP] Chua nhan status; lan thu lai giu nguyen anh va ID.");
  return -1;
}

int uploadPending() {
  if (!at("AT+CCHSSLCFG=0,0")) return -1;
  if (!asyncZero(String("AT+CCHOPEN=0,\"") + HOST + "\",443,2", "+CCHOPEN:", true)) return -1;
  std::string headers = CaptureProtocol::makeHeaders(DEVICE_API_KEY, observationId, capturedAt, pending->len);
  int status = -1;
  if (!headers.empty() && sendTLS((const uint8_t *)headers.data(), headers.size()) &&
      sendTLS(pending->buf, pending->len)) status = readHTTPStatus();
  // Never append CR/LF, NUL, base64 or multipart delimiters after the JPEG.
  if (!fatalError) asyncZero("AT+CCHCLOSE=0", "+CCHCLOSE:", true);
  return status;
}

void setup() {
  Serial.begin(115200); delay(1500);
  Serial.println("\nESP32CAM -> A7670C -> camera 0001");
  if (String(DEVICE_API_KEY) == "PASTE_DEVICE_API_KEY_HERE" || String(APN) == "YOUR_SIM_APN") {
    failStop("Dien DEVICE_API_KEY va APN o dau file truoc khi nap."); return;
  }
  if (!CaptureProtocol::safeValue(DEVICE_API_KEY) || !CaptureProtocol::safeValue(APN) ||
      String(APN).indexOf('"') >= 0 || String(APN).indexOf('\\') >= 0) {
    failStop("API key/APN co ky tu khong hop le."); return;
  }
  if (!prefs.begin("capture0001", false)) { failStop("Khong mo duoc NVS."); return; }
  if (!initCamera()) { failStop("Khoi tao camera that bai."); return; }
  Modem.setRxBufferSize(8192);
  Modem.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX, MODEM_TX);
}

void loop() {
  if (fatalError) { delay(1000); return; }
  if (!ready) {
    ready = initModem();
    if (!ready) { Serial.println("[RETRY] Khoi tao modem lai sau 15s."); delay(15000); return; }
  }
  if (!pending) {
    if ((int32_t)(millis() - nextCapture) < 0) { delay(50); return; }
    if (!captureImage()) { ready = false; delay(5000); return; }
  }
  int status = uploadPending();
  if (status == 200 || status == 202) {
    Serial.println(status == 202 ? "[OK] Anh da vao hang doi AI." : "[OK] Server da nhan observation nay.");
    esp_camera_fb_return(pending); pending = nullptr;
    retryDelay = 5000;
    nextCapture = millis() + CAPTURE_INTERVAL_MS;
  } else if (CaptureProtocol::retryable(status)) {
    Serial.printf("[RETRY] Giu nguyen JPEG, ID va captured-at; thu lai sau %lu ms.\n", (unsigned long)retryDelay);
    ready = false;
    delay(retryDelay);
    retryDelay = retryDelay < 30000 ? retryDelay * 2 : 60000;
  } else {
    // 401/403: key; 404: camera/route; 409: conflict; 413/415: body/type;
    // 400/422: validation. Never silently generate another ID for the same photo.
    failStop("HTTP khong the tu sua. Xem status/body, sua cau hinh/backend roi reset.");
  }
}
