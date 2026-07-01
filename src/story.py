"""Sinh kich ban video WHITEBOARD / NGUOI QUE ke chuyen (facts/mystery/life lesson) bang Groq.

Ho tro: Tieng Anh va Tieng Viet.
Tao kich ban kich tinh, co hook manh, twist, diem nhan viral de de viral.

Tra ve dict:
{
  "title": str,
  "hook": str,                 # cau mo dau giat gan (3s dau rat quan trong)
  "scenes": [
     {"narration": str, "image_prompt": str},   # loi ke + mo ta hinh (stick / cartoon style)
     ...
  ],
  "cta": str
}
"""
from __future__ import annotations

import json
import re

import requests

from .common import get_env, load_config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _get_style_hint(visual_style: str) -> str:
    """Tra ve huong dan style hinh anh cho image_prompt."""
    hints = {
        "stick_figure": "minimalist black stick figure on plain white, simple expressive stickman, clean bold thin lines, no shading, very simple cartoon, high contrast, centered composition",
        "whiteboard": "black and white line art, clean bold thin outlines, high contrast, simple doodle illustration, plain white background, no shading",
        "cartoon_simple": "simple cute cartoon illustration, flat colors with bold black outlines, expressive characters, clean minimal style, white background, friendly and clear",
        "doodle": "hand-drawn doodle style, loose expressive lines, sketchy but clear, black on off-white paper texture, fun and relatable",
        "dramatic_sketch": "dramatic high-contrast sketch, bold expressive lines, emotional poses, cinematic framing, strong light/shadow suggestion with linework only",
    }
    return hints.get(visual_style, hints["whiteboard"])


# ==================== ENGLISH PROMPTS (VIRAL + DRAMATIC) ====================

EN_FACTS_SYSTEM = (
    "You are a world-class viral short-form storyteller specializing in faceless animation "
    "(stick figure / simple cartoon / whiteboard). You craft HIGHLY engaging, dramatic, curiosity-driven "
    "stories optimized for Shorts, TikTok, Reels. Every line must hook attention and build emotion."
)

EN_FACTS_USER = """Topic: "{topic}"
Language: English
Visual style hint: {style_hint}
Target scenes: exactly {num_scenes}
Target spoken length: ~{target_seconds}s (keep narration tight)

Create a VIRAL-WORTHY script with strong dramatic structure:
- title: Clickbait-y but truthful YouTube/Shorts title (max 70 chars)
- hook: EXTREMELY powerful first line. Must stop the scroll (under 14 words). Use pattern like "Most people don't know...", "This will blow your mind...", "You will never guess what happened..."
- scenes: EXACTLY {num_scenes} scenes with escalating tension.
  Each scene: 
    - "narration": 1-3 short vivid spoken sentences. Use pauses for drama. Build suspense, emotion, twist.
    - "image_prompt": very concrete, simple visual description (1 main subject). Add " {style_hint} "
- cta: strong share/engage CTA.

Rules for viral:
- Hook in first 3 seconds
- One big twist or revelation
- Emotional peak near end
- Memorable one-liner lesson or shock
Total words ~ 140-230.

Return ONLY clean JSON: {{"title":"..","hook":"..","scenes":[{{"narration":"..","image_prompt":".."}}],"cta":".."}}

"""

EN_LESSON_SYSTEM = (
    "You are an elite emotional storyteller for faceless animated videos. You create short, "
    "powerful human stories that feel cinematic and end with a profound, memorable life lesson. "
    "Use stick-figure or simple animation style. Make viewers FEEL and want to share."
)

EN_LESSON_USER = """Topic or theme: "{topic}"
Language: English
Visual style hint: {style_hint}
Scenes: exactly {num_scenes}
Approx duration: ~{target_seconds}s

Write ONE continuous dramatic short story with perfect arc:
setup (ordinary world) -> rising conflict/struggle -> emotional low or crisis -> turning point -> powerful resolution + life lesson.

- title: emotional + curiosity YouTube title
- hook: gripping 1-liner (shock, question or strong image) <=14 words
- scenes: each has:
    "narration": natural spoken, emotional, use character names or "he/she". Show don't tell. Short sentences.
    "image_prompt": simple, clear visual (person/action/emotion). {style_hint}
- cta: warm powerful CTA

Place the clear memorable lesson in scene n-1.
Make it highly re-sharable.

Return ONLY valid JSON.
"""

# ==================== VIETNAMESE PROMPTS (KICH TINH + VIRAL) ====================

VN_FACTS_SYSTEM = (
    "Bạn là chuyên gia viết kịch bản video ngắn viral dạng hoạt hình người que / AI animation / "
    "whiteboard. Viết bằng tiếng Việt tự nhiên, dễ nghe, kịch tính cao, dùng để tạo video YouTube Shorts / TikTok / Reels. "
    "Mỗi câu phải gây tò mò, cảm xúc mạnh."
)

VN_FACTS_USER = """Chủ đề: "{topic}"
Ngôn ngữ: Tiếng Việt
Gợi ý phong cách hình: {style_hint}
Số cảnh: chính xác {num_scenes}
Thời lượng thoại: khoảng {target_seconds} giây

Viết kịch bản CÓ ĐIỂM NHẤN VIRAL + KỊCH TÍNH:
- title: Tiêu đề hấp dẫn kiểu YouTube Shorts (dễ click, chân thực)
- hook: Câu mở đầu cực mạnh, dừng scroll ngay (dưới 14 từ). Dùng kiểu: "Hầu hết mọi người không biết...", "Điều này sẽ làm bạn sốc...", "Bạn sẽ không đoán được..."
- scenes: ĐÚNG {num_scenes} cảnh, leo thang kịch tính.
  Mỗi cảnh:
    - "narration": 1-3 câu thoại nói tự nhiên, ngắn gọn, giàu hình ảnh. Xây dựng suspense, cảm xúc, twist.
    - "image_prompt": Mô tả hình ảnh ĐƠN GIẢN, cụ thể (1 đối tượng chính). Kết hợp {style_hint}
- cta: Lời kêu gọi chia sẻ mạnh mẽ.

Quy tắc viral:
- Hook cực mạnh 3 giây đầu
- Có 1 twist hoặc tiết lộ lớn
- Đỉnh cảm xúc gần cuối
- Câu nói ấn tượng dễ nhớ
Tổng ~140-230 từ.

CHỈ TRẢ VỀ JSON hợp lệ: {{"title":"..","hook":"..","scenes":[{{"narration":"..","image_prompt":".."}}],"cta":".."}}
"""

VN_LESSON_SYSTEM = (
    "Bạn là bậc thầy kể chuyện cảm xúc bằng hoạt hình đơn giản (người que, cartoon AI). "
    "Tạo câu chuyện ngắn, nhân văn, kịch tính, kết thúc bằng bài học cuộc sống sâu sắc, dễ lan tỏa. "
    "Dùng tiếng Việt tự nhiên, gần gũi."
)

VN_LESSON_USER = """Chủ đề / thông điệp: "{topic}"
Ngôn ngữ: Tiếng Việt
Phong cách hình: {style_hint}
Số cảnh: {num_scenes}
Thời lượng ~{target_seconds}s

Viết MỘT câu chuyện liên tục có cấu trúc hoàn hảo:
khởi đầu -> xung đột leo thang -> khủng hoảng cảm xúc -> bước ngoặt -> kết thúc + bài học mạnh.

- title: Tiêu đề giàu cảm xúc + tò mò
- hook: Câu mở đầu cực hút (sốc / câu hỏi / hình ảnh mạnh) <=14 từ
- scenes: 
    narration: thoại tự nhiên, giàu cảm xúc, dùng nhân vật. Câu ngắn. Hiện cảm xúc qua hành động.
    image_prompt: hình đơn giản, rõ ràng, bám {style_hint}
- cta: CTA ấm áp, truyền cảm hứng, mời chia sẻ

Bài học rõ ràng, dễ nhớ đặt ở cảnh áp chót.

CHỈ TRẢ JSON.
"""

# Mapping
_PROMPTS = {
    "en": {
        "facts": (EN_FACTS_SYSTEM, EN_FACTS_USER),
        "life_lesson": (EN_LESSON_SYSTEM, EN_LESSON_USER),
    },
    "vi": {
        "facts": (VN_FACTS_SYSTEM, VN_FACTS_USER),
        "life_lesson": (VN_LESSON_SYSTEM, VN_LESSON_USER),
    },
}

# Good default voices per language
DEFAULT_VOICES = {
    "en": "en-US-AndrewMultilingualNeural",
    "vi": "vi-VN-HoaiMyNeural",
}


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Khong tim thay JSON trong phan hoi cua Groq:\n{text}")
    return json.loads(match.group(0))


def generate_story(
    topic: str,
    lang: str = "en",
    mode: str | None = None,
    num_scenes: int | None = None,
    target_seconds: int | None = None,
    visual_style: str = "whiteboard",
    temperature: float | None = None,
) -> dict:
    """
    Sinh kich ban ke chuyen.
    lang: 'en' | 'vi'
    mode: 'life_lesson' | 'facts'
    visual_style: 'stick_figure' | 'whiteboard' | 'cartoon_simple' | 'doodle' | 'dramatic_sketch'
    """
    cfg = load_config()["story"]
    api_key = get_env("GROQ_API_KEY")

    lang = lang if lang in ("en", "vi") else "en"
    mode = mode or cfg.get("mode", "life_lesson")
    num_scenes = num_scenes or cfg.get("num_scenes", 7)
    target_seconds = target_seconds or 75
    temp = temperature if temperature is not None else cfg.get("temperature", 0.9)

    system_prompt, user_template = _PROMPTS[lang].get(mode, _PROMPTS[lang]["life_lesson"])
    style_hint = _get_style_hint(visual_style)

    payload = {
        "model": cfg.get("model", "llama-3.3-70b-versatile"),
        "temperature": temp,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_template.format(
                    topic=topic,
                    num_scenes=num_scenes,
                    target_seconds=target_seconds,
                    style_hint=style_hint,
                    spc=cfg.get("sentences_per_scene", 2),
                ),
            },
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq loi {resp.status_code}: {resp.text}")

    data = _extract_json(resp.json()["choices"][0]["message"]["content"])

    if not data.get("scenes"):
        raise ValueError("Kich ban thieu 'scenes'.")
    data.setdefault("title", topic)
    data.setdefault("hook", "")
    data.setdefault("cta", "Like và chia sẻ nếu bạn thấy hữu ích!" if lang == "vi" else "Like and share if this inspired you!")

    def _end_sentence(s: str) -> str:
        s = s.strip()
        return s if (not s or s[-1] in ".!?") else s + "."

    # Dua hook vao dau, cta vao cuoi (dam bao doc tu nhien)
    if data["hook"]:
        data["scenes"][0]["narration"] = (
            _end_sentence(data["hook"]) + " " + data["scenes"][0]["narration"].strip()
        )
    data["scenes"][-1]["narration"] = (
        _end_sentence(data["scenes"][-1]["narration"]) + " " + data["cta"].strip()
    )

    # Luu thong tin bo sung de web UI dung lai
    data["_meta"] = {
        "lang": lang,
        "mode": mode,
        "visual_style": visual_style,
        "num_scenes": len(data["scenes"]),
    }
    return data


if __name__ == "__main__":
    import sys

    t = sys.argv[1] if len(sys.argv) > 1 else "bí mật tam giác Bermuda"
    print(json.dumps(generate_story(t, lang="vi", visual_style="stick_figure"), indent=2, ensure_ascii=False))
