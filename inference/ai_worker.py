"""
Worker AI Python doc lap cho ssc-road-alerts (phuong an A da duyet).

Thay the hoan toan server/ai-worker.js: KHONG goi sang code Node, KHONG doc
ghi truc tiep server/data/cameras.json hay road-alerts.json. Chi noi chuyen
voi backend qua HTTP/JSON cong khai (GET /api/ai/jobs, POST /api/ai/results,
POST /api/ai/jobs/fail) - dung y het hop dong ma ai-worker.js mau da dung,
bao gom ca allowlist URL anh chong SSRF (backend KHONG tu chan viec nay,
day la trach nhiem cua worker).

CHI CHAY MOT TIEN TRINH DUY NHAT tai mot thoi diem - khong co co che
khoa/claim job giua nhieu worker.

Chay:
    ..\\.venv\\Scripts\\python.exe ai_worker.py            # vong lap, poll moi 3s
    ..\\.venv\\Scripts\\python.exe ai_worker.py --once     # 1 luot roi thoat (test tay)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from analysis import analyze, save_analyzed_image

HERE = Path(__file__).resolve().parent

API_URL = os.environ.get("SSC_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.environ.get("AI_API_KEY", "")
IMAGES_DIR = Path(
    os.environ.get(
        "SSC_IMAGES_DIR",
        str(HERE / ".." / "ssc-road-alerts" / "server" / "data" / "images"),
    )
).resolve()
POLL_INTERVAL_S = float(os.environ.get("AI_POLL_INTERVAL_S", "3"))
REQUEST_TIMEOUT_S = 15

_API_ORIGIN = urlsplit(API_URL)
_IMAGE_PATH_RE = re.compile(r"^/api/images/[a-f0-9-]{36}\.jpg$")


def _headers(json_body: bool) -> dict:
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _request(method: str, path: str, json_payload: dict | None = None) -> dict:
    response = requests.request(
        method,
        API_URL + path,
        headers=_headers(json_body=json_payload is not None),
        json=json_payload,
        timeout=REQUEST_TIMEOUT_S,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"error": response.text}
    if not response.ok:
        raise RuntimeError(f"{response.status_code}: {data.get('error')}")
    return data


def _allowed_image_url(image_url: str | None) -> bool:
    """Allowlist chong SSRF - diem bao mat quan trong nhat cua worker nay.

    Chi chap nhan image_url cung goc voi backend VA dung dinh dang
    /api/images/<uuid>.jpg do chinh backend tu tao ra khi luu anh upload.
    Tu choi moi URL khac (URL ngoai, path la...) TRUOC khi tai - khong bao
    gio de worker tai mot dia chi bat ky do thiet bi/nguon nao gui len.
    """
    if not image_url:
        return False
    parts = urlsplit(image_url)
    if parts.scheme or parts.netloc:
        if (parts.scheme, parts.netloc) != (_API_ORIGIN.scheme, _API_ORIGIN.netloc):
            return False
        path = parts.path
    else:
        path = image_url
    return bool(_IMAGE_PATH_RE.match(path))


def _fail(camera_id: str, observation_id: str, message: str) -> None:
    message = str(message)[:1000]
    try:
        _request(
            "POST",
            "/api/ai/jobs/fail",
            {"camera_id": camera_id, "observation_id": observation_id, "error": message},
        )
    except Exception as error:  # noqa: BLE001 - can bao loi ra console, khong crash worker
        print(f"[{observation_id}] khong bao duoc loi len backend: {error}", file=sys.stderr)
    print(f"[{observation_id}] failed: {message}")


def _process_job(job: dict) -> None:
    camera_id = job["camera_id"]
    observation_id = job["observation_id"]
    image_url = job.get("image_url")

    if not _allowed_image_url(image_url):
        _fail(
            camera_id,
            observation_id,
            f"image_url khong hop le hoac khong nam trong allowlist /api/images/<uuid>.jpg: {image_url!r}",
        )
        return

    absolute_url = image_url if urlsplit(image_url).netloc else API_URL + image_url
    try:
        response = requests.get(absolute_url, timeout=REQUEST_TIMEOUT_S, allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise RuntimeError(f"Anh tra ve redirect ({response.status_code}), tu choi (khong theo redirect)")
        response.raise_for_status()
        jpeg_bytes = response.content
    except Exception as error:  # noqa: BLE001
        _fail(camera_id, observation_id, f"Khong tai duoc anh: {error}")
        return

    try:
        result = analyze(jpeg_bytes)
    except Exception as error:  # noqa: BLE001 - anh hong/model loi khong duoc lam crash worker
        _fail(camera_id, observation_id, f"Model loi: {error}")
        return

    analyzed_url = None
    try:
        filename = save_analyzed_image(result["analyzed_bytes"], camera_id, observation_id, IMAGES_DIR)
        analyzed_url = f"/api/images/{filename}"
    except Exception as error:  # noqa: BLE001 - van gui duoc ket qua so du khong luu duoc anh overlay
        print(f"[{observation_id}] khong luu duoc anh phan tich (van gui ket qua so): {error}", file=sys.stderr)

    payload = {
        "camera_id": camera_id,
        "observation_id": observation_id,
        "waste_coverage_pct": result["waste_coverage_pct"],
        "confidence": result["confidence"],
    }
    if "drain_blockage_pct" in result:  # vang mat khi camera khong thay mieng cong nao
        payload["drain_blockage_pct"] = result["drain_blockage_pct"]
    if analyzed_url:
        payload["analyzed_url"] = analyzed_url

    try:
        outcome = _request("POST", "/api/ai/results", payload)
    except Exception as error:  # noqa: BLE001 - de job o pending, luot poll sau se thu lai
        print(f"[{observation_id}] gui ket qua that bai, se thu lai o luot poll sau: {error}", file=sys.stderr)
        return

    observation = outcome.get("observation", {})
    print(
        f"[{observation_id}] status={observation.get('status')} "
        f"applied={observation.get('applied')} duplicate={outcome.get('duplicate')}"
    )


def run_once() -> int:
    data = _request("GET", "/api/ai/jobs?status=pending&limit=20")
    jobs = data.get("jobs", [])
    for job in jobs:
        _process_job(job)
    return len(jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Chay dung 1 luot roi thoat (dung de test tay).")
    args = parser.parse_args()

    print(f"SSC AI worker (Python) -> {API_URL} | anh phan tich luu tai {IMAGES_DIR}")

    if args.once:
        count = run_once()
        print(f"Da xu ly {count} job.")
        return

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("\nDa nhan Ctrl+C, dung worker.")
            break
        except Exception as error:  # noqa: BLE001 - 1 vong lap loi khong duoc lam dung han worker
            print(f"Loi vong lap: {error}", file=sys.stderr)
        try:
            time.sleep(POLL_INTERVAL_S)
        except KeyboardInterrupt:
            print("\nDa nhan Ctrl+C, dung worker.")
            break


if __name__ == "__main__":
    main()
