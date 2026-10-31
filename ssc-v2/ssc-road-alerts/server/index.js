import { createServer as createHttpsServer } from "node:https";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createApiServer } from "./app.js";
const port = Number(process.env.PORT || 8010);
const host = process.env.HOST || "127.0.0.1";
if (!Number.isInteger(port) || port < 1 || port > 65535)
  throw new Error("Invalid PORT");
const server = createApiServer({
  apiKey: process.env.ADMIN_API_KEY || "",
  deviceKey: process.env.DEVICE_API_KEY || process.env.ADMIN_API_KEY || "",
  aiKey: process.env.AI_API_KEY || process.env.ADMIN_API_KEY || "",
  enableTestApi: process.env.ENABLE_TEST_API !== "false",
});
server.on("error", (error) => {
  console.error(error.message);
  process.exitCode = 1;
});
server.listen(port, host, () =>
  console.log(`CleanSight API: http://${host}:${port}/api/health`),
);

// HTTPS server rieng, tu quan ly TLS (khong qua ngrok edge) — cho phep TLS/cipher
// cu de tuong thich voi modem GSM co stack TLS gioi han (vd SIMCom A76XX).
// Chi dung khi can thiet bi phan cung ket noi truc tiep qua tunnel TCP (vd `ngrok tcp`).
const certDir = fileURLToPath(new URL("./certs/", import.meta.url));
const keyPath = certDir + "key.pem";
const certPath = certDir + "cert.pem";
if (existsSync(keyPath) && existsSync(certPath)) {
  const httpsPort = Number(process.env.HTTPS_PORT || 8453);
  const requestListener = server.listeners("request")[0];
  const httpsServer = createHttpsServer(
    {
      key: readFileSync(keyPath),
      cert: readFileSync(certPath),
      minVersion: "TLSv1", // Chap nhan ca TLS 1.0/1.1 cho stack TLS cu tren modem.
      ciphers:
        "DEFAULT:@SECLEVEL=0:ALL", // Mo rong toi da danh sach cipher (chi dung cho thiet bi test, khong dung production that).
      honorCipherOrder: true,
    },
    requestListener,
  );
  httpsServer.on("error", (error) => console.error("HTTPS:", error.message));
  httpsServer.listen(httpsPort, host, () =>
    console.log(`CleanSight API (self-managed HTTPS, for the modem): https://${host}:${httpsPort}/api/health`),
  );
  for (const signal of ["SIGINT", "SIGTERM"])
    process.on(signal, () => httpsServer.close());
}

for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => server.close(() => process.exit(0)));
