"""
MMO Video Studio - Web UI
Giao diện dễ dùng để tạo video ngắn viral (người que / hoạt hình AI / whiteboard).

Chạy:
    streamlit run app.py

Yêu cầu:
    - .env có GROQ_API_KEY
    - ffmpeg + python deps đã cài
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

import streamlit as st

from src.common import ROOT, load_config, slugify
from src.web_gen import (
    ASPECTS, VISUAL_STYLES, CONTENT_MODES,
    GenParams, VideoGenerator, estimate_scenes,
)

# --------------------------- PAGE SETUP ---------------------------
st.set_page_config(
    page_title="MMO Video Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS nhẹ
st.markdown("""
<style>
    .main-title { font-size: 2.1rem; font-weight: 700; margin-bottom: 0.1rem; }
    .subtitle { color: #666; margin-bottom: 1rem; }
    .step-header { font-weight: 600; font-size: 1.05rem; }
    .scene-card { background: #f8f9fa; padding: 12px 14px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #eee; }
    .hook { font-style: italic; background: #fff3cd; padding: 6px 10px; border-radius: 6px; }
    .stButton>button { font-weight: 600; }
    .big-btn { font-size: 1.1rem !important; padding: 0.6rem 1.4rem !important; }
    .success-box { background:#d4edda; padding:12px; border-radius:8px; }
</style>
""", unsafe_allow_html=True)

# --------------------------- HELPERS ---------------------------
def get_recent_videos(limit: int = 12) -> list[dict]:
    """Return list of dicts with video path and metadata."""
    out_dir = ROOT / "output"
    items = []
    if out_dir.exists():
        for d in sorted(out_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                v = d / "video.mp4"
                if v.exists():
                    meta = {"path": v, "name": d.name, "time": d.stat().st_mtime}
                    # Try to get duration
                    try:
                        import subprocess
                        res = subprocess.run(
                            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(v)],
                            capture_output=True, text=True, timeout=5
                        )
                        dur = float(res.stdout.strip())
                        meta["duration"] = round(dur)
                    except Exception:
                        meta["duration"] = None
                    items.append(meta)
                    if len(items) >= limit:
                        break
    return items


def extract_thumbnail(video_path: Path, out_path: Path) -> Path | None:
    """Extract a thumbnail from video for gallery."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-ss", "00:00:03", "-vframes", "1", "-vf", "scale=320:-1", str(out_path)],
            capture_output=True, timeout=15
        )
        if out_path.exists():
            return out_path
    except Exception:
        pass
    return None


def load_topics_file(filename: str) -> list[str]:
    path = ROOT / filename
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    return []


TOPIC_FILES = {
    "topics.txt (English shorts)": "topics.txt",
    "topics_story.txt (Whiteboard stories)": "topics_story.txt",
    "messi_topics.txt": "messi_topics.txt",
}

def save_uploaded_music(uploaded_file) -> Path | None:
    if not uploaded_file:
        return None
    music_dir = ROOT / "assets" / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    dest = music_dir / f"custom_{int(time.time())}_{uploaded_file.name}"
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest

def render_scene_editor(story: dict, lang: str) -> dict:
    """Hiển thị và cho phép chỉnh sửa kịch bản scene-by-scene."""
    st.markdown("### 📝 Chỉnh sửa kịch bản (rất quan trọng cho chất lượng)")

    edited = story.copy()
    edited["title"] = st.text_input("Tiêu đề video", value=story.get("title", ""), key="title_edit")
    edited["hook"] = st.text_input("Hook (câu mở đầu cực mạnh)", value=story.get("hook", ""), key="hook_edit")

    st.caption("Chỉnh narration và image_prompt để tăng kịch tính / điểm nhấn viral. Sau đó bấm 'Lưu chỉnh sửa'.")

    scenes = story.get("scenes", [])
    new_scenes = []

    for idx, sc in enumerate(scenes):
        with st.container(border=True):
            st.markdown(f"**Cảnh {idx+1}**")
            nar = st.text_area(
                "Lời thoại (narration)",
                value=sc.get("narration", ""),
                height=70,
                key=f"nar_{idx}",
                help="Nên ngắn, giàu cảm xúc, có nhịp."
            )
            imgp = st.text_area(
                "Mô tả hình ảnh (image_prompt)",
                value=sc.get("image_prompt", ""),
                height=55,
                key=f"imgp_{idx}",
                help="Giữ đơn giản, 1-2 đối tượng chính. Tool sẽ tự thêm style."
            )
            new_scenes.append({"narration": nar.strip(), "image_prompt": imgp.strip()})

    edited["scenes"] = new_scenes

    # CTA
    edited["cta"] = st.text_input("CTA cuối video", value=story.get("cta", ""), key="cta_edit")

    if st.button("💾 Lưu chỉnh sửa kịch bản", use_container_width=True):
        st.session_state["edited_story"] = edited
        st.success("Đã lưu chỉnh sửa! Bây giờ bạn có thể render video.")
        st.rerun()

    return edited

# --------------------------- SIDEBAR ---------------------------
with st.sidebar:
    st.header("⚙️ Cài đặt nhanh")
    st.caption("Các giá trị này áp dụng cho lần tạo tiếp theo.")

    if st.button("📂 Mở thư mục output", use_container_width=True):
        os.startfile(str(ROOT / "output")) if os.name == "nt" else st.info(str(ROOT / "output"))

    st.divider()
    st.markdown("**Gợi ý chủ đề hot**")
    examples = [
        "Cậu bé bị thiếu hormone tăng trưởng đã làm gì để thay đổi số phận",
        "Bài học kiên nhẫn từ người nông dân",
        "Sự thật kinh hoàng về Tam giác Bermuda",
        "Tại sao người giàu không bao giờ làm những việc này",
        "Câu chuyện về sự trung thực thay đổi cả một thị trấn",
    ]
    for ex in examples:
        if st.button(ex[:55] + ("..." if len(ex) > 55 else ""), key=f"ex_{hash(ex)}"):
            st.session_state["topic_prefill"] = ex
            st.rerun()

    st.divider()
    st.markdown("**Hướng dẫn sử dụng nhanh**")
    st.markdown("""
    1. Nhập chủ đề / ý tưởng
    2. Chọn ngôn ngữ + voice
    3. Chọn khung hình + thời lượng
    4. Chọn **Style Người que / Hoạt hình**
    5. Bấm **Tạo kịch bản**
    6. **Chỉnh lời thoại** (bắt buộc để viral)
    7. Bấm **Render video**
    """)

    st.caption("💡 Muốn video kịch tính hơn → tick 'Kịch tính cao' + chọn Dramatic Sketch hoặc Stick Figure")

    st.divider()
    st.markdown("**💡 Mẹo Viral & Nhanh**")
    st.markdown("""
    - Dùng **NGƯỜI QUE NHANH** + Fast mode = video trong < 2 phút
    - Hook mạnh 3s đầu, có twist, bài học rõ
    - Thời lượng 45-65s là ngon nhất cho Shorts
    - Bỏ phụ đề khi test nhanh
    """)

# --------------------------- HEADER ---------------------------
st.markdown('<div class="main-title">🎥 MMO Video Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Tạo video ngắn viral dễ dàng • Người que • Hoạt hình AI • Kịch tính • Có nhạc nền</div>', unsafe_allow_html=True)

# Check keys (hỗ trợ cả local .env và Streamlit secrets)
cfg = load_config()

def _get_secret(name: str) -> str:
    # Streamlit secrets (deploy)
    if "st" in globals() and hasattr(st, "secrets"):
        try:
            val = st.secrets.get(name)
            if val:
                return val
        except Exception:
            pass
    # Local env
    return os.getenv(name, "")

groq_key = _get_secret("GROQ_API_KEY")
has_groq = bool(groq_key and not str(groq_key).startswith("your_"))
if not has_groq:
    st.error("⚠️ Thiếu GROQ_API_KEY. Local: tạo .env | Deploy: vào Secrets của Streamlit Cloud")
    st.info("Lấy key miễn phí tại https://console.groq.com")

# Quick ffmpeg check for deploy
try:
    import subprocess
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=3)
except Exception:
    st.warning("⚠️ Không tìm thấy ffmpeg. Trên deploy: đảm bảo packages.txt hoặc Dockerfile cài ffmpeg.")

# --------------------------- MAIN TABS ---------------------------
tab_create, tab_batch, tab_gallery, tab_deploy = st.tabs([
    "🎥 Tạo Video Đơn", 
    "📦 Batch Nhiều Video", 
    "🖼️ Thư viện & Lịch sử", 
    "🚀 Hướng dẫn Deploy"
])

with tab_create:
    st.markdown("## 1. Thiết lập yêu cầu")

# Defaults (All features optimized for speed)
_fast_default = True
_skip_default = False
_duration_default = 55
_visual_default = "procedural_stick"

col1, col2 = st.columns([3, 2])

with col1:
    default_topic = st.session_state.get("topic_prefill", "")
    if st.session_state.get("preset_ultra"):
        st.session_state["preset_ultra"] = False
        _visual_default = "procedural_stick"
        _fast_default = True
        _skip_default = True
        _duration_default = 55

    topic = st.text_area(
        "Nhập yêu cầu / chủ đề / cốt truyện",
        value=default_topic,
        height=110,
        placeholder="Ví dụ: Câu chuyện về một người đàn ông nghèo đã thay đổi cuộc đời nhờ một quyết định nhỏ...",
        help="Càng cụ thể càng tốt. Tool sẽ biến nó thành kịch bản kịch tính với hook + twist."
    )

    # Quick popular topics
    st.caption("Chủ đề gợi ý nhanh:")
    quick_topics = [
        "Cậu bé bị thiếu hormone tăng trưởng đã làm gì",
        "Bài học kiên nhẫn từ người nông dân nghèo",
        "Sự thật kinh hoàng về Tam giác Bermuda",
        "Tại sao người giàu không bao giờ làm việc này",
        "Câu chuyện về sự trung thực thay đổi cả một thị trấn"
    ]
    qcols = st.columns(len(quick_topics))
    for i, qt in enumerate(quick_topics):
        with qcols[i]:
            if st.button(qt[:22] + "...", key=f"quick_{i}"):
                st.session_state["topic_prefill"] = qt
                st.rerun()

with col2:
    lang = st.radio(
        "Ngôn ngữ",
        options=["vi", "en"],
        format_func=lambda x: "🇻🇳 Tiếng Việt" if x == "vi" else "🇬🇧 Tiếng Anh",
        horizontal=True,
    )

    # Rich voice options
    VOICES = {
        "vi": [
            ("vi-VN-HoaiMyNeural", "Nữ - Tự nhiên, ấm (khuyến nghị kể chuyện)"),
            ("vi-VN-NamMinhNeural", "Nam - Trầm, truyền cảm"),
        ],
        "en": [
            ("en-US-AndrewMultilingualNeural", "Nam - Trầm, hay cho kể chuyện (khuyến nghị)"),
            ("en-US-AriaNeural", "Nữ - Năng động"),
            ("en-US-GuyNeural", "Nam - Rõ ràng"),
            ("en-GB-SoniaNeural", "Nữ Anh - Sang trọng"),
            ("en-US-EmmaNeural", "Nữ - Dịu dàng"),
            ("en-US-BrianNeural", "Nam - Sâu"),
        ],
    }
    voice_display = [f"{v[0]} — {v[1]}" for v in VOICES[lang]]
    voice_choice = st.selectbox("Giọng nói", voice_display, index=0)
    voice_name = voice_choice.split(" — ")[0]

    st.caption("💡 Andrew/HoaiMy rất hợp video kịch tính. Dùng slider ở Advanced để chỉnh tốc độ.")

# Row 2: Khung hình + Thời lượng + Style
col3, col4, col5 = st.columns(3)

with col3:
    aspect = st.selectbox(
        "Khung hình (Aspect Ratio)",
        list(ASPECTS.keys()),
        format_func=lambda k: f"{k} — {ASPECTS[k]['label']}",
        index=0,
    )

with col4:
    duration = st.slider(
        "Thời lượng mục tiêu (giây)",
        min_value=30, max_value=120, value=_duration_default, step=5,
        help="Ngắn = nhanh hơn rất nhiều. 45-70s là lý tưởng cho viral Shorts."
    )
    est_scenes = estimate_scenes(duration, fast=_fast_default)
    est_time = max(25, int(duration * 0.9 + est_scenes * 6))
    st.caption(f"Ước tính ~{est_scenes} cảnh → khoảng {est_time}-{est_time+35}s khi dùng procedural + fast mode")

with col5:
    visual_style = st.selectbox(
        "🎨 Phong cách hình ảnh",
        list(VISUAL_STYLES.keys()),
        format_func=lambda k: VISUAL_STYLES[k],
        index=list(VISUAL_STYLES.keys()).index(_visual_default) if _visual_default in VISUAL_STYLES else 0,
    )
    if visual_style == "procedural_stick":
        st.success("🚀 Siêu nhanh (không gọi Pollinations). Khuyến nghị cho video nhanh!")
    elif visual_style == "stick_figure":
        st.info("Chất lượng tốt hơn nhưng chậm hơn nhiều (cần gọi API hình)")
    elif "dramatic" in visual_style:
        st.info("Kịch tính cao nhưng chậm vì phải tải hình")

col6, col7 = st.columns(2)
with col6:
    content_mode = st.selectbox(
        "Loại nội dung",
        list(CONTENT_MODES.keys()),
        format_func=lambda k: CONTENT_MODES[k],
        index=0,
    )

with col7:
    dramatic = st.checkbox("🔥 Tăng kịch tính & điểm nhấn viral (khuyến nghị)", value=True)
    fast_mode = st.checkbox("⚡ Chế độ SIÊU NHANH (ít cảnh + whisper tiny + procedural)", value=_fast_default)
    skip_captions = st.checkbox("🔥 Siêu nhanh cực độ: BỎ PHỤ ĐỀ (chỉ còn giọng nói + hình)", value=_skip_default, help="Tiết kiệm thêm 20-50s, phù hợp khi test nhanh")

# Music section
st.markdown("### 🎵 Nhạc nền")
mcol1, mcol2, mcol3 = st.columns([1.2, 1, 1])

with mcol1:
    use_music = st.checkbox("Lồng nhạc nền tự động", value=True)

with mcol2:
    music_vol = st.slider("Âm lượng nhạc", 0.03, 0.25, 0.11, 0.01, disabled=not use_music)

with mcol3:
    uploaded = st.file_uploader("Tải nhạc riêng (tùy chọn)", type=["mp3", "m4a", "wav"], disabled=not use_music)
    custom_music = save_uploaded_music(uploaded) if uploaded else None
    if custom_music:
        st.caption(f"✓ Đã nhận: {custom_music.name}")

    # List available music
    music_dir = ROOT / "assets" / "music"
    available_music = []
    if music_dir.exists():
        available_music = [f.name for f in music_dir.iterdir() if f.suffix.lower() in (".mp3", ".m4a", ".wav")]
    if available_music and use_music:
        selected_music_name = st.selectbox("Chọn nhạc có sẵn", ["Ngẫu nhiên"] + available_music, key="music_select")
        if selected_music_name != "Ngẫu nhiên":
            custom_music = music_dir / selected_music_name

# Advanced settings
with st.expander("⚙️ Cài đặt nâng cao (Voice, Token, ... )"):
    acol1, acol2 = st.columns(2)

    with acol1:
        voice_rate = st.slider("Tốc độ giọng nói", -20, 20, 0, 2, format="%+d%%") 
        voice_rate_str = f"{voice_rate:+d}%"

        voice_pitch = st.slider("Cao độ giọng nói", -20, 20, 0, 2, format="%+dHz")
        voice_pitch_str = f"{voice_pitch:+d}Hz"

    with acol2:
        polli_token = st.text_input(
            "Pollinations Token (tùy chọn - làm hình AI nhanh hơn ~3x)",
            type="password",
            help="Đăng ký miễn phí tại https://auth.pollinations.ai để có token. Chỉ cần khi dùng style Pollinations (không procedural)"
        )

    st.caption("Voice rate/pitch chỉ áp dụng cho lần tạo này.")

# Topics Presets + Batch
st.markdown("### 📚 Chủ đề mẫu & Batch")
tcol1, tcol2 = st.columns([1, 1])

with tcol1:
    st.caption("Chọn file chủ đề có sẵn:")
    topic_file_choice = st.selectbox("Chọn danh sách", list(TOPIC_FILES.keys()), index=0)
    if st.button("📥 Tải chủ đề từ file vào ô nhập"):
        loaded = load_topics_file(TOPIC_FILES[topic_file_choice])
        if loaded:
            st.session_state["loaded_topics"] = loaded
            st.success(f"Đã tải {len(loaded)} chủ đề. Bạn có thể dùng ở Batch bên dưới hoặc copy 1 cái.")
        else:
            st.warning("Không tìm thấy file.")

with tcol2:
    st.caption("Chế độ Batch (nhiều chủ đề cùng lúc):")
    batch_mode = st.checkbox("Bật Batch mode", value=False)
    if batch_mode:
        batch_text = st.text_area(
            "Nhập nhiều chủ đề (mỗi dòng 1 chủ đề)",
            value="\n".join(st.session_state.get("loaded_topics", [])[:5]) if st.session_state.get("loaded_topics") else "",
            height=100,
            placeholder="Chủ đề 1\nChủ đề 2\n..."
        )
        st.session_state["batch_mode_active"] = True
    else:
        st.session_state["batch_mode_active"] = False

# Action buttons + Presets
st.divider()

# Ultra Fast Preset button (All features)
if st.button("⚡⚡ SET ULTRA FAST PRESET (Người que + Nhanh nhất + Bỏ phụ đề)", use_container_width=True):
    st.session_state["topic_prefill"] = topic or "Bài học cuộc sống từ người bình thường"
    # Will be handled in next rerun via defaults
    st.rerun()

btn_col1, btn_col2, btn_col3 = st.columns([1.6, 1.6, 1])

with btn_col1:
    gen_story_btn = st.button("📜 TẠO / TẠO LẠI KỊCH BẢN", type="primary", use_container_width=True)

with btn_col2:
    render_btn = st.button("🎬 RENDER VIDEO ĐẦY ĐỦ", use_container_width=True)

# Preview only (script + voice) - siêu nhanh để test
if st.button("👀 Preview nhanh: Chỉ kịch bản + giọng nói (5-15s)", help="Test nội dung trước khi render hình"):
    if topic.strip():
        params = GenParams(topic=topic.strip(), lang=lang, fast_mode=True, skip_captions=True, visual_style="procedural_stick", duration=min(45, duration))
        st.session_state["params"] = params
        with st.spinner("Tạo nhanh preview..."):
            gen = VideoGenerator(params)
            story = gen.generate_story_only()
            st.session_state["story"] = story
            st.session_state["edited_story"] = story
            st.success("Preview sẵn sàng. Bạn có thể chỉnh và render sau.")
            st.rerun()

with btn_col3:
    if st.button("🧹 Xóa session", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith(("story", "edited", "gen", "params")):
                del st.session_state[k]
        st.rerun()

# Quick preset
if st.button("⚡ Chọn ngay: ULTRA FAST (60s, Người que nhanh, bỏ phụ đề)", use_container_width=False):
    st.session_state["preset_ultra"] = True
    st.rerun()

# --------------------------- STATE INIT ---------------------------
if "params" not in st.session_state:
    st.session_state.params = None
if "story" not in st.session_state:
    st.session_state.story = None
if "edited_story" not in st.session_state:
    st.session_state.edited_story = None
if "video_path" not in st.session_state:
    st.session_state.video_path = None
if "gen_logs" not in st.session_state:
    st.session_state.gen_logs = []

# --------------------------- GENERATE STORY ---------------------------
if gen_story_btn:
    if not topic.strip():
        st.error("Vui lòng nhập chủ đề / yêu cầu.")
    elif not has_groq:
        st.error("Thiếu GROQ_API_KEY.")
    else:
        custom_rate = voice_rate_str if 'voice_rate_str' in locals() else ("-4%" if lang == "vi" else "+2%")
        custom_pitch = voice_pitch_str if 'voice_pitch_str' in locals() else "+0Hz"

        params = GenParams(
            topic=topic.strip(),
            lang=lang,
            aspect=aspect,
            duration=duration,
            visual_style=visual_style,
            content_mode=content_mode,
            voice_name=voice_name,
            voice_rate=custom_rate,
            voice_pitch=custom_pitch,
            use_music=use_music,
            music_volume=music_vol,
            music_path=str(custom_music) if custom_music else None,
            dramatic=dramatic,
            fast_mode=fast_mode,
            skip_captions=skip_captions,
            polli_token=polli_token if 'polli_token' in locals() and polli_token else None,
        )
        st.session_state.params = params

        with st.spinner("Đang viết kịch bản bằng AI (Groq)..."):
            gen = VideoGenerator(params)
            story = gen.generate_story_only()
            st.session_state.story = story
            st.session_state.edited_story = story  # khởi tạo
            st.session_state.gen_logs = gen.get_logs()
            st.session_state.video_path = None

        st.success("Kịch bản đã sẵn sàng! Hãy chỉnh sửa bên dưới rồi bấm Render.")
        st.rerun()

# --------------------------- SHOW STORY + EDITOR ---------------------------
current_story = st.session_state.get("edited_story") or st.session_state.get("story")

if current_story:
    st.markdown("---")
    st.markdown("## 2. Kịch bản & Chỉnh sửa")

    # Hiển thị meta
    meta = current_story.get("_meta", {})
    st.markdown(f"**{current_story.get('title','')}** — {meta.get('num_scenes', len(current_story.get('scenes',[])))} cảnh | {lang.upper()} | {visual_style}")

    with st.expander("Hook gốc (để tham khảo)", expanded=False):
        st.markdown(f"> {current_story.get('hook','')}")

    # Editor
    edited = render_scene_editor(current_story, lang)
    # Cập nhật nếu người dùng vừa lưu
    if st.session_state.get("edited_story"):
        current_story = st.session_state["edited_story"]

    st.markdown("---")

# --------------------------- RENDER VIDEO (SINGLE + BATCH) ---------------------------
if render_btn:
    is_batch = st.session_state.get("batch_mode_active", False) or ( 'batch_mode' in locals() and batch_mode and 'batch_text' in locals() and batch_text.strip() )

    if is_batch:
        # BATCH MODE
        topics = [t.strip() for t in batch_text.split("\n") if t.strip()] if 'batch_text' in locals() else []
        if not topics:
            st.error("Vui lòng nhập ít nhất 1 chủ đề trong Batch text area.")
        else:
            st.info(f"🚀 Bắt đầu Batch {len(topics)} video (có thể mất nhiều thời gian)...")
            batch_results = []
            for idx, t in enumerate(topics, 1):
                st.write(f"### [{idx}/{len(topics)}] {t}")
                bparams = GenParams(
                    topic=t,
                    lang=lang,
                    aspect=aspect,
                    duration=duration,
                    visual_style="procedural_stick",  # force fast for batch
                    content_mode=content_mode,
                    voice_name=voice_name,
                    voice_rate="-4%" if lang == "vi" else "+2%",
                    use_music=use_music,
                    music_volume=music_vol,
                    fast_mode=True,
                    skip_captions=skip_captions,
                )
                bgen = VideoGenerator(bparams)
                try:
                    bstory = bgen.generate_story_only()
                    bout = bgen.full_generate(story_override=bstory)
                    batch_results.append((t, bout))
                    st.success(f"✅ Xong: {bout.name}")
                except Exception as be:
                    st.error(f"Lỗi với '{t}': {be}")
            st.session_state["batch_results"] = batch_results
            st.rerun()

    else:
        # SINGLE
        params: GenParams | None = st.session_state.get("params")
        story_to_use = st.session_state.get("edited_story") or st.session_state.get("story")

        if not params or not story_to_use:
            st.error("Bạn cần tạo kịch bản trước (bước 1).")
        else:
            # Cập nhật lại một số param từ UI (nếu thay đổi)
            params.use_music = use_music
            params.music_volume = music_vol
            if custom_music:
                params.music_path = str(custom_music)
            if 'polli_token' in locals() and polli_token:
                params.polli_token = polli_token

            gen = VideoGenerator(params)
            st.session_state.gen_logs = []

            progress_placeholder = st.empty()

            with st.status("Đang render video... (dùng procedural nhanh nhất)", expanded=True) as status:
                def progress_cb(stage: str, current: int, total: int):
                    progress_placeholder.progress(min(current / max(total, 1), 1.0), text=f"{stage}: {current}/{total}")

                try:
                    out_path = gen.full_generate(story_override=story_to_use, progress_cb=progress_cb)
                    st.session_state.video_path = str(out_path)
                    st.session_state.gen_logs = gen.get_logs()
                    status.update(label="✅ Video đã tạo xong!", state="complete")
                    st.balloons()
                except Exception as e:
                    status.update(label="❌ Có lỗi", state="error")
                    st.exception(e)
                    st.session_state.gen_logs.append(f"ERROR: {e}")

            st.rerun()

# --------------------------- BATCH RESULTS ---------------------------
if st.session_state.get("batch_results"):
    st.markdown("## ✅ Kết quả Batch")
    for topic_name, vpath in st.session_state["batch_results"]:
        st.write(f"**{topic_name}**")
        if Path(vpath).exists():
            with open(vpath, "rb") as f:
                st.download_button(f"⬇️ Tải {Path(vpath).name}", data=f.read(), file_name=Path(vpath).name)
    if st.button("Xóa kết quả batch"):
        st.session_state["batch_results"] = []
        st.rerun()

# --------------------------- FINAL RESULT ---------------------------
video_path = st.session_state.get("video_path")
if video_path and Path(video_path).exists():
    st.markdown("---")
    st.markdown("## ✅ Video của bạn đã sẵn sàng")

    vp = Path(video_path)
    workdir = vp.parent

    # Video player
    with open(vp, "rb") as f:
        video_bytes = f.read()
    st.video(video_bytes, start_time=0)

    # Downloads - Full assets
    st.markdown("**Tải các file thành phần (rất hữu ích để chỉnh sửa thêm):**")

    files_to_offer = []
    story_file = workdir / "story.json"
    if story_file.exists():
        files_to_offer.append(("📜 Kịch bản (story.json)", story_file))

    captions_file = workdir / "captions.ass"
    if captions_file.exists():
        files_to_offer.append(("💬 Phụ đề (.ass)", captions_file))

    # Voice files
    voice_files = sorted(workdir.glob("voice_*.mp3")) or sorted(workdir.glob("voice_*.m4a"))
    if voice_files:
        files_to_offer.append(("🔊 Giọng nói từng cảnh (zip gợi ý tải riêng)", None))  # special

    voice_all = workdir / "voice_all.m4a"
    if voice_all.exists():
        files_to_offer.append(("🔊 Toàn bộ giọng nói", voice_all))

    silent = workdir / "silent.mp4"
    if silent.exists():
        files_to_offer.append(("🎞️ Video im lặng (không lời)", silent))

    dcols = st.columns(min(4, max(1, len(files_to_offer))))
    for i, (label, fpath) in enumerate(files_to_offer):
        with dcols[i % len(dcols)]:
            if fpath and fpath.exists():
                with open(fpath, "rb") as ff:
                    st.download_button(label, data=ff.read(), file_name=fpath.name, use_container_width=True)
            elif "Giọng nói từng cảnh" in label:
                # Zip voices on the fly
                import zipfile, io
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for vf in voice_files:
                        zf.writestr(vf.name, vf.read_bytes())
                zip_buffer.seek(0)
                st.download_button(label, data=zip_buffer, file_name="voices.zip", mime="application/zip", use_container_width=True)

    dcol_extra1, dcol_extra2 = st.columns(2)
    with dcol_extra1:
        st.download_button("⬇️ Tải video MP4", data=video_bytes, file_name=vp.name, mime="video/mp4", use_container_width=True)
    with dcol_extra2:
        if st.button("📂 Mở thư mục output", use_container_width=True):
            os.startfile(str(workdir)) if os.name == "nt" else st.info(str(workdir))

    st.caption(f"📁 Thư mục: {vp.parent}")

    # Show scenes + images if exist
    if (workdir / "images").exists():
        with st.expander("🖼️ Xem hình ảnh các cảnh (để kiểm tra)"):
            imgs = sorted((workdir / "images").glob("*.png"))
            for i, imgp in enumerate(imgs):
                col_img, col_txt = st.columns([1, 2])
                with col_img:
                    st.image(str(imgp), caption=f"Cảnh {i+1}", width=220)
                with col_txt:
                    if st.session_state.get("edited_story"):
                        sc = st.session_state["edited_story"]["scenes"][i] if i < len(st.session_state["edited_story"]["scenes"]) else {}
                        st.text(sc.get("narration", "")[:280])
    else:
        # For procedural, show story scenes
        if st.session_state.get("edited_story"):
            with st.expander("📝 Xem chi tiết các cảnh trong kịch bản"):
                for i, sc in enumerate(st.session_state["edited_story"].get("scenes", [])):
                    st.markdown(f"**Cảnh {i+1}:** {sc.get('narration', '')[:200]}...")

# --------------------------- RECENT + LOGS ---------------------------
st.divider()

with st.expander("📜 Nhật ký lần chạy gần nhất"):
    logs = st.session_state.get("gen_logs", [])
    if logs:
        st.code("\n".join(logs))
    else:
        st.caption("Chưa có log.")

st.markdown("### 🖼️ Thư viện Video gần đây")
recents = get_recent_videos(9)
if recents:
    cols = st.columns(3)
    for idx, item in enumerate(recents):
        with cols[idx % 3]:
            vpath = item["path"]
            thumb_dir = ROOT / "output" / "_thumbnails"
            thumb_path = thumb_dir / f"{item['name']}.jpg"
            if not thumb_path.exists():
                extract_thumbnail(vpath, thumb_path)

            if thumb_path.exists():
                st.image(str(thumb_path), use_column_width=True)
            else:
                st.caption("🎥 Video")

            dur_str = f" • {item.get('duration', '?')}s" if item.get('duration') else ""
            st.caption(f"{item['name'][:35]}{dur_str}")

            if st.button(f"▶ Xem & Tải", key=f"gallery_{idx}"):
                st.session_state.video_path = str(vpath)
                st.rerun()
else:
    st.info("Chưa có video. Hãy tạo video đầu tiên ở tab 'Tạo Video Đơn'!")

# Deploy help (hữu ích khi user mở app đã deploy)
with st.expander("🚀 Hướng dẫn Deploy miễn phí + Tạo video nhanh (quan trọng)"):
    st.markdown("""
**Để video nhanh nhất:**
- Chọn **🚀 NGƯỜI QUE NHANH**
- Tick **Chế độ SIÊU NHANH**
- Tick **BỎ PHỤ ĐỀ** nếu chỉ test
- Thời lượng 45-65 giây

**Deploy free (Streamlit Cloud - dễ nhất):**
1. Push code lên GitHub
2. https://share.streamlit.io → Deploy app.py
3. Vào **Secrets** thêm `GROQ_API_KEY`
4. `packages.txt` và `Dockerfile` đã có sẵn

Xem file **DEPLOY.md** trong repo để có hướng dẫn đầy đủ (Render, HF Spaces...).
""")

# Footer
st.caption("MMO Video Studio • Procedural Stick (siêu nhanh) • Việt + Anh • Free deploy ready")

st.markdown("---")
with st.expander("📋 TÓM TẮT ALL FEATURES ĐÃ LÀM (hoàn chỉnh)"):
    st.markdown("""
**Tính năng Web đầy đủ:**
- Nhập yêu cầu tự do + quick topics + load từ file (topics, messi...)
- Chọn khung hình (9:16, 16:9, 1:1, 4:5)
- Chọn thời lượng
- Voice đầy đủ VN (HoaiMy, NamMinh) + EN nhiều giọng hay
- Tùy chỉnh rate/pitch
- Style: Người que NHANH (mặc định, siêu tốc), hoặc Pollinations styles
- Fast mode + Siêu nhanh (bỏ phụ đề)
- Nhạc nền: tự động hoặc chọn/upload
- Batch mode: tạo nhiều video cùng lúc
- Chỉnh sửa kịch bản chi tiết từng cảnh
- Tích hợp Pollinations token
- Gallery lịch sử với thumbnail
- Tải đầy đủ assets (video, story, voices zip, captions, silent)

**Tốc độ:**
- Procedural stick: không rate limit Pollinations
- Song song voice
- Whisper tiny
- FFmpeg ultrafast
- Mặc định 55s, 5 cảnh → thường 40-90 giây

**Deploy:**
- Dockerfile, render.yaml, packages.txt sẵn
- Secrets support
- Hướng dẫn trong app + DEPLOY.md

Mọi thứ đã sẵn sàng cho free deploy và tạo video nhanh + viral.
""")

# ============ COMPLETE DEPLOY GUIDE (for all) ============
with st.expander("🚀 HƯỚNG DẪN DEPLOY MIỄN PHÍ HOÀN CHỈNH - Làm ngay (Copy-Paste)", expanded=False):
    st.markdown(f"""
    **Repo của bạn:** https://github.com/Thien222/MMO-GenVideo

    ### Bước 1: Push code mới nhất (chứa tất cả tính năng)
    ```powershell
    cd "C:\\Users\\thien\\OneDrive\\Desktop\\MMO"
    git add .
    git commit -m "All features: Batch + Gallery + Advanced + Deploy ready"
    git push
    ```

    ### Bước 2: Deploy trên Streamlit Cloud (dễ nhất, miễn phí)
    1. Mở https://share.streamlit.io
    2. New app → GitHub repo `Thien222/MMO-GenVideo`
    3. Main file: `app.py`
    4. Deploy

    ### Bước 3: Thêm API Key (Secrets)
    Vào **Manage app → Settings → Secrets**, paste:
    ```toml
    GROQ_API_KEY = "gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    ```
    (Lấy key tại https://console.groq.com)

    ### Bước 4: Xong!
    App sẽ chạy công khai. Mọi lần `git push` sau này sẽ tự cập nhật.

    **Lưu ý tốc độ trên cloud:**
    - Luôn chọn **🚀 NGƯỜI QUE NHANH**
    - Tick **Chế độ SIÊU NHANH** + **Bỏ phụ đề** khi test
    - 45-65 giây là tối ưu

    Xem file `DEPLOY.md` và `Dockerfile` + `render.yaml` trong repo để deploy Render.com nếu muốn.
    """)
