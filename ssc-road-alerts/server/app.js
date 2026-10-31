import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { createService } from "./service.js";
import { ApiError, requireValue } from "./errors.js";
import { body, jsonBody } from "./input.js";
import { POLICY } from "./config.js";
import { createWeatherService } from "./weather.js";

const defaultDataDir = fileURLToPath(new URL("./data/", import.meta.url));
export function createApiServer({
  dataDir = defaultDataDir,
  apiKey = "",
  deviceKey = apiKey,
  aiKey = apiKey,
  enableTestApi = true,
  clock = Date.now,
  weatherFetch = fetch,
} = {}) {
  const service = createService(dataDir, clock);
  const weather = createWeatherService({ fetchImpl: weatherFetch, clock });
  const mediaDir = join(dataDir, "images");
  function authorize(req, role = "admin") {
    const expected =
      role === "device" ? deviceKey : role === "ai" ? aiKey : apiKey;
    if (expected) {
      const received = String(req.headers["x-api-key"] ?? "");
      const left = Buffer.from(received);
      const right = Buffer.from(expected);
      requireValue(
        left.length === right.length && timingSafeEqual(left, right),
        "X-API-Key không hợp lệ",
        401,
      );
    } else {
      requireValue(
        ["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(
          req.socket.remoteAddress,
        ),
        "Cần cấu hình API key để nhận dữ liệu từ thiết bị qua LAN",
        401,
      );
      const host = String(req.headers.host ?? "");
      requireValue(
        /^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/i.test(host),
        "Host không hợp lệ cho chế độ demo không khóa",
        403,
      );
    }
  }
  const server = createServer(async (req, res) => {
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Origin", req.headers.origin ?? "*");
    const send = (code, data) => {
      res.writeHead(code);
      res.end(JSON.stringify(data));
    };
    try {
      const url = new URL(req.url ?? "/", "http://localhost");
      const path = url.pathname.replace(/\/$/, "");
      const method = req.method;
      if (method === "OPTIONS") {
        res.setHeader(
          "Access-Control-Allow-Methods",
          "GET, POST, PATCH, PUT, DELETE, OPTIONS",
        );
        res.setHeader(
          "Access-Control-Allow-Headers",
          req.headers["access-control-request-headers"] ||
            "Accept, Content-Type, X-API-Key, X-Observation-Id, X-Captured-At",
        );
        res.writeHead(204);
        res.end();
        return;
      }
      if (path === "/api/health" && method === "GET") {
        send(200, {
          status: "ok",
          version: 2,
          storage: "json",
          test_api: enableTestApi,
        });
        return;
      }
      if (path === "/api/policy" && method === "GET") {
        send(200, {
          ...POLICY,
          assessment: "heuristic-calibrated",
          aggregation: "mean-of-fresh-camera-readings",
        });
        return;
      }
      if (path === "/api/weather/cameras" && method === "GET") {
        send(200, await weather.camerasForecast(await service.list("cameras")));
        return;
      }
      if (path === "/api/ai/reports" && method === "POST") {
        authorize(req, "ai");
        send(200, await service.aiReport(await jsonBody(req)));
        return;
      }
      const image = path.match(/^\/api\/images\/([a-f0-9-]{36}\.jpg)$/);
      if (image && method === "GET") {
        let bytes;
        try {
          bytes = await readFile(join(mediaDir, image[1]));
        } catch (error) {
          if (error.code === "ENOENT")
            throw new ApiError(404, "Ảnh không tồn tại");
          throw error;
        }
        res.setHeader("Content-Type", "image/jpeg");
        res.setHeader("Content-Length", bytes.length);
        res.writeHead(200);
        res.end(bytes);
        return;
      }
      const collection = path.match(
        /^\/api\/(cameras|road-alerts)(?:\/([^/]+))?$/,
      );
      if (collection) {
        const kind = collection[1] === "cameras" ? "cameras" : "roads";
        const key = kind === "cameras" ? "camera_id" : "road_id";
        const entityId = collection[2]
          ? decodeURIComponent(collection[2])
          : undefined;
        if (method === "GET") {
          const rows = await service.list(kind);
          if (entityId) {
            const item = rows.find((row) => row[key] === entityId);
            requireValue(item, "Không tìm thấy đối tượng", 404);
            send(200, item);
          } else
            send(200, {
              [kind]: rows,
              fetched_at: new Date(clock()).toISOString(),
            });
          return;
        }
        if (!entityId && method === "POST") {
          authorize(req);
          send(201, await service.save(kind, await jsonBody(req)));
          return;
        }
        if (entityId && method === "PATCH") {
          authorize(req);
          send(200, await service.save(kind, await jsonBody(req), entityId));
          return;
        }
        if (entityId && method === "DELETE") {
          authorize(req);
          send(200, await service.remove(kind, entityId));
          return;
        }
        res.setHeader("Allow", entityId ? "GET, PATCH, DELETE" : "GET, POST");
        throw new ApiError(405, "Method không được hỗ trợ");
      }
      if (path === "/api/esp32/observations" && method === "POST") {
        authorize(req, "device");
        const result = await service.enqueue(await jsonBody(req));
        send(result.duplicate ? 200 : 202, result);
        return;
      }
      const capture = path.match(/^\/api\/esp32\/cameras\/([^/]+)\/capture$/);
      if (capture && method === "POST") {
        authorize(req, "device");
        requireValue(
          req.headers["content-type"]?.split(";")[0].trim() === "image/jpeg",
          "Cần Content-Type: image/jpeg",
          415,
        );
        const bytes = await body(req, POLICY.maxImageBytes);
        requireValue(
          bytes.length >= 4 &&
            bytes[0] === 255 &&
            bytes[1] === 216 &&
            bytes.at(-2) === 255 &&
            bytes.at(-1) === 217,
          "Body không có dấu đầu/cuối JPEG hợp lệ",
        );
        const result = await service.enqueue(
          {
            camera_id: decodeURIComponent(capture[1]),
            observation_id: req.headers["x-observation-id"],
            captured_at: req.headers["x-captured-at"],
          },
          {
            contentHash: createHash("sha256").update(bytes).digest("hex"),
            saveImage: async () => {
              await mkdir(mediaDir, { recursive: true });
              const name = `${randomUUID()}.jpg`;
              await writeFile(join(mediaDir, name), bytes, { flag: "wx" });
              return `/api/images/${name}`;
            },
          },
        );
        send(result.duplicate ? 200 : 202, result);
        return;
      }
      if (path === "/api/ai/jobs" && method === "GET") {
        authorize(req, "ai");
        send(200, {
          jobs: await service.jobs({
            status: url.searchParams.get("status") ?? "pending",
            camera_id: url.searchParams.get("camera_id") ?? undefined,
            limit: Number(url.searchParams.get("limit") ?? 50),
          }),
        });
        return;
      }
      if (path === "/api/ai/results" && method === "POST") {
        authorize(req, "ai");
        send(200, await service.applyResult(await jsonBody(req)));
        return;
      }
      if (
        ["/api/ai/jobs/fail", "/api/ai/jobs/retry"].includes(path) &&
        method === "POST"
      ) {
        authorize(req, "ai");
        send(
          200,
          await service.jobAction(await jsonBody(req), path.endsWith("/retry")),
        );
        return;
      }
      const action = path.match(
        /^\/api\/road-alerts\/([^/]+)\/(alert|weather)$/,
      );
      if (action) {
        authorize(req);
        const roadId = decodeURIComponent(action[1]);
        if (action[2] === "alert" && method === "POST") {
          send(
            201,
            await service.roadAction(roadId, "alert", await jsonBody(req)),
          );
          return;
        }
        if (action[2] === "alert" && method === "DELETE") {
          send(200, await service.roadAction(roadId, "clear"));
          return;
        }
        if (action[2] === "weather" && method === "PUT") {
          send(
            200,
            await service.roadAction(roadId, "weather", await jsonBody(req)),
          );
          return;
        }
        throw new ApiError(405, "Method không được hỗ trợ");
      }
      if (path === "/api/test/simulate" && method === "POST") {
        requireValue(enableTestApi, "API test đã tắt", 404);
        authorize(req);
        send(200, await service.simulate(await jsonBody(req)));
        return;
      }
      throw new ApiError(404, "Endpoint không tồn tại");
    } catch (error) {
      const status =
        error instanceof ApiError
          ? error.status
          : 400 <= error.status && error.status <= 599
            ? error.status
            : 500;
      if (status === 500) console.error(error);
      if (!res.headersSent)
        send(status, {
          error:
            status === 500
              ? "Lỗi đọc/ghi dữ liệu. Xem terminal backend; dữ liệu cũ được giữ khi ghi thất bại."
              : error.message,
        });
      else res.end();
    }
  });
  server.requestTimeout = 30_000;
  server.headersTimeout = 15_000;
  return server;
}
