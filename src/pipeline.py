"""Dieu phoi toan bo: chu de -> kich ban -> giong noi -> phu de -> B-roll -> video MP4.

Dung:
  python -m src.pipeline --topic "3 English phrases natives use instead of very good"
  python -m src.pipeline --batch topics.txt
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from .assemble import assemble_video
from .captions import generate_captions
from .common import workdir_for
from .script import generate_script
from .visuals import fetch_broll
from .voice import generate_voice


def make_video(topic: str) -> Path:
    print(f"\n=== Chu de: {topic} ===")
    workdir = workdir_for(topic)

    existing = workdir / "video.mp4"
    if existing.exists():
        print("      Bo qua (da co video.mp4). Xoa thu muc neu muon tao lai.")
        return existing

    print("[1/5] Viet kich ban (Groq)...")
    script = generate_script(topic)
    (workdir / "script.json").write_text(
        json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("      Hook:", script["hook"])

    print("[2/5] Long tieng (edge-tts)...")
    voice_path = generate_voice(script["narration"], workdir / "voice.mp3")

    print("[3/5] Tao phu de karaoke (faster-whisper)...")
    ass_path = generate_captions(voice_path, workdir / "captions.ass")

    print("[4/5] Tai B-roll (Pexels)...")
    clips = fetch_broll(script["visual_keywords"], workdir)
    print(f"      Da tai {len(clips)} clip.")

    print("[5/5] Ghep video (FFmpeg)...")
    out = assemble_video(clips, voice_path, ass_path, workdir)

    print(f"XONG -> {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Tao video short faceless English Learning.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="Mot chu de duy nhat")
    group.add_argument("--batch", help="File chua danh sach chu de (moi dong 1 chu de)")
    args = parser.parse_args()

    if args.topic:
        topics = [args.topic]
    else:
        lines = Path(args.batch).read_text(encoding="utf-8").splitlines()
        topics = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]

    ok, fail = 0, 0
    for topic in topics:
        try:
            make_video(topic)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"LOI o chu de '{topic}': {e}", file=sys.stderr)
            traceback.print_exc()

    print(f"\n=== Hoan tat: {ok} thanh cong, {fail} loi ===")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
