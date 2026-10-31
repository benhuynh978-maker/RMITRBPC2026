#pragma once
#include <string>
#include <cstdio>
#include <cstddef>

namespace CaptureProtocol {
inline bool safeValue(const std::string &s) {
  if (s.empty() || s.size() > 512) return false;
  for (unsigned char c : s) if (c < 33 || c > 126) return false;
  return true;
}
inline bool validId(const std::string &s) {
  if (s.empty() || s.size() > 80) return false;
  for (char c : s) if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
      (c >= '0' && c <= '9') || c == '_' || c == '-')) return false;
  return true;
}
// CCLK timezone unit = 15 minutes, NOT hours. Keep the explicit ISO offset.
inline std::string clockToISO(const std::string &s) {
  int y, m, d, h, mi, se, tz, used = 0; char sign;
  if (std::sscanf(s.c_str(), "+CCLK: \"%d/%d/%d,%d:%d:%d%c%d\"%n",
      &y, &m, &d, &h, &mi, &se, &sign, &tz, &used) != 8 ||
      used != (int)s.size()) return {};
  if (y < 26 || y > 99 || m < 1 || m > 12 || h < 0 || h > 23 ||
      mi < 0 || mi > 59 || se < 0 || se > 59 || tz < 0 || tz > 56 ||
      (sign != '+' && sign != '-')) return {};
  const int year = 2000 + y;
  const int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  int maxDay = days[m-1];
  if (m == 2 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)) ++maxDay;
  if (d < 1 || d > maxDay) return {};
  char out[96];
  std::snprintf(out, sizeof(out), "%04d-%02d-%02dT%02d:%02d:%02d%c%02d:%02d",
                year, m, d, h, mi, se, sign, tz / 4, (tz % 4) * 15);
  return out;
}
inline bool jpegOK(const unsigned char *p, size_t n) {
  return p && n >= 4 && n <= 5u * 1024 * 1024 &&
         p[0] == 0xff && p[1] == 0xd8 && p[n-2] == 0xff && p[n-1] == 0xd9;
}
inline std::string makeHeaders(const std::string &key, const std::string &id,
                               const std::string &capturedAt, size_t size) {
  if (!safeValue(key) || !validId(id) || !safeValue(capturedAt) ||
      size < 4 || size > 5u * 1024 * 1024) return {};
  return "POST /api/esp32/cameras/cam0001/capture HTTP/1.1\r\n"
         "Host: laptop-p8gad5f2.tailc4a76e.ts.net\r\n"
         "Content-Type: image/jpeg\r\n"
         "Content-Length: " + std::to_string(size) + "\r\n"
         "X-API-Key: " + key + "\r\n"
         "X-Observation-Id: " + id + "\r\n"
         "X-Captured-At: " + capturedAt + "\r\n"
         "User-Agent: ESP32CAM-A7670C/1.0\r\n"
         "Accept: application/json\r\n"
         "Connection: close\r\n\r\n";
}
inline int statusCode(const std::string &headers) {
  int code = 0;
  if (headers.find("\r\n\r\n") == std::string::npos) return -1;
  if (std::sscanf(headers.c_str(), "HTTP/1.1 %d", &code) != 1 &&
      std::sscanf(headers.c_str(), "HTTP/1.0 %d", &code) != 1) return -1;
  return code >= 100 && code <= 599 ? code : -1;
}
inline bool retryable(int code) {
  return code < 0 || code == 408 || code == 425 || code == 429 || code >= 500;
}
} // namespace CaptureProtocol
