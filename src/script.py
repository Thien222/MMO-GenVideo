"""Sinh kich ban video bang Groq API (Llama 3.3 70B).

Tra ve dict:
{
  "hook": str,
  "points": [{"phrase": str, "example": str}, ...],
  "cta": str,
  "visual_keywords": [str, ...],
  "narration": str   # loi thoai day du de long tieng
}
"""
from __future__ import annotations

import json
import re

import requests

from .common import get_env, load_config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a viral short-form scriptwriter for a faceless English-learning channel "
    "targeting non-native speakers worldwide. You write punchy, high-retention scripts."
)

USER_PROMPT_TEMPLATE = """Write a {max_words}-word-max vertical short video script about: "{topic}"

Rules:
- HOOK (first line): a bold, curiosity-driven sentence that makes a learner stop scrolling. Max 12 words.
- Teach EXACTLY 3 practical points. Each point: a short English "phrase" plus a natural one-line "example" sentence using it.
- Use simple words (CEFR B1). Conversational, energetic, friendly tone.
- CTA (last line): a short call to action like "Follow for daily English."
- Also give 3 to 5 "visual_keywords": simple, concrete English nouns good for searching stock video (e.g. "city street", "coffee shop", "happy friends"). No abstract words.

Return ONLY valid JSON, no markdown, with this exact shape:
{{
  "hook": "...",
  "points": [
    {{"phrase": "...", "example": "..."}},
    {{"phrase": "...", "example": "..."}},
    {{"phrase": "...", "example": "..."}}
  ],
  "cta": "...",
  "visual_keywords": ["...", "...", "..."]
}}"""


def _extract_json(text: str) -> dict:
    """Lay khoi JSON dau tien trong chuoi (phong khi model them text thua)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Khong tim thay JSON trong phan hoi cua Groq:\n{text}")
    return json.loads(match.group(0))


def build_narration(data: dict) -> str:
    """Ghep cac phan thanh 1 doan loi thoai mach lac de long tieng."""
    parts = [data["hook"].strip()]
    for point in data["points"]:
        phrase = point["phrase"].strip().rstrip(".")
        example = point["example"].strip()
        parts.append(f"{phrase}. For example: {example}")
    parts.append(data["cta"].strip())
    # Noi bang khoang nghi nhe de giong doc tu nhien hon.
    return " ... ".join(parts)


def generate_script(topic: str) -> dict:
    """Goi Groq sinh kich ban cho 1 chu de."""
    cfg = load_config()
    api_key = get_env("GROQ_API_KEY")

    payload = {
        "model": cfg["llm"]["model"],
        "temperature": cfg["llm"].get("temperature", 0.8),
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    topic=topic, max_words=cfg["llm"].get("max_words", 90)
                ),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq loi {resp.status_code}: {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"]
    data = _extract_json(content)

    # Kiem tra toi thieu + bo sung mac dinh.
    data.setdefault("cta", "Follow for daily English.")
    data.setdefault("visual_keywords", [topic])
    if not data.get("points"):
        raise ValueError("Kich ban thieu 'points'.")

    data["narration"] = build_narration(data)
    return data


if __name__ == "__main__":
    import sys

    t = sys.argv[1] if len(sys.argv) > 1 else "3 English phrases natives use instead of very good"
    result = generate_script(t)
    print(json.dumps(result, indent=2, ensure_ascii=False))
