"""
Chiếu polygon viền mask (vùng rác phát hiện được, toạ độ pixel ảnh) lên mặt đất phẳng
(mặt phẳng chứa marker), ra toạ độ (lat, lon) gần đúng - dùng file hiệu chỉnh camera
(R, t, camera_matrix) đã lưu ở calibration/<camera_id>.json.

Hình học cốt lõi:
  1) Mỗi điểm ảnh -> 1 tia từ tâm camera, trong hệ CAMERA (camera_model.pixel_to_ray).
  2) Đổi tia sang hệ MARKER (cũng là hệ "mặt đất", z=0 là mặt đất):
        dir_marker = R^T @ ray_cam        (R: marker -> camera, lưu trong calibration)
     Tâm camera trong hệ marker:
        C_marker = -R^T @ t
  3) Giao tia với mặt đất z=0:
        P(s) = C_marker + s * dir_marker ,  cần P.z = 0
        => s = -C_marker.z / dir_marker.z
     Điểm hợp lệ khi s > 0 (giao ở phía trước camera, theo chiều tia nhìn ra).
     Nếu dir_marker.z ~ 0 (tia gần như song song mặt đất - nhìn ra đường chân trời)
     hoặc s <= 0 (mặt đất nằm "phía sau" hướng tia, tức điểm ảnh đó là bầu trời/phía sau)
     thì BỎ điểm đó, in cảnh báo, không crash.
  4) (X, Y) của P trong hệ marker được coi là (Đông, Bắc) mét tương đối so với marker.
     GIẢ ĐỊNH ĐƠN GIẢN HOÁ: trục X của marker trùng hướng Đông, trục Y trùng hướng Bắc
     (không đo compass thật tại hiện trường - ghi rõ hạn chế này, chỉ dùng cho thử nghiệm).
  5) Đổi mét -> độ (lat, lon) bằng công thức xấp xỉ mặt phẳng (meters_to_latlon),
     đủ dùng ở phạm vi vài trăm mét quanh marker.

Diện tích vùng mask (v2):
  Contour cv2.findContours đi qua TÂM các pixel biên nên co ~0.5 px quanh viền => diện tích
  hụt có hệ thống (vật nhỏ: 4-7%). Vì vậy mặc định dùng BIÊN PIXEL (boundary="pixel"):
  mask_to_pixel_boundary_polygons() dò đúng cạnh các ô pixel (mỗi pixel là ô vuông
  [u-0.5, u+0.5] x [v-0.5, v+0.5], tâm pixel ở toạ độ nguyên - cùng quy ước cv2.projectPoints),
  nên diện tích đa giác trên ảnh == số pixel của mask (chính xác, có hỗ trợ lỗ).
  Đường cũ (đỉnh = tâm pixel biên) vẫn còn: boundary="contour_center".

Tỉ lệ khung hình:
  camera_matrix lưu trong calibration gắn với tỉ lệ khung lúc hiệu chỉnh. Ảnh khác tỉ lệ > 1%
  => ValueError (đổi tỉ lệ thường là crop, co giãn fx/fy khác nhau làm méo), trừ khi truyền
  allow_aspect_mismatch=True (CHỈ DÙNG CHO DEMO với ảnh dataset khác tỉ lệ).
"""
from __future__ import annotations

import json
import math
import sys
from typing import List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import cv2
import numpy as np

import camera_model
import config

# Tỉ lệ rộng/cao của ảnh được phép lệch so với lúc hiệu chỉnh (tương đối) trước khi báo lỗi.
ASPECT_TOLERANCE = 0.01

VALID_BOUNDARIES = ("pixel", "contour_center")

# Các cảnh báo đã in trong tiến trình này (mỗi cảnh báo chỉ in MỘT lần, không in mỗi lần chiếu).
_WARNED: set = set()


# ---------------------------------------------------------------------------------------
# Cảnh báo in một lần
# ---------------------------------------------------------------------------------------
def _warn_once(key, message: str) -> bool:
    """In message (stdout) đúng 1 lần cho mỗi key trong tiến trình. Trả True nếu vừa in."""
    if key in _WARNED:
        return False
    _WARNED.add(key)
    print(message)
    return True


def reset_warnings() -> None:
    """Xoá bộ nhớ 'đã cảnh báo' (dùng trong test để kiểm đếm số lần in)."""
    _WARNED.clear()


def warn_calibration_quality(calib: dict) -> None:
    """
    Nếu calib có khối "quality" với "warnings" không rỗng -> in cảnh báo MỘT lần (theo camera_id +
    nội dung). File hiệu chỉnh cũ không có khối quality, hoặc calib dựng trong bộ nhớ -> bỏ qua êm.
    """
    quality = calib.get("quality") if isinstance(calib, dict) else None
    if not isinstance(quality, dict):
        return
    warnings = quality.get("warnings")
    if not warnings:
        return
    if isinstance(warnings, (str, bytes)):
        warnings = [warnings]
    try:
        items = [str(w) for w in warnings]
    except TypeError:
        items = [str(warnings)]
    camera_id = calib.get("camera_id", "unknown")
    detail = "; ".join(items)
    _warn_once(
        ("quality", camera_id, detail),
        f"[CẢNH BÁO] Chất lượng hiệu chỉnh camera '{camera_id}': {detail}",
    )


# ---------------------------------------------------------------------------------------
# Calibration + hình học cơ bản
# ---------------------------------------------------------------------------------------
def load_calibration(camera_id: str) -> dict:
    """
    Đọc file hiệu chỉnh calibration/<camera_id>.json. Lỗi rõ ràng nếu chưa có.
    Nếu file có khối "quality.warnings" thì in cảnh báo MỘT lần (file cũ không có khối đó: bỏ qua).
    """
    path = config.CALIBRATION_DIR / f"{camera_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Chưa có file hiệu chỉnh cho camera '{camera_id}': {path}. "
            f"Hãy chạy calibrate_aruco.py trước."
        )
    calib = json.loads(path.read_text(encoding="utf-8"))
    warn_calibration_quality(calib)
    return calib


def camera_origin_in_marker_frame(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Vị trí camera, biểu diễn trong hệ toạ độ marker/mặt đất: C_marker = -R^T @ t."""
    return -R.T @ t


def ray_to_marker_frame(ray_cam: np.ndarray, R: np.ndarray) -> np.ndarray:
    """Đổi hướng tia từ hệ camera sang hệ marker: dir_marker = R^T @ ray_cam."""
    return R.T @ ray_cam


def intersect_ray_with_ground(
    cam_origin_marker: np.ndarray,
    dir_marker: np.ndarray,
    min_z_component: float = 1e-9,
) -> Optional[Tuple[float, float]]:
    """
    Giao tia (gốc cam_origin_marker, hướng dir_marker) với mặt đất z=0 (hệ marker).

    Trả (X, Y) nếu giao ở phía trước camera (s > 0).
    Trả None nếu tia song song mặt đất (|dir.z| quá nhỏ) hoặc giao điểm ở phía sau/lên trời
    (s <= 0) - không crash, bên gọi tự in cảnh báo.
    """
    dz = float(dir_marker[2])
    if abs(dz) < min_z_component:
        return None
    s = -float(cam_origin_marker[2]) / dz
    if s <= 0:
        return None
    point = cam_origin_marker + s * dir_marker
    return float(point[0]), float(point[1])


def calib_azimuth_deg(calib: dict) -> float:
    """Phương vị la bàn (độ) của trục +Y bảng trong calib; file cũ không có khoá -> 0.0 (Y = Bắc)."""
    return float(calib.get("azimuth_deg", 0.0)) if isinstance(calib, dict) else 0.0


def marker_xy_to_enu(x, y, azimuth_deg: float = 0.0):
    """
    Đổi (x, y) mét trong hệ marker -> (Đông, Bắc) mét. x, y có thể là số hoặc mảng numpy cùng shape.

    azimuth_deg (beta) = phương vị la bàn của trục +Y bảng (0 = Bắc, 90 = Đông, chiều kim đồng hồ):
        E =  x*cos(beta) + y*sin(beta)
        N = -x*sin(beta) + y*cos(beta)
    beta = 0 trả đúng (x, y) như hành vi cũ (X marker = Đông, Y marker = Bắc). Ví dụ beta = 90:
    điểm (1, 0) -> (0, -1) (Nam); điểm (0, 1) -> (1, 0) (Đông). Bội của 90 độ dùng sin/cos chính xác.
    """
    b = float(azimuth_deg) % 360.0
    exact = {0.0: (1.0, 0.0), 90.0: (0.0, 1.0), 180.0: (-1.0, 0.0), 270.0: (0.0, -1.0)}
    if b == 0.0:
        return x, y
    c, s = exact.get(b, (math.cos(math.radians(b)), math.sin(math.radians(b))))
    return x * c + y * s, -x * s + y * c


def meters_to_latlon(lat0_deg: float, lon0_deg: float, east_m: float, north_m: float) -> Tuple[float, float]:
    """
    Đổi độ lệch (Đông, Bắc) mét -> (lat, lon) tuyệt đối, xấp xỉ mặt phẳng cục bộ
    (đủ dùng ở phạm vi vài trăm mét quanh điểm gốc (lat0, lon0)).

    Dịch về phía Bắc (north_m > 0) làm TĂNG lat; dịch về phía Đông (east_m > 0) làm TĂNG lon
    (đúng chiều ở Việt Nam - bán cầu Bắc, Đông bán cầu).
    """
    lat0_rad = math.radians(lat0_deg)
    delta_lat_deg = (north_m / config.EARTH_RADIUS_M) * (180.0 / math.pi)
    delta_lon_deg = (east_m / (config.EARTH_RADIUS_M * math.cos(lat0_rad))) * (180.0 / math.pi)
    return lat0_deg + delta_lat_deg, lon0_deg + delta_lon_deg


def _scaled_camera_matrix(
    calib: dict,
    image_size: Tuple[int, int],
    allow_aspect_mismatch: bool = False,
) -> np.ndarray:
    """
    Co giãn camera_matrix đã lưu trong calibration nếu ảnh chứa mask có độ phân giải
    khác ảnh lúc hiệu chỉnh (cùng 1 camera vật lý, cùng góc mở ống kính, chỉ khác resize).

    - Cùng kích thước: trả nguyên camera_matrix.
    - Tỉ lệ rộng/cao lệch quá ASPECT_TOLERANCE (1%) so với lúc hiệu chỉnh:
        * mặc định -> ValueError (co giãn fx, fy khác nhau làm méo pixel; đổi tỉ lệ thật
          thường là crop chứ không phải resize, nên không thể tự suy đúng);
        * allow_aspect_mismatch=True (CHỈ DÙNG CHO DEMO) -> in MỘT cảnh báo/tiến trình và dùng
          MỘT hệ số co giãn chung cho cả fx và fy: s = đường chéo ảnh mới / đường chéo ảnh lúc
          hiệu chỉnh (giữ nguyên góc mở đường chéo, vì camera_matrix gốc dựng từ góc mở chéo).
          Điểm chính (cx, cy) co theo từng trục để giữ đúng vị trí tương đối trong ảnh.
    - Khác kích thước nhưng cùng tỉ lệ: cũng dùng hệ số chung s như trên (khác hệ số riêng từng
      trục < 1%), in 1 ghi chú/tiến trình cho mỗi cặp kích thước.
    """
    cm = np.array(calib["camera_matrix"], dtype=np.float64).copy()
    calib_w, calib_h = calib["image_size"]
    w, h = image_size
    if (calib_w, calib_h) == (w, h):
        return cm
    if w <= 0 or h <= 0 or calib_w <= 0 or calib_h <= 0:
        raise ValueError(f"Kích thước ảnh không hợp lệ: ảnh {w}x{h}, lúc hiệu chỉnh {calib_w}x{calib_h}")

    aspect = w / h
    calib_aspect = calib_w / calib_h
    rel_diff = abs(aspect / calib_aspect - 1.0)
    mismatch = rel_diff > ASPECT_TOLERANCE
    if mismatch and not allow_aspect_mismatch:
        raise ValueError(
            f"Tỉ lệ khung hình của ảnh ({w}x{h}, rộng/cao = {aspect:.4f}) khác tỉ lệ lúc hiệu chỉnh "
            f"({calib_w}x{calib_h}, rộng/cao = {calib_aspect:.4f}) quá {ASPECT_TOLERANCE * 100:.0f}% "
            f"(lệch {rel_diff * 100:.1f}%). Không tự co giãn fx/fy riêng rẽ vì sẽ làm méo kết quả. "
            f"Hãy hiệu chỉnh lại camera đúng ở độ phân giải/tỉ lệ đang dùng, hoặc chỉ khi chạy DEMO với "
            f"ảnh khác tỉ lệ thì truyền allow_aspect_mismatch=True."
        )

    s = math.hypot(w, h) / math.hypot(calib_w, calib_h)
    cm[0, 0] *= s  # fx
    cm[1, 1] *= s  # fy (cùng hệ số => pixel vuông, không méo)
    cm[0, 2] *= w / calib_w  # cx
    cm[1, 2] *= h / calib_h  # cy
    if mismatch:
        _warn_once(
            ("aspect", calib.get("camera_id", "unknown"), calib_w, calib_h, w, h),
            f"[CẢNH BÁO] DEMO: tỉ lệ khung hình ảnh ({w}x{h}) khác lúc hiệu chỉnh ({calib_w}x{calib_h}) "
            f"{rel_diff * 100:.1f}% - đã cho phép (allow_aspect_mismatch=True) và dùng 1 hệ số co giãn chung "
            f"{s:.4f} cho fx, fy (giữ góc mở đường chéo). Kết quả KHÔNG đáng tin cho đo đạc thật.",
        )
    else:
        _warn_once(
            ("resize", calib.get("camera_id", "unknown"), calib_w, calib_h, w, h),
            f"[CẢNH BÁO] Ảnh mask ({w}x{h}) khác kích thước ảnh lúc hiệu chỉnh ({calib_w}x{calib_h}) "
            f"- đã co giãn camera_matrix tương ứng (hệ số {s:.4f}).",
        )
    return cm


# ---------------------------------------------------------------------------------------
# Mask -> polygon (biên pixel / contour tâm pixel)
# ---------------------------------------------------------------------------------------
def _ring_area(ring: np.ndarray) -> float:
    """Diện tích CÓ DẤU (shoelace) của vòng (N,2), không cần khép kín."""
    r = np.asarray(ring, dtype=np.float64)
    if len(r) < 3:
        return 0.0
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def polygon_area_m2(polygon_xy: np.ndarray, holes: Optional[Sequence[np.ndarray]] = None) -> float:
    """
    Diện tích đa giác (m²) từ toạ độ MÉT (Đông, Bắc) bằng shoelace, trị tuyệt đối.
    holes: danh sách vòng lỗ (cũng theo mét) - diện tích lỗ được trừ đi.
    """
    area = abs(_ring_area(polygon_xy))
    for hole in holes or []:
        area -= abs(_ring_area(hole))
    return float(area)


def _merge_collinear(ring: np.ndarray) -> np.ndarray:
    """Bỏ các đỉnh nằm giữa 2 cạnh cùng hướng (không đổi hình học)."""
    n = len(ring)
    if n < 4:
        return ring
    prev_d = ring - np.roll(ring, 1, axis=0)
    next_d = np.roll(ring, -1, axis=0) - ring
    cross = prev_d[:, 0] * next_d[:, 1] - prev_d[:, 1] * next_d[:, 0]
    keep = np.abs(cross) > 1e-12
    out = ring[keep]
    return out if len(out) >= 3 else ring


def mask_to_pixel_boundary_polygons(
    mask: np.ndarray,
    min_area_px: int = 0,
    simplify_eps_px: float = 0.0,
) -> List[dict]:
    """
    Tách mask nhị phân thành các đa giác theo BIÊN PIXEL (cạnh các ô pixel), chính xác tuyệt đối.

    Mỗi pixel (x, y) là ô vuông [x-0.5, x+0.5] x [y-0.5, y+0.5] (tâm pixel ở toạ độ nguyên, đúng
    quy ước cv2.projectPoints / camera_matrix). Vì vậy:
        diện tích đa giác (viền ngoài trừ lỗ) == số pixel của thành phần đó, KHÔNG co 0.5 px như
        cv2.findContours (đỉnh qua tâm pixel biên).

    Kết nối: pixel chéo nhau (chỉ chạm góc) được coi là TÁCH RỜI (4-liên thông), nên mỗi vòng
    không tự cắt vào giữa 2 pixel; hai thành phần chỉ chạm góc cho ra 2 đa giác riêng.
    Lỗ (holes) được hỗ trợ: mỗi đa giác có "holes" = list vòng trong.

    Trả list dict (sắp tất định: diện tích giảm dần, hoà thì theo (y, x) đỉnh đầu):
        {
          "outer":   ndarray (N,2) float64, toạ độ pixel (u, v), vòng ngoài (không lặp đỉnh đầu),
          "holes":   list[ndarray (M,2)],
          "area_px": int, số pixel thật của thành phần (đã trừ lỗ),
          "seed_px": (x, y) 1 pixel bất kỳ thuộc thành phần (để tra nhãn liên thông 4 bên ngoài),
        }
    min_area_px: bỏ thành phần có area_px < ngưỡng này.
    simplify_eps_px > 0: rút gọn đỉnh bằng cv2.approxPolyDP (làm lệch viền tối đa ~eps, KHÔNG còn
        khớp diện tích tuyệt đối); vòng nào rút gọn xuống < 3 đỉnh thì giữ nguyên bản chính xác.
    """
    m = (np.asarray(mask) > 0)
    if m.ndim != 2:
        raise ValueError(f"mask phải là 2D, nhận shape {m.shape}")
    h, w = m.shape
    if not m.any():
        return []

    # Đệm 1 pixel nền quanh mask để mọi biên đều được phát hiện
    pad = np.zeros((h + 2, w + 2), dtype=bool)
    pad[1:-1, 1:-1] = m
    core = pad[1:-1, 1:-1]
    top_bg = ~pad[:-2, 1:-1]
    right_bg = ~pad[1:-1, 2:]
    bottom_bg = ~pad[2:, 1:-1]
    left_bg = ~pad[1:-1, :-2]

    ys, xs = np.nonzero(core)
    # Toạ độ góc (corner): pixel (x,y) có góc TL=(x,y), TR=(x+1,y), BR=(x+1,y+1), BL=(x,y+1).
    # Cạnh định hướng theo chiều kim đồng hồ trên màn hình (y hướng xuống) => phần mask nằm bên PHẢI
    # => viền ngoài có diện tích dấu dương, lỗ có diện tích dấu âm.
    e_x0, e_y0, e_x1, e_y1, e_px, e_py = [], [], [], [], [], []

    def add(sel, x0, y0, x1, y1):
        if sel.any():
            xx, yy = xs[sel], ys[sel]
            e_x0.append(xx + x0)
            e_y0.append(yy + y0)
            e_x1.append(xx + x1)
            e_y1.append(yy + y1)
            e_px.append(xx)
            e_py.append(yy)

    sel = top_bg[ys, xs]
    add(sel, 0, 0, 1, 0)  # TL -> TR
    sel = right_bg[ys, xs]
    add(sel, 1, 0, 1, 1)  # TR -> BR
    sel = bottom_bg[ys, xs]
    add(sel, 1, 1, 0, 1)  # BR -> BL
    sel = left_bg[ys, xs]
    add(sel, 0, 1, 0, 0)  # BL -> TL

    X0 = np.concatenate(e_x0)
    Y0 = np.concatenate(e_y0)
    X1 = np.concatenate(e_x1)
    Y1 = np.concatenate(e_y1)
    PX = np.concatenate(e_px)
    PY = np.concatenate(e_py)
    n_edges = len(X0)

    outgoing: dict = {}
    for i in range(n_edges):
        outgoing.setdefault((int(X0[i]), int(Y0[i])), []).append(i)
    used = np.zeros(n_edges, dtype=bool)

    # Nhãn thành phần 4-liên thông (khớp quy tắc "rẽ phải" tách pixel chéo ở bước nối cạnh)
    n_lab, labels = cv2.connectedComponents(core.astype(np.uint8), connectivity=4)
    comp_area = np.bincount(labels.ravel(), minlength=n_lab)

    rings_by_label: dict = {}  # label -> list[(signed_area, ring ndarray corner coords)]
    rings_seed: dict = {}  # label -> (x, y) 1 pixel thuộc thành phần đó
    for start in range(n_edges):
        if used[start]:
            continue
        verts = []
        cur = start
        used[cur] = True
        while True:
            verts.append((int(X0[cur]), int(Y0[cur])))
            vx, vy = int(X1[cur]), int(Y1[cur])
            cands = [e for e in outgoing.get((vx, vy), []) if (not used[e]) or e == start]
            if not cands:
                break  # không xảy ra với mask hợp lệ; thoát an toàn
            if len(cands) > 1:
                # Đỉnh "bàn cờ" (2 pixel chéo): ưu tiên rẽ PHẢI so với hướng đi để ôm đúng 1 pixel
                dx, dy = vx - int(X0[cur]), vy - int(Y0[cur])
                rx, ry = -dy, dx  # vector rẽ phải (y hướng xuống)
                pref = [e for e in cands if (int(X1[e]) - vx, int(Y1[e]) - vy) == (rx, ry)]
                nxt = pref[0] if pref else cands[0]
            else:
                nxt = cands[0]
            if nxt == start:
                break
            used[nxt] = True
            cur = nxt
        ring = np.array(verts, dtype=np.float64)
        if len(ring) < 4:
            continue
        ring = _merge_collinear(ring)
        lab = int(labels[PY[start], PX[start]])
        rings_by_label.setdefault(lab, []).append((_ring_area(ring), ring))
        rings_seed.setdefault(lab, (int(PX[start]), int(PY[start])))

    out: List[dict] = []
    for lab, rings in rings_by_label.items():
        area_px = int(comp_area[lab])
        if area_px < min_area_px:
            continue
        outers = [r for a, r in rings if a > 0]
        holes = [r for a, r in rings if a < 0]
        if not outers:
            continue
        outer = max(outers, key=lambda r: abs(_ring_area(r)))

        def conv(r: np.ndarray) -> np.ndarray:
            r = r - 0.5  # toạ độ góc -> toạ độ tâm-nguyên (pixel i trải từ i-0.5 đến i+0.5)
            if simplify_eps_px > 0:
                ap = cv2.approxPolyDP(r.astype(np.float32).reshape(-1, 1, 2), float(simplify_eps_px), True)
                ap = ap.reshape(-1, 2).astype(np.float64)
                if len(ap) >= 3:
                    return ap
            return r

        seed = rings_seed[lab]
        out.append(
            {
                "outer": conv(outer),
                "holes": [conv(hh) for hh in holes],
                "area_px": area_px,
                "seed_px": seed,
            }
        )

    out.sort(key=lambda d: (-d["area_px"], float(d["outer"][:, 1].min()), float(d["outer"][:, 0].min())))
    return out


def mask_to_center_contour_polygons(mask: np.ndarray, min_area_px: int = 0) -> List[dict]:
    """
    Đường CŨ ("contour_center"): cv2.findContours (RETR_CCOMP, CHAIN_APPROX_NONE), đỉnh = tâm
    pixel biên => đa giác co ~0.5 px quanh viền (diện tích hụt). Cùng định dạng trả về với
    mask_to_pixel_boundary_polygons (area_px = số pixel thật của thành phần).
    """
    m = (np.asarray(mask) > 0).astype(np.uint8)
    if m.ndim != 2:
        raise ValueError(f"mask phải là 2D, nhận shape {m.shape}")
    contours, hierarchy = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        return []
    hierarchy = hierarchy.reshape(-1, 4)
    out: List[dict] = []
    for i, c in enumerate(contours):
        if hierarchy[i][3] != -1 or len(c) < 3:  # chỉ lấy viền ngoài (không có cha)
            continue
        holes = []
        child = hierarchy[i][2]
        while child != -1:
            if len(contours[child]) >= 3:
                holes.append(contours[child].reshape(-1, 2).astype(np.float64))
            child = hierarchy[child][0]
        filled = np.zeros_like(m)
        cv2.drawContours(filled, [c], -1, 1, thickness=cv2.FILLED)
        for hc in holes:
            cv2.drawContours(filled, [hc.astype(np.int32).reshape(-1, 1, 2)], -1, 0, thickness=cv2.FILLED)
        area_px = int((filled > 0).sum())
        if area_px < min_area_px or area_px == 0:
            continue
        out.append({"outer": c.reshape(-1, 2).astype(np.float64), "holes": holes, "area_px": area_px})
    out.sort(key=lambda d: (-d["area_px"], float(d["outer"][:, 1].min()), float(d["outer"][:, 0].min())))
    return out


def _mask_polygons(mask: np.ndarray, boundary: str, min_area_px: int, simplify_eps_px: float) -> List[dict]:
    if boundary not in VALID_BOUNDARIES:
        raise ValueError(f"boundary phải là một trong {VALID_BOUNDARIES}, nhận '{boundary}'")
    if boundary == "pixel":
        return mask_to_pixel_boundary_polygons(mask, min_area_px, simplify_eps_px)
    return mask_to_center_contour_polygons(mask, min_area_px)


# ---------------------------------------------------------------------------------------
# Pixel -> mặt đất (vector hoá) + tiện ích chiếu theo mét
# ---------------------------------------------------------------------------------------
def pixels_to_ground_xy(
    uv: np.ndarray,
    camera_matrix: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
    min_z_component: float = 1e-9,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Chiếu mảng điểm ảnh (N,2) xuống mặt đất z=0 (vector hoá, cùng công thức pixel_to_ray ->
    ray_to_marker_frame -> intersect_ray_with_ground). Trả (xy (N,2) mét [Đông, Bắc], valid (N,) bool);
    điểm không hợp lệ (tia song song / giao sau lưng camera) có xy = NaN, valid = False.
    """
    uv = np.asarray(uv, dtype=np.float64).reshape(-1, 2)
    fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]
    cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]
    rays = np.stack([(uv[:, 0] - cx) / fx, (uv[:, 1] - cy) / fy, np.ones(len(uv))], axis=1)
    rays /= np.linalg.norm(rays, axis=1, keepdims=True)
    dirs = rays @ R  # hàng i = (R^T @ ray_i)^T
    C = camera_origin_in_marker_frame(R, np.asarray(t, dtype=np.float64).reshape(3))
    dz = dirs[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = -C[2] / dz
    valid = (np.abs(dz) >= min_z_component) & (s > 0)
    pts = C[None, :2] + s[:, None] * dirs[:, :2]
    pts[~valid] = np.nan
    return pts, valid


def _projection_setup(calib: dict, image_size: Tuple[int, int], allow_aspect_mismatch: bool):
    warn_calibration_quality(calib)
    camera_matrix = _scaled_camera_matrix(calib, image_size, allow_aspect_mismatch)
    R = np.array(calib["R"], dtype=np.float64)
    t = np.array(calib["t"], dtype=np.float64).reshape(3)
    return camera_matrix, R, t


def project_pixel_polygon_to_ground_m(
    polygon_px: np.ndarray,
    image_size: Tuple[int, int],
    calib: dict,
    allow_aspect_mismatch: bool = False,
    _setup=None,
) -> Tuple[Optional[np.ndarray], int]:
    """
    Chiếu 1 vòng đa giác theo toạ độ PIXEL (u, v) xuống mặt đất, trả ((M,2) mét [Đông, Bắc], số điểm bỏ).
    Đã xoay theo calib["azimuth_deg"] (mặc định 0 = trục Y bảng là Bắc; xem marker_xy_to_enu).
    Trả (None, n_bỏ) nếu còn < 3 điểm hợp lệ. Điểm không cắt mặt đất bị bỏ (không crash).
    """
    camera_matrix, R, t = _setup or _projection_setup(calib, image_size, allow_aspect_mismatch)
    pts, valid = pixels_to_ground_xy(polygon_px, camera_matrix, R, t)
    n_dropped = int((~valid).sum())
    good = pts[valid]
    if len(good) < 3:
        return None, n_dropped
    e, n = marker_xy_to_enu(good[:, 0], good[:, 1], calib_azimuth_deg(calib))  # azimuth 0: giữ nguyên
    return np.stack([e, n], axis=1), n_dropped


def project_mask_to_ground_m(
    mask: np.ndarray,
    calib: dict,
    boundary: str = "pixel",
    allow_aspect_mismatch: bool = False,
    min_area_px: int = 0,
    simplify_eps_px: float = 0.0,
) -> dict:
    """
    Chiếu mask (H,W) xuống mặt đất, trả đa giác theo MÉT (Đông, Bắc) quanh marker + diện tích m²
    (đã xoay theo calib["azimuth_deg"], mặc định 0; xoay không đổi diện tích).

    boundary: "pixel" (mặc định, biên pixel - diện tích khớp số pixel) hoặc "contour_center" (cũ).
    Trả dict:
        {
          "polygons": [ {"outer_m": (N,2), "holes_m": [(M,2),...], "area_m2": float, "area_px": int}, ... ],
          "area_m2":  tổng diện tích (m²) mọi đa giác (đã trừ lỗ),
          "area_px":  tổng số pixel mọi đa giác,
          "n_dropped_vertices": số đỉnh bị bỏ do tia không cắt mặt đất,
        }
    Đa giác nào mất >= 3 điểm hợp lệ (vòng ngoài) thì bị loại. Vòng lỗ không đủ điểm thì bỏ lỗ đó.
    Mặt đất coi phẳng: chỉ đúng với vật nằm sát mặt đất (xem README/size_test về vật có chiều cao).
    """
    arr = np.asarray(mask)
    if arr.ndim != 2:
        raise ValueError(f"mask phải là 2D, nhận shape {arr.shape}")
    h, w = arr.shape
    setup = _projection_setup(calib, (w, h), allow_aspect_mismatch)
    polys = _mask_polygons(arr, boundary, min_area_px, simplify_eps_px)

    out_polys = []
    n_dropped_total = 0
    for p in polys:
        outer_m, nd = project_pixel_polygon_to_ground_m(p["outer"], (w, h), calib, _setup=setup)
        n_dropped_total += nd
        if outer_m is None:
            continue
        holes_m = []
        for hole in p["holes"]:
            hm, nd_h = project_pixel_polygon_to_ground_m(hole, (w, h), calib, _setup=setup)
            n_dropped_total += nd_h
            if hm is not None:
                holes_m.append(hm)
        out_polys.append(
            {
                "outer_m": outer_m,
                "holes_m": holes_m,
                "area_m2": polygon_area_m2(outer_m, holes_m),
                "area_px": p["area_px"],
            }
        )
    return {
        "polygons": out_polys,
        "area_m2": float(sum(p["area_m2"] for p in out_polys)),
        "area_px": int(sum(p["area_px"] for p in out_polys)),
        "n_dropped_vertices": n_dropped_total,
    }


# ---------------------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------------------
def _oriented(ring_xy: np.ndarray, ccw: bool) -> np.ndarray:
    """Đảo chiều vòng (Đông, Bắc) cho đúng RFC 7946: viền ngoài ngược chiều kim đồng hồ, lỗ thuận chiều."""
    is_ccw = _ring_area(ring_xy) > 0
    return ring_xy if is_ccw == ccw else ring_xy[::-1]


def _ring_m_to_lonlat(ring_xy: np.ndarray, lat0: float, lon0: float) -> list:
    ring = []
    for east_m, north_m in ring_xy:
        lat, lon = meters_to_latlon(lat0, lon0, float(east_m), float(north_m))
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring


def _norm_polygon_to_lonlat_ring(
    polygon_norm: Sequence[Tuple[float, float]],
    image_size: Tuple[int, int],
    setup,
    lat0: float,
    lon0: float,
    azimuth_deg: float = 0.0,
) -> Optional[list]:
    """Vòng toạ độ chuẩn hoá -> ring [lon, lat] khép kín (giữ nguyên hành vi/dòng in cảnh báo cũ)."""
    w, h = image_size
    camera_matrix, R, t = setup
    cam_origin_marker = camera_origin_in_marker_frame(R, t)

    ring_lonlat = []
    n_skipped = 0
    for xn, yn in polygon_norm:
        u = xn * w
        v = yn * h
        ray_cam = camera_model.pixel_to_ray(camera_matrix, u, v)
        dir_marker = ray_to_marker_frame(ray_cam, R)
        ground_xy = intersect_ray_with_ground(cam_origin_marker, dir_marker)
        if ground_xy is None:
            n_skipped += 1
            print(
                f"[CẢNH BÁO] Bỏ điểm pixel chuẩn hoá ({xn:.4f},{yn:.4f}) "
                f"- tia không cắt mặt đất phía trước camera"
            )
            continue
        east_m, north_m = marker_xy_to_enu(ground_xy[0], ground_xy[1], azimuth_deg)
        lat, lon = meters_to_latlon(lat0, lon0, east_m, north_m)
        ring_lonlat.append([lon, lat])

    if n_skipped:
        print(f"[THÔNG TIN] Đã bỏ {n_skipped}/{len(polygon_norm)} điểm không hợp lệ")

    if len(ring_lonlat) < 3:
        print("[LỖI] Không đủ điểm hợp lệ (>=3) để tạo polygon GeoJSON")
        return None

    if ring_lonlat[0] != ring_lonlat[-1]:
        ring_lonlat.append(list(ring_lonlat[0]))
    return ring_lonlat


def project_mask_to_geojson(
    polygon_norm: Optional[Sequence[Tuple[float, float]]],
    image_size: Tuple[int, int],
    calib: dict,
    boundary: str = "pixel",
    *,
    mask: Optional[np.ndarray] = None,
    allow_aspect_mismatch: bool = False,
    simplify_eps_px: float = 0.0,
) -> Optional[dict]:
    """
    polygon_norm: list toạ độ (x, y) CHUẨN HOÁ 0..1 của viền mask, trong ảnh gốc.
    image_size:   (width, height) pixel THẬT của ảnh chứa mask đó.
    calib:        dict hiệu chỉnh đã load (xem load_calibration()).
    boundary:     cách hiểu viền (xem bên dưới), "pixel" (mặc định) | "contour_center" (cũ).
    mask:         (tuỳ chọn) mảng mask (H,W) - nếu có thì đa giác được DỰNG TỪ MASK theo `boundary`
                  (polygon_norm bị bỏ qua, có thể là None), và image_size phải khớp (W,H) của mask.
    allow_aspect_mismatch: CHỈ DÙNG CHO DEMO - cho phép ảnh khác tỉ lệ khung lúc hiệu chỉnh.
    simplify_eps_px: (chỉ khi có mask) > 0 thì rút gọn đỉnh bằng approxPolyDP với sai số tối đa ~eps pixel
                  (giảm số đỉnh GeoJSON; diện tích không còn khớp tuyệt đối số pixel). Mặc định 0 = chính xác.

    Hành vi theo đầu vào:
      * Có `mask`:
          - boundary="pixel": đa giác theo biên pixel (mask_to_pixel_boundary_polygons) - diện
            tích khớp số pixel của mask, có lỗ; nhiều thành phần -> MultiPolygon.
          - boundary="contour_center": cv2.findContours (đỉnh = tâm pixel biên), diện tích co ~0.5 px.
      * Chỉ có `polygon_norm` (đường cũ, kết quả GIỐNG HỆT bản trước): các đỉnh được chiếu nguyên
        trạng - đỉnh được coi là NẰM TRÊN biên vùng (đúng với nhãn tay và với đầu ra của
        mask_to_pixel_boundary_polygons), nên `boundary` không đổi gì. Muốn khắc phục độ co 0.5 px
        của contour qua tâm pixel thì truyền `mask=` thay vì tự tạo polygon từ cv2.findContours.

    Trả về GeoJSON Feature (Polygon / MultiPolygon, toạ độ [lon, lat]) hoặc None nếu không còn đủ
    điểm hợp lệ. Có thể raise ValueError nếu lệch tỉ lệ khung hình (xem _scaled_camera_matrix).
    """
    if boundary not in VALID_BOUNDARIES:
        raise ValueError(f"boundary phải là một trong {VALID_BOUNDARIES}, nhận '{boundary}'")
    lat0, lon0 = calib["marker_latlon"]
    camera_id = calib.get("camera_id", "unknown")

    if mask is not None:
        arr = np.asarray(mask)
        if arr.ndim != 2 or (arr.shape[1], arr.shape[0]) != (int(image_size[0]), int(image_size[1])):
            raise ValueError(
                f"image_size {tuple(image_size)} không khớp mask shape (H,W) = {arr.shape}"
            )
        res = project_mask_to_ground_m(
            arr, calib, boundary, allow_aspect_mismatch, simplify_eps_px=simplify_eps_px
        )
        if res["n_dropped_vertices"]:
            print(f"[THÔNG TIN] Đã bỏ {res['n_dropped_vertices']} đỉnh không cắt mặt đất phía trước camera")
        polygons = []
        for p in res["polygons"]:
            rings = [_ring_m_to_lonlat(_oriented(p["outer_m"], True), lat0, lon0)]
            rings += [_ring_m_to_lonlat(_oriented(hm, False), lat0, lon0) for hm in p["holes_m"]]
            polygons.append(rings)
        if not polygons:
            print("[LỖI] Không đủ điểm hợp lệ (>=3) để tạo polygon GeoJSON")
            return None
        props = {
            "camera_id": camera_id,
            "label": "rac",
            "boundary": boundary,
            "area_m2": res["area_m2"],
            "area_px": res["area_px"],
        }
        if len(polygons) == 1:
            geometry = {"type": "Polygon", "coordinates": polygons[0]}
        else:
            geometry = {"type": "MultiPolygon", "coordinates": polygons}
        return {"type": "Feature", "properties": props, "geometry": geometry}

    if polygon_norm is None:
        raise ValueError("Cần truyền polygon_norm hoặc mask")
    setup = _projection_setup(calib, image_size, allow_aspect_mismatch)
    ring_lonlat = _norm_polygon_to_lonlat_ring(
        polygon_norm, image_size, setup, lat0, lon0, calib_azimuth_deg(calib)
    )
    if ring_lonlat is None:
        return None
    return {
        "type": "Feature",
        "properties": {
            "camera_id": camera_id,
            "label": "rac",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring_lonlat],
        },
    }


def project_polygons_to_geojson(
    polygons_norm: Sequence[Sequence[Tuple[float, float]]],
    image_size: Tuple[int, int],
    calib: dict,
    allow_aspect_mismatch: bool = False,
    extra_properties: Optional[dict] = None,
) -> Optional[dict]:
    """
    Chiếu NHIỀU polygon chuẩn hoá (vd. mọi polygon lớp Trash của 1 ảnh nhãn) thành 1 Feature
    MultiPolygon (hoặc Polygon nếu chỉ còn 1 polygon hợp lệ). Polygon nào không đủ điểm hợp lệ bị bỏ.
    Trả None nếu không polygon nào chiếu được. Đỉnh được chiếu nguyên trạng (xem project_mask_to_geojson).
    """
    lat0, lon0 = calib["marker_latlon"]
    setup = _projection_setup(calib, image_size, allow_aspect_mismatch)
    rings = []
    azimuth = calib_azimuth_deg(calib)
    for poly in polygons_norm:
        ring = _norm_polygon_to_lonlat_ring(poly, image_size, setup, lat0, lon0, azimuth)
        if ring is not None:
            rings.append([ring])
    if not rings:
        return None
    props = {
        "camera_id": calib.get("camera_id", "unknown"),
        "label": "rac",
        "n_polygons": len(rings),
    }
    if extra_properties:
        props.update(extra_properties)
    geometry = (
        {"type": "Polygon", "coordinates": rings[0]}
        if len(rings) == 1
        else {"type": "MultiPolygon", "coordinates": rings}
    )
    return {"type": "Feature", "properties": props, "geometry": geometry}


def marker_point_geojson(calib: dict) -> dict:
    """GeoJSON Feature Point - vị trí BẢNG ĐÁNH DẤU (marker), = calib["marker_latlon"]."""
    lat0, lon0 = calib["marker_latlon"]
    return {
        "type": "Feature",
        "properties": {
            "camera_id": calib.get("camera_id", "unknown"),
            "source": calib.get("source", "unknown"),
            "role": "marker",
            "label": "Vị trí bảng đánh dấu",
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lon0, lat0],
        },
    }


def camera_position_geojson(calib: dict) -> dict:
    """
    GeoJSON Feature Point - vị trí camera THẬT tính từ pose hiệu chỉnh: C_marker = -R^T @ t (hệ marker,
    X~Đông, Y~Bắc, Z~lên) rồi đổi mét -> lat/lon quanh marker_latlon bằng meters_to_latlon.
    Properties kèm east_m, north_m (so với marker), height_m (độ cao camera trên mặt đất).
    """
    lat0, lon0 = calib["marker_latlon"]
    R = np.array(calib["R"], dtype=np.float64)
    t = np.array(calib["t"], dtype=np.float64).reshape(3)
    c = camera_origin_in_marker_frame(R, t)
    c = np.array([*marker_xy_to_enu(float(c[0]), float(c[1]), calib_azimuth_deg(calib)), float(c[2])])
    lat, lon = meters_to_latlon(lat0, lon0, float(c[0]), float(c[1]))
    return {
        "type": "Feature",
        "properties": {
            "camera_id": calib.get("camera_id", "unknown"),
            "source": calib.get("source", "unknown"),
            "role": "camera",
            "label": "Camera (tính từ hiệu chỉnh)",
            "east_m": float(c[0]),
            "north_m": float(c[1]),
            "height_m": float(c[2]),
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
    }


def camera_point_geojson(calib: dict) -> dict:
    """
    DEPRECATED - tên cũ gây hiểu nhầm: hàm này trả vị trí BẢNG ĐÁNH DẤU (marker_latlon), KHÔNG phải
    vị trí camera. Giữ lại để code cũ (stress_test, size_test, model_demo) vẫn chạy; toạ độ trả về
    y hệt trước đây. Code mới dùng marker_point_geojson() (vị trí marker) và camera_position_geojson()
    (vị trí camera tính từ R, t).
    """
    return marker_point_geojson(calib)


# ---------------------------------------------------------------------------------------
# Vùng mặt đất camera nhìn thấy (footprint)
# ---------------------------------------------------------------------------------------
def _clip_convex(subject: np.ndarray, clip_ccw: np.ndarray) -> np.ndarray:
    """Sutherland-Hodgman: cắt đa giác lồi `subject` (N,2) bằng đa giác lồi `clip_ccw` (M,2, ngược chiều kim đồng hồ)."""
    out = [tuple(p) for p in subject]
    m = len(clip_ccw)
    for i in range(m):
        a, b = clip_ccw[i], clip_ccw[(i + 1) % m]
        ex, ey = b[0] - a[0], b[1] - a[1]

        def side(p):  # > 0: nằm bên trái cạnh (phía trong khi clip ngược chiều kim đồng hồ)
            return ex * (p[1] - a[1]) - ey * (p[0] - a[0])

        inp, out = out, []
        if not inp:
            break
        for j in range(len(inp)):
            cur, nxt = inp[j], inp[(j + 1) % len(inp)]
            sc, sn = side(cur), side(nxt)
            if sc >= 0:
                out.append(cur)
            if (sc >= 0) != (sn >= 0):
                k = sc / (sc - sn)
                out.append((cur[0] + k * (nxt[0] - cur[0]), cur[1] + k * (nxt[1] - cur[1])))
    return np.array(out, dtype=np.float64).reshape(-1, 2)


def ground_footprint_polygon(
    calib: dict,
    image_size: Tuple[int, int],
    max_range_m: float,
    n_arc: int = 72,
) -> np.ndarray:
    """
    Vùng mặt đất (z=0) mà camera nhìn thấy, GIỚI HẠN trong bán kính max_range_m quanh chân camera
    (hình chiếu thẳng đứng của tâm camera xuống đất). Trả (N,2) mét trong HỆ MARKER (x, y) - chưa xoay
    azimuth, dùng marker_xy_to_enu để đổi sang Đông/Bắc; ngược chiều kim đồng hồ; đa giác lồi nên luôn
    đơn (không tự cắt). Mảng rỗng (0,2) nếu camera không nhìn thấy mặt đất.

    Cách chọn (viết rõ theo yêu cầu):
      1) Khung ảnh là hình chữ nhật [-0.5, w-0.5] x [-0.5, h-0.5] pixel. Độ cao "tia" ở pixel (u,v) tính
         bằng thành phần z hệ marker của tia: g(u,v) = R[:,2] . (x, y, 1) với x=(u-cx)/fx, y=(v-cy)/fy -
         tuyến tính theo (u,v). Phần ảnh nằm DƯỚI đường chân trời là g < 0. Cắt chữ nhật theo nửa mặt
         phẳng g <= 0 (Sutherland-Hodgman) -> đa giác lồi trong ảnh; đỉnh nằm trên đường chân trời (g ~ 0)
         là điểm ở vô cực theo hướng ngang của tia.
      2) Đổi từng đỉnh sang mặt đất: tia hướng xuống (g < 0) -> giao mặt đất. Phép chiếu phối cảnh giữ
         đường thẳng nên cạnh thẳng trong ảnh vẫn là cạnh thẳng trên đất, không cần chia nhỏ cạnh;
         đỉnh đường chân trời (hoặc xa hơn 100*max_range_m) thay bằng điểm cách chân camera 100*max_range_m
         theo hướng ngang của tia đó -> vùng lồi (hình thang / quạt mở rộng phía trước).
      3) Cắt vùng lồi này bằng hình tròn bán kính max_range_m quanh chân camera (đa giác đều n_arc cạnh,
         đỉnh nằm trên đường tròn). Điểm xa hơn max_range_m do đó được thay bằng điểm trên chính hướng
         đó ở khoảng cách max_range_m (cung tròn phía xa) mà không tạo cạnh chồng nhau.
    """
    if not max_range_m > 0:
        raise ValueError(f"max_range_m phải > 0, nhận {max_range_m!r}")
    w, h = int(image_size[0]), int(image_size[1])
    cm = _scaled_camera_matrix(calib, (w, h))
    R = np.array(calib["R"], dtype=np.float64)
    t = np.array(calib["t"], dtype=np.float64).reshape(3)
    C = camera_origin_in_marker_frame(R, t)
    if C[2] <= 0:
        return np.zeros((0, 2))
    fx, fy, cx, cy = cm[0, 0], cm[1, 1], cm[0, 2], cm[1, 2]

    def height_z(u, v):  # thành phần z (chưa chuẩn hoá) của tia trong hệ marker
        return R[0, 2] * (u - cx) / fx + R[1, 2] * (v - cy) / fy + R[2, 2]

    rect = [(-0.5, -0.5), (w - 0.5, -0.5), (w - 0.5, h - 0.5), (-0.5, h - 0.5)]
    poly = []
    for i in range(4):  # cắt theo g <= 0
        cur, nxt = rect[i], rect[(i + 1) % 4]
        gc, gn = height_z(*cur), height_z(*nxt)
        if gc <= 0:
            poly.append((cur, gc))
        if (gc <= 0) != (gn <= 0):
            k = gc / (gc - gn)
            poly.append(((cur[0] + k * (nxt[0] - cur[0]), cur[1] + k * (nxt[1] - cur[1])), 0.0))
    if len(poly) < 3:
        return np.zeros((0, 2))

    far = 100.0 * float(max_range_m)
    pts = []
    for (u, v), g in poly:
        d = R.T @ np.array([(u - cx) / fx, (v - cy) / fy, 1.0])
        dh = float(np.hypot(d[0], d[1]))
        if dh < 1e-12:  # nhìn thẳng xuống nhưng g ~ 0: không xảy ra; bỏ đỉnh
            continue
        p = None
        if d[2] < -1e-12:
            s = -C[2] / d[2]
            if s * dh <= far:
                p = (C[0] + s * d[0], C[1] + s * d[1])
        if p is None:  # chân trời / quá xa: đặt ở khoảng cách `far` theo hướng ngang của tia
            p = (C[0] + far * d[0] / dh, C[1] + far * d[1] / dh)
        pts.append(p)
    if len(pts) < 3:
        return np.zeros((0, 2))
    region = np.array(pts, dtype=np.float64)
    if _ring_area(region) < 0:
        region = region[::-1]

    ang = np.linspace(0.0, 2.0 * math.pi, n_arc, endpoint=False)
    disc = np.stack([C[0] + max_range_m * np.cos(ang), C[1] + max_range_m * np.sin(ang)], axis=1)
    out = _clip_convex(region, disc)
    if len(out) < 3 or abs(_ring_area(out)) < 1e-9:
        return np.zeros((0, 2))
    return out
