"""Ghep video cuoi cung bang FFmpeg.

- Crop B-roll ve 9:16 (1080x1920), noi cac clip de phu kin thoi luong giong noi
- Chay phu de karaoke (.ass)
- Tron nhac nen + tu dong ha nhac khi co giong noi (ducking)
- Xuat MP4
"""
from __future__ import annotations

import random
import subprocess
from pathlib import Path

from .common import ROOT, load_config


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "FFmpeg loi:\n" + (proc.stderr[-3000:] if proc.stderr else "(khong co log)")
        )


def _duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        raise RuntimeError(f"Khong doc duoc thoi luong cua {path}: {proc.stderr}")


def _pick_music() -> Path | None:
    music_dir = ROOT / "assets" / "music"
    if not music_dir.exists():
        return None
    files = [p for p in music_dir.iterdir() if p.suffix.lower() in {".mp3", ".m4a", ".wav"}]
    return random.choice(files) if files else None


def assemble_video(
    clips: list[Path],
    voice_path: Path,
    ass_path: Path,
    workdir: Path,
    out_name: str = "video.mp4",
) -> Path:
    cfg = load_config()
    W = cfg["video"]["width"]
    H = cfg["video"]["height"]
    FPS = cfg["video"]["fps"]
    music_vol = cfg["audio"]["music_volume"]
    duck = cfg["audio"]["duck"]

    workdir = Path(workdir)
    voice_path = Path(voice_path).resolve()
    ass_path = Path(ass_path)

    # .ass phai nam trong workdir va dung ten tuong doi (tranh loi escape duong dan tren Windows).
    ass_name = ass_path.name

    audio_dur = _duration(voice_path)
    n = len(clips)
    seg = audio_dur / n + 0.5  # cong them dem de chac chan phu kin

    music = _pick_music()

    cmd: list[str] = ["ffmpeg", "-y"]
    for clip in clips:
        cmd += ["-stream_loop", "-1", "-t", f"{seg:.3f}", "-i", str(Path(clip).resolve())]
    cmd += ["-i", str(voice_path)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music.resolve())]

    parts: list[str] = []
    for i in range(n):
        parts.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS},setpts=PTS-STARTPTS[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}]" for i in range(n))
    parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vcat]")
    parts.append(f"[vcat]subtitles={ass_name}[vout]")

    voice_idx = n
    if music:
        music_idx = n + 1
        parts.append(f"[{music_idx}:a]volume={music_vol},aresample=async=1[mvol]")
        if duck:
            parts.append(
                f"[mvol][{voice_idx}:a]sidechaincompress=threshold=0.02:ratio=8:"
                f"attack=5:release=300[mduck]"
            )
            parts.append(
                f"[{voice_idx}:a][mduck]amix=inputs=2:duration=first:normalize=0[aout]"
            )
        else:
            parts.append(
                f"[{voice_idx}:a][mvol]amix=inputs=2:duration=first:normalize=0[aout]"
            )
        audio_map = "[aout]"
    else:
        audio_map = f"{voice_idx}:a"

    filter_complex = ";".join(parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", audio_map,
        "-t", f"{audio_dur:.3f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        out_name,
    ]

    _run(cmd, cwd=workdir)
    out_path = workdir / out_name
    if not out_path.exists():
        raise RuntimeError("FFmpeg khong tao duoc file video.")
    return out_path


def concat_audio_with_durations(
    voice_paths: list[Path], durations: list[float], out_path: Path
) -> Path:
    """Ghep cac file giong noi theo tung canh, moi canh dem im lang cho du thoi luong canh."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = ["ffmpeg", "-y"]
    for vp in voice_paths:
        cmd += ["-i", str(Path(vp).resolve())]

    parts, labels = [], ""
    for i, d in enumerate(durations):
        parts.append(
            f"[{i}:a]aresample=44100,apad,atrim=0:{d:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
        labels += f"[a{i}]"
    parts.append(f"{labels}concat=n={len(durations)}:v=0:a=1[aout]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
        str(out_path.resolve()),
    ]
    _run(cmd, cwd=out_path.parent)
    if not out_path.exists():
        raise RuntimeError("Khong ghep duoc audio.")
    return out_path


def assemble_final(
    video_path: Path,
    voice_path: Path,
    ass_path: Path,
    workdir: Path,
    out_name: str = "video.mp4",
    music_path: Path | None = None,
    music_volume: float | None = None,
    skip_subtitles: bool = False,
) -> Path:
    """Ghep video co san (im lang) + giong noi + nhac nen + phu de -> MP4 hoan chinh.
    music_path: duong dan file nhac cu the (uu tien cao hon assets).
    skip_subtitles: bỏ phụ đề để siêu nhanh.
    """
    cfg = load_config()
    FPS = cfg["video"]["fps"]
    music_vol = music_volume if music_volume is not None else cfg["audio"]["music_volume"]
    duck = cfg["audio"]["duck"]

    workdir = Path(workdir)
    video_path = Path(video_path).resolve()
    voice_path = Path(voice_path).resolve()

    audio_dur = _duration(voice_path)

    # uu tien music_path -> assets
    music = None
    if (music_volume is None or music_volume > 0.005):
        music = music_path if music_path and Path(music_path).exists() else _pick_music()

    cmd: list[str] = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(voice_path)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(Path(music).resolve())]

    if skip_subtitles or not ass_path or not ass_path.exists():
        # Không có phụ đề → chỉ map video gốc
        parts = []
        vout = "[0:v]"
        if music:
            parts.append(f"[2:a]volume={music_vol},aresample=async=1[mvol]")
            if duck:
                parts.append("[mvol][1:a]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300[mduck]")
                parts.append("[1:a][mduck]amix=inputs=2:duration=first:normalize=0[aout]")
            else:
                parts.append("[1:a][mvol]amix=inputs=2:duration=first:normalize=0[aout]")
            audio_map = "[aout]"
        else:
            audio_map = "1:a"

        cmd += [
            "-map", "0:v", "-map", audio_map,
            "-t", f"{audio_dur:.3f}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            out_name,
        ]
    else:
        ass_name = Path(ass_path).name
        parts = [f"[0:v]subtitles={ass_name}[vout]"]
        if music:
            parts.append(f"[2:a]volume={music_vol},aresample=async=1[mvol]")
            if duck:
                parts.append(
                    "[mvol][1:a]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300[mduck]"
                )
                parts.append("[1:a][mduck]amix=inputs=2:duration=first:normalize=0[aout]")
            else:
                parts.append("[1:a][mvol]amix=inputs=2:duration=first:normalize=0[aout]")
            audio_map = "[aout]"
        else:
            audio_map = "1:a"

        cmd += [
            "-filter_complex", ";".join(parts),
            "-map", "[vout]", "-map", audio_map,
            "-t", f"{audio_dur:.3f}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            out_name,
        ]

    _run(cmd, cwd=workdir)
    out_path = workdir / out_name
    if not out_path.exists():
        raise RuntimeError("FFmpeg khong tao duoc file video.")
    return out_path
