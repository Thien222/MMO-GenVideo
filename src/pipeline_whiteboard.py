"""Pipeline VIDEO WHITEBOARD ke chuyen (facts/mystery).

chu de -> kich ban nhieu canh (Groq) -> giong noi (edge-tts) -> hinh line-art (Pollinations)
-> hieu ung ve tay (OpenCV) -> phu de (faster-whisper) -> ghep MP4 (FFmpeg).

Dung:
  python -m src.pipeline_whiteboard --topic "the mystery of the Bermuda Triangle"
  python -m src.pipeline_whiteboard --batch topics_story.txt
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

from .assemble import _duration, assemble_final, concat_audio_with_durations
from .captions import generate_captions
from .common import ROOT, load_config, slugify, workdir_for
from .images import fetch_images
from .story import generate_story
from .voice import generate_voice
from .whiteboard import build_whiteboard_video


def make_whiteboard_video(topic: str) -> Path:
    cfg = load_config()
    tail = cfg["whiteboard"]["scene_tail"]
    cap_style = cfg.get("captions_story") or cfg["captions"]
    story_voice = cfg["story"].get("voice") or cfg["voice"]

    print(f"\n=== Chu de: {topic} ===")
    workdir = workdir_for("wb-" + topic)

    existing = workdir / "video.mp4"
    if existing.exists():
        print("      Bo qua (da co video.mp4). Xoa thu muc neu muon tao lai.")
        return existing

    print("[1/6] Viet kich ban ke chuyen (Groq)...")
    story = generate_story(topic)
    (workdir / "story.json").write_text(
        json.dumps(story, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    scenes = story["scenes"]
    print(f"      Tieu de: {story['title']} ({len(scenes)} canh)")

    print("[2/6] Long tieng tung canh (edge-tts)...")
    voices: list[Path] = []
    durations: list[float] = []
    for i, sc in enumerate(scenes):
        vp = generate_voice(sc["narration"], workdir / f"voice_{i:02d}.mp3", voice_cfg=story_voice)
        voices.append(vp)
        durations.append(_duration(vp) + tail)

    print("[3/6] Tao hinh line-art (Pollinations, co nghi giua cac lan)...")
    prompts = [sc["image_prompt"] for sc in scenes]
    images = fetch_images(prompts, workdir)

    print("[4/6] Dung hieu ung ve tay (OpenCV)...")
    silent = build_whiteboard_video(list(zip(images, durations)), workdir / "silent.mp4")

    print("[5/6] Ghep tieng + tao phu de...")
    voice_all = concat_audio_with_durations(voices, durations, workdir / "voice_all.m4a")
    ass_path = generate_captions(voice_all, workdir / "captions.ass", style=cap_style)

    print("[6/6] Ghep video hoan chinh (FFmpeg)...")
    out = assemble_final(silent, voice_all, ass_path, workdir)

    print(f"XONG -> {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Tao video whiteboard ke chuyen facts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="Mot chu de duy nhat")
    group.add_argument("--batch", help="File danh sach chu de (moi dong 1 chu de)")
    args = parser.parse_args()

    if args.topic:
        topics = [args.topic]
    else:
        lines = Path(args.batch).read_text(encoding="utf-8").splitlines()
        topics = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]

    ready_dir = ROOT / "output" / "_ready"
    ready_dir.mkdir(parents=True, exist_ok=True)

    ok, fail = 0, 0
    for topic in topics:
        try:
            out = make_whiteboard_video(topic)
            # Gom video thanh pham vao 1 cho cho de lay len lich dang.
            shutil.copy2(out, ready_dir / f"{slugify(topic)}.mp4")
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"LOI o chu de '{topic}': {e}", file=sys.stderr)
            traceback.print_exc()

    print(f"\n=== Hoan tat: {ok} thanh cong, {fail} loi. Video gom tai: {ready_dir} ===")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
