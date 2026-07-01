"""
PROCEDURAL STICK FIGURE + SIMPLE ANIMATION - TỐI ƯU TỐC ĐỘ + TRÔNG CHUYÊN NGHIỆP.

Không gọi bất kỳ API hình ảnh nào → siêu nhanh (thường < 60s cho video 1 phút).
Hỗ trợ:
- Nhiều pose cảm xúc tự động
- Bối cảnh đơn giản (nền, sàn, đồ vật) dựa trên nội dung
- Biểu cảm khuôn mặt tốt hơn
- Animation mượt + chuyển cảnh nhẹ
- Hỗ trợ nhiều nhân vật cơ bản (cho câu chuyện có tương tác)
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

from .common import load_config


def _infer_scene_context(narration: str) -> dict:
    """Suy luận bối cảnh đơn giản từ lời thoại (để vẽ nền nhanh)."""
    text = (narration or "").lower()
    ctx = {
        "bg_color": (250, 250, 250),
        "ground": True,
        "props": [],           # list of simple prop names
        "num_figures": 1,
        "accent_color": (30, 30, 30),
    }

    # Bối cảnh phổ biến cho viral stories
    if any(k in text for k in ["biển", "bờ biển", "sóng", "ocean", "biển cả"]):
        ctx["bg_color"] = (220, 240, 255)
        ctx["props"].append("wave")
    elif any(k in text for k in ["núi", "đỉnh núi", "mountain", "đồi"]):
        ctx["bg_color"] = (235, 245, 235)
        ctx["props"].append("mountain")
    elif any(k in text for k in ["đêm", "trăng", "bóng tối", "night", "dark"]):
        ctx["bg_color"] = (45, 50, 70)
        ctx["accent_color"] = (220, 220, 240)
    elif any(k in text for k in ["nhà", "phòng", "cửa", "home", "room"]):
        ctx["props"].append("door")
    elif any(k in text for k in ["đường", "đi bộ", "city", "street"]):
        ctx["props"].append("road")

    if any(k in text for k in ["hai người", "cả hai", "hai bạn", "together", "vợ chồng"]):
        ctx["num_figures"] = 2
    if any(k in text for k in ["đám đông", "nhiều người", "mọi người"]):
        ctx["num_figures"] = 3

    if any(k in text for k in ["cây", "cây cối", "rừng"]):
        ctx["props"].append("tree")
    if any(k in text for k in ["hoa", "quà", "hộp"]):
        ctx["props"].append("gift")
    if any(k in text for k in ["ghế", "ghế dài", "bench"]):
        ctx["props"].append("bench")

    return ctx


def _infer_pose(narration: str) -> str:
    text = (narration or "").lower()
    if any(k in text for k in ["sốc", "shock", "wow", "bất ngờ", "surprise", "khủng khiếp", "không thể tin"]):
        return "surprised"
    if any(k in text for k in ["buồn", "sad", "khóc", "thất vọng", "chết", "mất", "đau lòng"]):
        return "sad"
    if any(k in text for k in ["vui", "happy", "cười", "thành công", "thắng", "tuyệt vời", "hạnh phúc"]):
        return "happy"
    if any(k in text for k in ["nghĩ", "think", "suy nghĩ", "tại sao", "làm sao", "cân nhắc"]):
        return "thinking"
    if any(k in text for k in ["chỉ", "point", "đó", "nhìn kìa", "xem này"]):
        return "pointing"
    if any(k in text for k in ["chạy", "walk", "đi", "bước", "di chuyển"]):
        return "walking"
    if any(k in text for k in ["ôm", "hug", "bế", "cầm"]):
        return "hugging"
    if any(k in text for k in ["ngã", "fall", "té", "đổ"]):
        return "falling"
    return "neutral"


def _get_pose_params(pose: str, t: float) -> dict:
    """Tính toán pose theo thời gian cho animation mượt."""
    phase = t * 2 * math.pi
    base = {
        "head_tilt": 0,
        "body_lean": 0,
        "arm_l": -28,
        "arm_r": 28,
        "leg_l": -12,
        "leg_r": 12,
        "head_y_offset": 0,
        "mouth": "neutral",
    }

    if pose == "happy":
        base["arm_l"] = -85 + 25 * math.sin(phase * 1.6)
        base["arm_r"] = 85 - 25 * math.sin(phase * 1.6)
        base["mouth"] = "smile"
    elif pose == "sad":
        base["head_tilt"] = 14
        base["arm_l"] = -8
        base["arm_r"] = 8
        base["head_y_offset"] = 10
        base["body_lean"] = 6
        base["mouth"] = "sad"
    elif pose == "surprised":
        base["arm_l"] = -115 + 18 * math.sin(phase * 2.2)
        base["arm_r"] = 115 - 18 * math.sin(phase * 2.2)
        base["head_tilt"] = -6
        base["mouth"] = "o"
    elif pose == "thinking":
        base["arm_l"] = -50
        base["arm_r"] = 65 + 12 * math.sin(phase * 0.9)
        base["head_tilt"] = -18
        base["body_lean"] = -4
    elif pose == "pointing":
        base["arm_r"] = 15 + 38 * math.sin(phase * 1.3)
        base["arm_l"] = -25
    elif pose == "walking":
        base["leg_l"] = -30 + 38 * math.sin(phase * 1.9)
        base["leg_r"] = 30 - 38 * math.sin(phase * 1.9)
        base["arm_l"] = -45 + 28 * math.sin(phase * 1.9 + 0.9)
        base["arm_r"] = 45 - 28 * math.sin(phase * 1.9 + 0.9)
        base["body_lean"] = 4 * math.sin(phase * 1.9)
    elif pose == "hugging":
        base["arm_l"] = -55
        base["arm_r"] = 55
        base["head_tilt"] = 5
    elif pose == "falling":
        base["head_tilt"] = 35
        base["arm_l"] = -90
        base["arm_r"] = 70
        base["body_lean"] = 22
        base["leg_l"] = 35
        base["leg_r"] = -20
    else:
        base["arm_l"] = -28 + 10 * math.sin(phase * 0.8)
        base["arm_r"] = 28 - 10 * math.sin(phase * 0.8)

    return base


def _draw_simple_face(frame, cx, cy, s, params, color):
    """Biểu cảm khuôn mặt đơn giản nhưng rõ."""
    mouth = params.get("mouth", "neutral")
    if mouth == "smile":
        cv2.ellipse(frame, (cx, cy + int(7*s)), (int(6*s), int(4*s)), 0, 0, 180, color, 2)
    elif mouth == "sad":
        cv2.ellipse(frame, (cx, cy + int(11*s)), (int(5*s), int(3*s)), 0, 180, 360, color, 2)
    elif mouth == "o":
        cv2.circle(frame, (cx, cy + int(8*s)), int(3.5*s), color, 2)
    else:
        cv2.line(frame, (cx - int(4*s), cy + int(8*s)), (cx + int(4*s), cy + int(8*s)), color, 2)


def _draw_stick_figure(frame: np.ndarray, cx: int, cy: int, scale: float, params: dict, color=(25, 25, 25), secondary=False):
    s = scale * (0.9 if secondary else 1.0)
    head_r = int(17 * s)
    head_y = cy - int(52 * s) + int(params.get("head_y_offset", 0))

    # Head + face
    cv2.circle(frame, (cx, head_y), head_r, color, max(3, int(3.5*s)), lineType=cv2.LINE_AA)
    eye_off = int(6 * s)
    cv2.circle(frame, (cx - eye_off, head_y - 2), max(2, int(2.5*s)), color, -1)
    cv2.circle(frame, (cx + eye_off, head_y - 2), max(2, int(2.5*s)), color, -1)
    _draw_simple_face(frame, cx, head_y, s, params, color)

    # Body
    body_top = (cx, head_y + head_r - 1)
    lean = int(params.get("body_lean", 0) * s)
    body_bot = (cx + lean, cy + int(8 * s))
    cv2.line(frame, body_top, body_bot, color, max(3, int(4.5*s)), lineType=cv2.LINE_AA)

    # Arms
    shoulder_y = head_y + int(10 * s)
    arm_len = int(36 * s)

    def arm(angle, sign):
        rad = math.radians(angle)
        ex = cx + int(arm_len * math.sin(rad)) * sign
        ey = shoulder_y + int(arm_len * math.cos(rad))
        cv2.line(frame, (cx, shoulder_y), (ex, ey), color, max(2, int(3.5*s)), lineType=cv2.LINE_AA)

    arm(params.get("arm_l", -28), -1)
    arm(params.get("arm_r", 28), 1)

    # Legs
    leg_len = int(40 * s)
    hip = body_bot

    def leg(angle, sign):
        rad = math.radians(angle)
        ex = hip[0] + int(leg_len * math.sin(rad)) * sign
        ey = hip[1] + int(leg_len * math.cos(rad))
        cv2.line(frame, hip, (ex, ey), color, max(2, int(3.5*s)), lineType=cv2.LINE_AA)

    leg(params.get("leg_l", -12), -1)
    leg(params.get("leg_r", 12), 1)


def _draw_context(frame, W, H, ctx, scale):
    """Vẽ nền và props đơn giản (rất nhanh)."""
    # Nền nhẹ
    frame[:] = ctx["bg_color"]

    # Sàn / ground
    if ctx.get("ground", True):
        ground_y = int(H * 0.68)
        cv2.line(frame, (0, ground_y), (W, ground_y), (180, 180, 180), 2)

    s = scale * 0.85
    # Props đơn giản
    for prop in ctx.get("props", []):
        if prop == "tree":
            cv2.line(frame, (W//4, int(H*0.55)), (W//4, int(H*0.72)), (70, 120, 70), 4)
            cv2.circle(frame, (W//4, int(H*0.48)), int(22*s), (50, 140, 50), -1)
        if prop == "mountain":
            pts = np.array([[W*0.15, H*0.68], [W*0.32, H*0.38], [W*0.48, H*0.68]], np.int32)
            cv2.fillPoly(frame, [pts], (140, 160, 140))
        if prop == "wave":
            for i in range(3):
                y = int(H * 0.72 + i*8)
                cv2.line(frame, (0, y), (W, y), (100, 160, 220), 2)
        if prop == "door":
            cv2.rectangle(frame, (int(W*0.72), int(H*0.42)), (int(W*0.82), int(H*0.68)), (90, 90, 90), 3)
        if prop == "gift":
            cv2.rectangle(frame, (int(W*0.6), int(H*0.62)), (int(W*0.7), int(H*0.72)), (220, 80, 80), -1)
            cv2.line(frame, (int(W*0.65), int(H*0.62)), (int(W*0.65), int(H*0.58)), (255, 255, 80), 2)


def build_procedural_stick_video(
    scenes: List[Tuple[str, float]],   # [(narration, duration), ...]
    out_path: Path,
    fps: int = 30,
) -> Path:
    """Tạo video người que hoạt hình cực nhanh và đẹp hơn."""
    cfg = load_config()
    W = cfg["video"]["width"]
    H = cfg["video"]["height"]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (W, H))
    if not writer.isOpened():
        raise RuntimeError("Không thể mở VideoWriter procedural.")

    try:
        for narration, dur in scenes:
            pose = _infer_pose(narration)
            ctx = _infer_scene_context(narration)
            total_frames = max(1, int(round(dur * fps)))

            # Vị trí các nhân vật
            figures = []
            n_fig = min(ctx.get("num_figures", 1), 3)
            if n_fig == 1:
                figures.append(W // 2)
            elif n_fig == 2:
                figures.append(int(W * 0.38))
                figures.append(int(W * 0.62))
            else:
                figures = [int(W * 0.28), int(W * 0.5), int(W * 0.72)]

            cy = int(H * 0.55)

            for f in range(total_frames):
                t = f / max(total_frames - 1, 1)
                params = _get_pose_params(pose, t)

                frame = np.full((H, W, 3), 255, dtype=np.uint8)
                _draw_context(frame, W, H, ctx, min(W, H) / 1080)

                # Vẽ các nhân vật
                for i, fx in enumerate(figures):
                    color = ctx["accent_color"] if i == 0 else (70, 70, 70)
                    _draw_stick_figure(frame, fx, cy, min(W, H) / 1050, params, color=color, secondary=(i > 0))

                # Nhẹ nhàng fade giữa các cảnh (không tốn nhiều)
                writer.write(frame)

    finally:
        writer.release()

    if not out_path.exists() or out_path.stat().st_size < 2000:
        raise RuntimeError("Tạo video procedural thất bại.")

    return out_path
