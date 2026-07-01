"""
Web Generation API - Core cho giao dien web.
Cho phep:
- Chon ngon ngu (vi/en), voice, khung hinh (aspect), thoi gian, style nguoi que / hoat hinh
- Tao kich ban co the chinh sua
- Render video day du (co nhac nen)
- Tra ve thong tin de hien thi tien do + ket qua

Su dung tu Streamlit hoac API.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .assemble import _duration, assemble_final, concat_audio_with_durations
from .captions import generate_captions
from .common import ROOT, load_config, slugify, workdir_for
from .images import fetch_images
from .procedural_stick import build_procedural_stick_video
from .story import generate_story, DEFAULT_VOICES
from .voice import generate_voice
from .whiteboard import build_whiteboard_video


ASPECTS = {
    "9:16": {"width": 1080, "height": 1920, "label": "Dọc (Shorts / TikTok / Reels)"},
    "16:9": {"width": 1920, "height": 1080, "label": "Ngang (YouTube)"},
    "1:1":  {"width": 1080, "height": 1080, "label": "Vuông (Instagram)"},
    "4:5":  {"width": 1080, "height": 1350, "label": "Dọc Feed (4:5)"},
}

VISUAL_STYLES = {
    "procedural_stick": "🚀 NGƯỜI QUE NHANH (khuyến nghị - siêu nhanh, không chờ API)",
    "stick_figure": "Người que (Pollinations - chất lượng cao hơn nhưng chậm)",
    "whiteboard": "Whiteboard line-art (Pollinations)",
    "cartoon_simple": "Hoạt hình đơn giản (Pollinations)",
    "doodle": "Doodle tay vẽ (Pollinations)",
    "dramatic_sketch": "Phác thảo kịch tính (Pollinations)",
}

FAST_VISUAL_STYLES = {"procedural_stick"}   # những style không cần gọi mạng hình ảnh

CONTENT_MODES = {
    "life_lesson": "Câu chuyện + Bài học cuộc sống (rất viral)",
    "facts": "Sự thật / Bí ẩn / Did-you-know",
}

DEFAULT_MUSIC_VOLUME = 0.12


@dataclass
class GenParams:
    topic: str
    lang: str = "vi"                    # 'vi' | 'en'
    aspect: str = "9:16"
    duration: int = 65                  # giay muc tieu (giảm để nhanh)
    visual_style: str = "procedural_stick"
    content_mode: str = "life_lesson"
    voice_name: str | None = None
    voice_rate: str = "+0%"
    voice_pitch: str = "+0Hz"
    use_music: bool = True
    music_volume: float = DEFAULT_MUSIC_VOLUME
    music_path: str | None = None       # duong dan tuy chon (upload)
    num_scenes: int | None = None
    dramatic: bool = True
    fast_mode: bool = True              # Bật chế độ nhanh: ít cảnh hơn, whisper tiny, skip một số bước
    skip_captions: bool = False         # Siêu nhanh: bỏ phụ đề karaoke (vẫn có giọng nói)
    polli_token: str | None = None      # Token Pollinations để tải hình nhanh hơn (khi dùng style không phải procedural)


def get_default_voice(lang: str) -> str:
    return DEFAULT_VOICES.get(lang, "en-US-AndrewMultilingualNeural")


def get_video_size(aspect: str) -> tuple[int, int]:
    info = ASPECTS.get(aspect, ASPECTS["9:16"])
    return info["width"], info["height"]


def estimate_scenes(duration: int, fast: bool = True) -> int:
    """Số cảnh tối ưu cho tốc độ."""
    base = 5 if fast else 6
    if duration <= 50:
        return 4 if fast else 5
    if duration <= 70:
        return base
    if duration <= 95:
        return 6 if fast else 7
    return 6 if fast else min(8, duration // 13)


class VideoGenerator:
    """Runner chinh, co the goi tu web UI voi progress callback."""

    def __init__(self, params: GenParams):
        self.p = params
        self.workdir: Path | None = None
        self.story: dict | None = None
        self.progress_steps: list[str] = []
        self._log: list[str] = []

    def log(self, msg: str):
        import time as _t
        ts = _t.strftime("%H:%M:%S")
        full = f"[{ts}] {msg}"
        print(full)
        self._log.append(full)

    def get_logs(self) -> list[str]:
        return self._log[:]

    def _apply_runtime_config(self):
        """Tam thoi cap nhat kich thuoc video tu aspect (patch config)."""
        # Because many modules read from load_config(), we patch in memory for this run.
        from .common import load_config as _orig_load
        # We cannot easily patch, instead we will monkey patch inside the generator
        # A cleaner way: edit the modules to accept size. For now we write a temp override.
        pass

    def generate_story_only(self) -> dict:
        """Chi tao kich ban (nhanh) - cho phep nguoi dung chinh sua."""
        p = self.p
        num_scenes = p.num_scenes or estimate_scenes(p.duration, fast=p.fast_mode)

        self.log(f"[1] Viet kich ban ({p.lang.upper()}, {p.content_mode}, style={p.visual_style})...")

        story = generate_story(
            topic=p.topic,
            lang=p.lang,
            mode=p.content_mode,
            num_scenes=num_scenes,
            target_seconds=p.duration,
            visual_style=p.visual_style,
            temperature=0.95 if p.dramatic else 0.8,
        )
        self.story = story
        self.log(f"    → Tiêu đề: {story.get('title')}")
        self.log(f"    → Hook: {story.get('hook')}")
        self.log(f"    → {len(story['scenes'])} cảnh")
        return story

    def full_generate(self, story_override: dict | None = None, progress_cb: Any = None) -> Path:
        """
        Chay day du tu kich ban (co the truyen override sau khi nguoi dung edit).
        Tra ve duong dan video.mp4
        """
        p = self.p
        cfg = load_config()

        # Set Pollinations token if provided (for faster image gen)
        if p.polli_token:
            os.environ["POLLINATIONS_TOKEN"] = p.polli_token.strip()

        # === APPLY ASPECT RATIO OVERRIDE (monkey patch load_config result) ===
        W, H = get_video_size(p.aspect)
        cfg["video"]["width"] = W
        cfg["video"]["height"] = H

        # Monkey patch load_config for the duration of this call
        import src.common as common_mod
        _orig_load = common_mod.load_config

        def _patched_load():
            c = _orig_load()
            c["video"]["width"] = W
            c["video"]["height"] = H
            return c

        common_mod.load_config = _patched_load
        # also keep local cfg in sync
        cfg = _patched_load()
        import time as _time
        start_total = _time.time()

        try:
            if story_override:
                self.story = story_override
            elif not self.story:
                self.generate_story_only()

            story = self.story
            scenes = story["scenes"]

            # Workdir
            prefix = "wb-" if p.lang == "en" else "vn-"
            self.workdir = workdir_for(prefix + p.topic)
            workdir = self.workdir

            # Neu da co video thi xoa hoac reuse? (cho web thi nen tao lai de test thay doi)
            out_existing = workdir / "video.mp4"
            if out_existing.exists():
                try:
                    out_existing.unlink()
                except Exception:
                    pass

            # Voice config
            voice_name = p.voice_name or get_default_voice(p.lang)
            voice_cfg = {
                "name": voice_name,
                "rate": p.voice_rate,
                "pitch": p.voice_pitch,
            }

            # 1. Voice per scene + durations (cố gắng song song để nhanh)
            self.log("[2] Tạo giọng nói từng cảnh (song song)...")
            import asyncio
            voices: list[Path] = []
            durations: list[float] = []
            tail = cfg["whiteboard"].get("scene_tail", 0.45)  # giảm tail để nhanh

            async def _gen_voice(i: int, text: str):
                vp = workdir / f"voice_{i:02d}.mp3"
                return generate_voice(text, vp, voice_cfg=voice_cfg)

            async def _gen_all_voices():
                tasks = [ _gen_voice(i, sc["narration"]) for i, sc in enumerate(scenes) ]
                return await asyncio.gather(*tasks)

            voice_paths = asyncio.run(_gen_all_voices())
            for i, vp in enumerate(voice_paths):
                voices.append(vp)
                d = _duration(vp) + tail
                durations.append(d)

            if progress_cb:
                progress_cb("voice", len(scenes), len(scenes))

            # 2 + 3. HÌNH ẢNH + HOẠT HÌNH (rẽ nhánh tốc độ)
            is_fast_stick = p.visual_style == "procedural_stick" or p.fast_mode

            if is_fast_stick:
                self.log("[3] Tạo hoạt hình NGƯỜI QUE THỦ CÔNG (siêu nhanh - không gọi API)...")
                # Dùng narration để suy luận pose
                stick_scenes = [(sc["narration"], d) for sc, d in zip(scenes, durations)]
                silent = build_procedural_stick_video(stick_scenes, workdir / "silent.mp4", fps=cfg["video"].get("fps", 30))
            else:
                self.log("[3] Tạo hình ảnh (Pollinations - có thể chậm)...")
                prompts = [sc["image_prompt"] for sc in scenes]
                images = fetch_images(prompts, workdir)
                self.log("[4] Xây dựng hiệu ứng hoạt hình (whiteboard/pollinations)...")
                silent = build_whiteboard_video(list(zip(images, durations)), workdir / "silent.mp4")

            if progress_cb:
                progress_cb("visuals", 100, 100)

            # 4. Audio concat + captions
            self.log("[5] Ghép âm thanh + phụ đề...")

            # Fast mode: dùng whisper tiny để nhanh (nếu cấu hình cho phép)
            if p.fast_mode:
                try:
                    # ép tạm config whisper nhanh
                    orig_whisper = cfg.get("whisper", {}).copy()
                    cfg.setdefault("whisper", {})["model"] = "tiny"
                    cfg["whisper"]["compute_type"] = "int8"
                except Exception:
                    pass

            voice_all = concat_audio_with_durations(voices, durations, workdir / "voice_all.m4a")

            if p.skip_captions:
                self.log("[5b] Bỏ qua phụ đề (ultra fast mode)")
                ass_path = None
            else:
                self.log("[5] Tạo phụ đề karaoke...")
                cap_style = cfg.get("captions_story") or cfg["captions"]
                ass_path = generate_captions(voice_all, workdir / "captions.ass", style=cap_style)

            # 6. Ghép video hoàn chỉnh (preset nhanh)
            self.log("[6] Ghép video hoàn chỉnh...")

            # Handle music
            final_music_path = None
            if p.use_music:
                if p.music_path:
                    mp = Path(p.music_path)
                    if mp.exists():
                        final_music_path = mp
                else:
                    music_dir = ROOT / "assets" / "music"
                    if music_dir.exists():
                        candidates = [p for p in music_dir.iterdir() if p.suffix.lower() in {".mp3", ".m4a", ".wav"}]
                        if candidates:
                            import random
                            final_music_path = random.choice(candidates)

            # Call assemble (hỗ trợ bỏ phụ đề)
            out = assemble_final(
                silent, voice_all, ass_path or Path(""), workdir,
                music_path=final_music_path,
                music_volume=p.music_volume if p.use_music else 0.0,
                skip_subtitles=p.skip_captions or ass_path is None,
            )

            # Save meta
            meta = {
                "params": asdict(p),
                "story": story,
                "voice": voice_cfg,
                "created": time.time(),
            }
            (workdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            elapsed = _time.time() - start_total
            self.log(f"✅ HOÀN TẤT trong {elapsed:.1f} giây → {out}")
            return out
        finally:
            # restore monkey patch
            try:
                common_mod.load_config = _orig_load
            except Exception:
                pass


# Convenience for CLI / simple call
def generate_video_simple(topic: str, **kwargs) -> Path:
    p = GenParams(topic=topic, **kwargs)
    gen = VideoGenerator(p)
    return gen.full_generate()
