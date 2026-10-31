/*
 CHI KIEM TRA PSRAM — khong camera, khong WiFi, khong modem.

 Muc dich: tach rieng van de PSRAM ra khoi camera, de biet chac la do
 cai dat Tools/board, hay do chinh chip/board khong co PSRAM that.

 Nap sketch nay, mo Serial Monitor (115200 baud), doc ket qua.
*/
void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n===== KIEM TRA PSRAM =====");

  Serial.printf("Chip model     : %s\n", ESP.getChipModel());
  Serial.printf("Chip revision  : %d\n", ESP.getChipRevision());
  Serial.printf("So nhan (cores): %d\n", ESP.getChipCores());
  Serial.printf("Flash size     : %u MB\n", (unsigned)(ESP.getFlashChipSize() / (1024 * 1024)));

  bool found = psramFound();
  Serial.printf("psramFound()   : %s\n", found ? "TRUE" : "FALSE");

  if (found) {
    Serial.printf("PSRAM tong     : %u KB\n", (unsigned)(ESP.getPsramSize() / 1024));
    Serial.printf("PSRAM con trong: %u KB\n", (unsigned)(ESP.getFreePsram() / 1024));
    Serial.println("[OK] PSRAM hoat dong binh thuong. Loi 'khong tim thay PSRAM' trong sketch");
    Serial.println("     camera KHONG phai do phan cung/cau hinh PSRAM nua — kiem tra lai");
    Serial.println("     phan code camera o cho khac.");
  } else {
    Serial.println("[LOI] Khong tim thay PSRAM that su. Kiem tra theo thu tu sau:");
    Serial.println("  1. Tools > PSRAM co dang chon \"OPI PSRAM\" khong (chup man hinh lai de chac chan).");
    Serial.println("  2. Tools > Board co dung la \"ESP32S3 Dev Module\" khong (chon nham board/chip");
    Serial.println("     khac se lam PSRAM khong duoc kich hoat dung, du chon dung dong PSRAM).");
    Serial.println("  3. Boards Manager (Tools > Board > Boards Manager, go \"esp32\") — ban \"esp32\" cua");
    Serial.println("     Espressif co phai la ban cu khong. Ban cu co the chua ho tro dung chip");
    Serial.println("     ESP32-S3R8 (PSRAM Octal nhung trong chip). Cap nhat len ban moi nhat roi thu lai.");
    Serial.println("  4. Neu ca 3 dieu tren deu dung roi ma van FALSE: co kha nang day la chip/board");
    Serial.println("     gia/nhai khong co PSRAM that du ghi N16R8 ben ngoai — can doi board that.");
  }
}

void loop() {
  delay(5000);
}
