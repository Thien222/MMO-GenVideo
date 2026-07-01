"""Tao phu de karaoke (.ass) tu file giong noi bang faster-whisper.

Hieu ung: hien 1-3 tu moi lan, tung tu sang mau (highlight) dung luc duoc doc.
Day la yeu to giu chan nguoi xem #1 cua video short.
"""
from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel

from .common import load_config

_MODEL_CACHE: dict[str, WhisperModel] = {}


def _get_model(cfg: dict) -> WhisperModel:
    key = f"{cfg['model']}-{cfg['device']}-{cfg['compute_type']}"
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = WhisperModel(
            cfg["model"], device=cfg["device"], compute_type=cfg["compute_type"]
        )
    return _MODEL_CACHE[key]


def _transcribe_words(audio_path: Path, cfg: dict) -> list[dict]:
    """Tra ve danh sach tu kem moc thoi gian: [{word, start, end}, ...]."""
    model = _get_model(cfg)
    segments, _ = model.transcribe(str(audio_path), word_timestamps=True)
    words: list[dict] = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if not text:
                continue
            words.append({"word": text, "start": float(w.start), "end": float(w.end)})
    return words


def _fmt_time(t: float) -> str:
    """Doi giay -> dinh dang ASS H:MM:SS.cc."""
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _chunk_words(words: list[dict], size: int) -> list[list[dict]]:
    return [words[i : i + size] for i in range(0, len(words), size)]


def _build_ass(words: list[dict], cfg_cap: dict, width: int, height: int) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{cfg_cap['font']},{cfg_cap['fontsize']},{cfg_cap['primary_color']},{cfg_cap['secondary_color']},{cfg_cap['outline_color']},&H64000000,{cfg_cap.get('bold', 1)},0,0,0,100,100,0,0,1,{cfg_cap['outline']},{cfg_cap.get('shadow', 1)},2,80,80,{cfg_cap['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for chunk in _chunk_words(words, cfg_cap.get("words_per_chunk", 3)):
        if not chunk:
            continue
        start = chunk[0]["start"]
        end = chunk[-1]["end"]
        parts = []
        for w in chunk:
            dur_cs = max(5, int(round((w["end"] - w["start"]) * 100)))
            # \kf = karaoke fill: tu chuyen tu SecondaryColour -> PrimaryColour
            parts.append(f"{{\\kf{dur_cs}}}{w['word']} ")
        text = "".join(parts).strip()
        lines.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def generate_captions(audio_path: Path, ass_path: Path, style: dict | None = None) -> Path:
    """Tao file .ass karaoke tu file giong noi.

    style: neu truyen vao se thay cho config['captions'] (vd phu de cho video ke chuyen).
    """
    cfg = load_config()
    words = _transcribe_words(Path(audio_path), cfg["whisper"])
    if not words:
        raise RuntimeError("Whisper khong nhan dien duoc tu nao tu file giong noi.")

    cap_style = style if style is not None else cfg["captions"]
    ass = _build_ass(words, cap_style, cfg["video"]["width"], cfg["video"]["height"])
    ass_path = Path(ass_path)
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path.write_text(ass, encoding="utf-8")
    return ass_path


if __name__ == "__main__":
    import sys

    audio = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/_voice_test.mp3")
    out = generate_captions(audio, audio.with_suffix(".ass"))
    print("Da tao:", out)
