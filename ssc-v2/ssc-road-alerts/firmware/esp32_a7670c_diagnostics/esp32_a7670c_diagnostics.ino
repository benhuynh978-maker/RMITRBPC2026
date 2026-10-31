/*
  ESP32-CAM (AI-Thinker) + SIMCom A7670C — Chan doan ket noi
  ------------------------------------------------------------
  Muc dich: kiem tra tung buoc mot (modem AT, SIM, tin hieu, dang ky mang,
  APN, gio mang, va goi HTTPS thu toi backend) TRUOC khi thu chup anh.
  Sketch nay KHONG dung camera — de co lap loi phan cung/mang rieng voi loi camera.

  Thu vien can cai (Arduino IDE > Tools > Manage Libraries):
    - "TinyGSM" by Volodymyr Shymanskyy

  Board: Tools > Board > ESP32 Arduino > "AI Thinker ESP32-CAM"
  Can bo nap FTDI/USB-TTL rieng (ESP32-CAM khong co cong USB tren board):
    - Noi FTDI TX -> ESP32 U0R (GPIO3), FTDI RX -> ESP32 U0T (GPIO1)
    - Noi GPIO0 xuong GND CHI khi nap code, thao ra va nhan RESET de chay binh thuong.

  Mo Serial Monitor toc do 115200 baud sau khi nap de xem ket qua.
*/

#define TINY_GSM_MODEM_SIM7600   // A7670C dung chung tap lenh AT voi ho SIM7600 trong TinyGSM
#include <TinyGsmClient.h>

// ==================== CHINH THEO PHAN CUNG THAT CUA BAN ====================
#define MODEM_RX_PIN 14   // ESP32 GPIO nhan  <- chan TX cua A7670C
#define MODEM_TX_PIN 15   // ESP32 GPIO gui   -> chan RX cua A7670C
#define MODEM_BAUD   115200

const char apn[]      = "v-internet";  // APN nha mang cua SIM ban dang dung — hoi tong dai neu khong chac
const char gprsUser[] = "";
const char gprsPass[] = "";

const char server[]     = "worrier-zoom-laboring.ngrok-free.dev"; // domain ngrok hien tai
const int  port         = 443;
const char healthPath[] = "/api/health";
// ============================================================================

HardwareSerial SerialAT(2);
TinyGsm modem(SerialAT);
TinyGsmClientSecure client(modem);

void logStep(const char* step, bool ok, const String& detail = "") {
  Serial.print(ok ? "[OK]   " : "[LOI]  ");
  Serial.print(step);
  if (detail.length()) { Serial.print(" - "); Serial.print(detail); }
  Serial.println();
}

void haltWithHint(const char* hint) {
  Serial.print("=> ");
  Serial.println(hint);
  Serial.println("Dung lai. Sua xong hay nhan nut RESET tren board de chay lai tu dau.");
  while (true) delay(1000);
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println();
  Serial.println("===== CHAN DOAN A7670C =====");

  SerialAT.begin(MODEM_BAUD, SERIAL_8N1, MODEM_RX_PIN, MODEM_TX_PIN);
  delay(3000); // cho module A7670C khoi dong xong (den trang thai thuong nhap nhay ~1s/lan)

  Serial.println("Buoc 1/8: Bat tay AT voi modem...");
  bool modemOk = modem.testAT(10000);
  logStep("Modem phan hoi AT", modemOk);
  if (!modemOk) haltWithHint(
    "Kiem tra: nguon rieng cho A7670C co du dong khong (toi thieu 2A xung), "
    "day RX/TX co bi noi cheo (TX-TX thay vi TX-RX) khong, muc logic co dung 3.3V/mismatch khong.");

  Serial.println("Buoc 2/8: Khoi tao lai modem...");
  modem.restart();
  Serial.print("Thong tin modem: ");
  Serial.println(modem.getModemInfo());

  Serial.println("Buoc 3/8: Kiem tra trang thai SIM...");
  SimStatus simStatus = modem.getSimStatus();
  logStep("SIM san sang", simStatus == SIM_READY, "ma trang thai=" + String((int)simStatus));
  if (simStatus != SIM_READY) haltWithHint(
    "Kiem tra: SIM da lap dung khe/dung chieu chua, SIM co dang bi khoa ma PIN khong, SIM con han su dung khong.");

  Serial.println("Buoc 4/8: Doc cuong do tin hieu...");
  int csq = modem.getSignalQuality();
  logStep("Tin hieu (CSQ)", csq > 0 && csq < 99, String(csq) + " (thang 0-31, cao hon la tot hon; 99 = chua xac dinh duoc)");

  Serial.println("Buoc 5/8: Cho dang ky mang (toi da 60s)...");
  bool netOk = modem.waitForNetwork(60000L);
  logStep("Dang ky mang thanh cong", netOk);
  if (!netOk) haltWithHint(
    "Kiem tra: vi tri dat thiet bi co song di dong khong, anten da gan chac chua, "
    "SIM co dang hoat dong/con han goi cuoc khong.");

  Serial.println("Buoc 6/8: Ket noi du lieu qua APN...");
  bool gprsOk = modem.gprsConnect(apn, gprsUser, gprsPass);
  logStep("Ket noi APN", gprsOk, String("apn=") + apn);
  if (!gprsOk) haltWithHint(
    "Kiem tra: ten APN da dung chua (goi tong dai nha mang de xac nhan), "
    "SIM co duoc kich hoat goi du lieu (data) khong.");

  Serial.print("Dia chi IP duoc cap: ");
  Serial.println(modem.getLocalIP());

  Serial.println("Buoc 7/8: Lay gio tu mang (NITZ)...");
  int year, month, day, hour, minute, second;
  float timezone;
  bool timeOk = modem.getNetworkTime(&year, &month, &day, &hour, &minute, &second, &timezone);
  if (timeOk) {
    char buf[40];
    snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d (UTC%+.1f)", year, month, day, hour, minute, second, timezone);
    logStep("Lay gio mang", true, buf);
  } else {
    logStep("Lay gio mang", false);
    Serial.println("=> Canh bao: sketch chup anh CAN gio dung de gui captured_at, "
                    "neu buoc nay that bai tren thiet bi that thi bao lai truoc khi chup anh.");
  }

  Serial.println("Buoc 8/8: Goi thu GET /api/health qua HTTPS...");
  bool connectOk = client.connect(server, port);
  logStep("Ket noi TLS toi server", connectOk, String(server) + ":" + String(port));
  if (connectOk) {
    client.print(String("GET ") + healthPath + " HTTP/1.1\r\n");
    client.print(String("Host: ") + server + "\r\n");
    client.print("ngrok-skip-browser-warning: true\r\n");
    client.print("Connection: close\r\n\r\n");

    unsigned long timeoutStart = millis();
    Serial.println("--- Phan hoi tho tu server ---");
    while (client.connected() && millis() - timeoutStart < 10000) {
      while (client.available()) {
        Serial.write(client.read());
        timeoutStart = millis();
      }
    }
    client.stop();
    Serial.println("\n--- Het phan hoi ---");
    Serial.println("=> Neu thay dong JSON {\"status\":\"ok\",...} o tren: TOAN BO DUONG TRUYEN DA THONG.");
  } else {
    Serial.println("=> Kiem tra: server co dung dang chay va ngrok tunnel co dang mo khong, "
                    "APN co cho phep truy cap Internet cong khai (khong bi chan port 443) khong.");
  }

  Serial.println("===== KET THUC CHAN DOAN =====");
}

void loop() {
  // Khong lam gi them; toan bo ket qua da in ra Serial Monitor trong setup().
}
