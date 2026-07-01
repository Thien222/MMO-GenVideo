"""Tai hinh line-art tu Pollinations.ai (free, khong can API key).

Endpoint: https://image.pollinations.ai/prompt/{prompt}?width=&height=&seed=&model=&nologo=true
Luu y: tier anonymous gioi han ~1 request / 15s -> can nghi giua cac lan goi.
"""
from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import quote

import requests

from .common import get_env, load_config

BASE = "https://image.pollinations.ai/prompt/"


def _get_token() -> str:
    """Token Pollinations (tuy chon) - co thi tai anh nhanh hon va bo watermark."""
    token = get_env("POLLINATIONS_TOKEN", required=False)
    return "" if token.startswith("your_") else token


def _effective_delay(cfg: dict) -> float:
    """Thoi gian nghi giua cac lan goi: nhanh hon neu co token."""
    if _get_token():
        return cfg.get("request_delay_auth", 6)
    return cfg.get("request_delay", 16)


def fetch_line_art(scene_prompt: str, dest: Path, seed: int = 0, style_override: str | None = None) -> Path:
    """Tai 1 hinh theo style (ho tro stick figure, cartoon, line art...)."""
    cfg = load_config()["images"]
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    token = _get_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    base_style = style_override or cfg.get("style", "")
    full_prompt = f"{scene_prompt.strip().rstrip('.')}, {base_style}".strip(", ")
    url = BASE + quote(full_prompt, safe="")
    params = {
        "width": cfg["width"],
        "height": cfg["height"],
        "seed": seed,
        "model": cfg.get("model", "flux"),
        "nologo": "true",
        "safe": "true",
    }

    last_err = None
    for attempt in range(1, cfg.get("retries", 3) + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=cfg.get("timeout", 120))
            ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and ctype.startswith("image"):
                dest.write_bytes(r.content)
                if dest.stat().st_size > 0:
                    return dest
                last_err = "file rong"
            else:
                last_err = f"status {r.status_code}, type {ctype}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(_effective_delay(cfg))

    raise RuntimeError(f"Khong tai duoc hinh tu Pollinations sau nhieu lan thu: {last_err}")


def fetch_images(prompts: list[str], workdir: Path, style_override: str | None = None) -> list[Path]:
    """Tai hinh cho danh sach prompt (co nghi giua cac lan de tranh rate limit)."""
    cfg = load_config()["images"]
    workdir = Path(workdir)
    img_dir = workdir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    delay = _effective_delay(cfg)
    paths: list[Path] = []
    for i, prompt in enumerate(prompts):
        dest = img_dir / f"scene_{i:02d}.png"
        print(f"      - Hinh canh {i + 1}/{len(prompts)}...")
        paths.append(fetch_line_art(prompt, dest, seed=1000 + i, style_override=style_override))
        if i < len(prompts) - 1:
            time.sleep(delay)
    return paths


if __name__ == "__main__":
    p = fetch_line_art("a lighthouse on a cliff at night", Path("output/_img_test.png"))
    print("Da tai:", p)
