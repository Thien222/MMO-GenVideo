"""Long tieng AI bang edge-tts (mien phi, khong can key, khong can GPU)."""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

from .common import load_config


async def _synthesize(text: str, out_path: Path, voice: str, rate: str, pitch: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(out_path))


def generate_voice(text: str, out_path: Path, voice_cfg: dict | None = None) -> Path:
    """Tao file mp3 giong noi tu doan loi thoai.

    voice_cfg: neu truyen vao se thay cho config['voice'] (vd giong rieng cho story).
    """
    cfg = voice_cfg if voice_cfg is not None else load_config()["voice"]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(
        _synthesize(
            text,
            out_path,
            voice=cfg.get("name", "en-US-AriaNeural"),
            rate=cfg.get("rate", "+0%"),
            pitch=cfg.get("pitch", "+0Hz"),
        )
    )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("edge-tts khong tao duoc file giong noi (kiem tra ket noi mang).")
    return out_path


if __name__ == "__main__":
    p = generate_voice("Hello world. This is a test of the voice engine.", Path("output/_voice_test.mp3"))
    print("Da tao:", p)
