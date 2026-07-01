"""Hieu ung WHITEBOARD: ve dan net len khung trang theo thu tu doc, co cay but di chuyen.

Ghep nhieu canh (moi canh 1 hinh line-art + thoi luong) thanh 1 video im lang (chua co tieng).
Chay hoan toan tren CPU bang OpenCV + NumPy.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .common import load_config


def _prepare(img_path: Path, W: int, H: int, margin: int, threshold: int):
    """Dat hinh vao giua khung trang WxH; tra ve (target_image, toa_do_net_theo_thu_tu)."""
    img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Khong doc duoc hinh: {img_path}")

    ih, iw = img.shape[:2]
    max_w, max_h = W - 2 * margin, H - 2 * margin
    scale = min(max_w / iw, max_h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)

    target = np.full((H, W, 3), 255, np.uint8)
    x0, y0 = (W - nw) // 2, (H - nh) // 2
    target[y0 : y0 + nh, x0 : x0 + nw] = resized

    gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(gray < threshold)
    coords = np.column_stack((ys, xs))
    # Thu tu doc: tu tren xuong, trai sang phai (tao cam giac dang ve).
    order = np.lexsort((xs, ys))
    return target, coords[order]


def _draw_pen(frame: np.ndarray, x: int, y: int) -> None:
    """Ve cay but tro vao diem (x, y)."""
    cv2.line(frame, (x + 74, y + 100), (x + 9, y + 12), (60, 60, 60), 12, cv2.LINE_AA)
    cv2.line(frame, (x + 9, y + 12), (x, y), (20, 20, 20), 7, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 4, (0, 0, 0), -1, cv2.LINE_AA)


def _render_scene(writer, target, coords, dur, fps, draw_ratio, pen) -> None:
    total = max(1, int(round(dur * fps)))
    draw_n = max(1, int(total * draw_ratio))
    hold_n = max(0, total - draw_n)

    canvas = np.full_like(target, 255)
    n = len(coords)
    if n == 0:  # hinh trang -> chi giu khung trang
        for _ in range(total):
            writer.write(canvas)
        return

    prev = 0
    for f in range(draw_n):
        idx = int(n * (f + 1) / draw_n)
        if idx > prev:
            pts = coords[prev:idx]
            canvas[pts[:, 0], pts[:, 1]] = target[pts[:, 0], pts[:, 1]]
            prev = idx
        if pen and prev > 0:
            frame = canvas.copy()
            y, x = coords[prev - 1]
            _draw_pen(frame, int(x), int(y))
            writer.write(frame)
        else:
            writer.write(canvas)

    # Bao dam ve day du roi giu hinh.
    canvas[coords[:, 0], coords[:, 1]] = target[coords[:, 0], coords[:, 1]]
    for _ in range(hold_n):
        writer.write(canvas)


def build_whiteboard_video(scenes: list[tuple[Path, float]], out_path: Path) -> Path:
    """scenes: danh sach (duong_dan_hinh, thoi_luong_giay). Tra ve video im lang .mp4."""
    cfg = load_config()
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    wb = cfg["whiteboard"]
    fps = wb["fps"]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (W, H))
    if not writer.isOpened():
        raise RuntimeError("Khong mo duoc VideoWriter (kiem tra opencv).")

    try:
        for img_path, dur in scenes:
            target, coords = _prepare(
                Path(img_path), W, H, wb["margin"], wb["ink_threshold"]
            )
            _render_scene(writer, target, coords, dur, fps, wb["draw_ratio"], wb["pen"])
    finally:
        writer.release()

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("Khong tao duoc video whiteboard.")
    return out_path


if __name__ == "__main__":
    import sys

    img = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/_img_test.png")
    out = build_whiteboard_video([(img, 6.0)], Path("output/_wb_test.mp4"))
    print("Da tao:", out)
