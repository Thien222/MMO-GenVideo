# MMO Video Studio - Tạo Video Ngắn Viral (Người que / Hoạt hình)

**Repo:** https://github.com/Thien222/MMO-GenVideo

**✅ ALL FEATURES DONE + FAST + DEPLOY READY**

- Web UI đầy đủ: nhập yêu cầu, khung hình, thời lượng, voice VN/EN, style (Người que NHANH mặc định)
- Siêu nhanh: Procedural stick figure (không Pollinations rate limit) + Fast mode + Skip captions → video 45-70s chỉ ~40-90s
- Batch, Gallery với thumbnail, chỉnh sửa script, tải assets đầy đủ, music, token input, topics presets
- Deploy free dễ dàng (Streamlit Cloud / Render / HF)

Công cụ tạo video short **kịch tính + dễ viral** bằng AI (người que hoạt hình, whiteboard, cartoon đơn giản).

**Điểm nổi bật mới:**
- Giao diện web Streamlit dễ dùng
- Hỗ trợ đầy đủ **Tiếng Việt + Tiếng Anh**
- **Siêu nhanh** với chế độ Người que thủ công (procedural) - không phụ thuộc Pollinations rate limit
- Nhạc nền, chỉnh sửa kịch bản trực tiếp, chọn khung hình, thời lượng...

Bản cũ tạo >10 phút → Bản mới (fast mode) thường chỉ **40-120 giây**.

---

## 1. Cai dat (lam 1 lan)

### 1.1. Cai cong cu nen (Windows, mo PowerShell)
```powershell
winget install Python.Python.3.11
winget install Gyan.FFmpeg
```
Dong va mo lai PowerShell, kiem tra:
```powershell
python --version
ffmpeg -version
```

### 1.2. Cai thu vien Python
```powershell
cd "$HOME\OneDrive\Desktop\MMO"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
> Neu bao chan script khi Activate: chay 1 lan `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 1.3. Khai bao API key
- Copy file `.env.example` thanh `.env`
- Dien `GROQ_API_KEY` (lay tai https://console.groq.com)
- Dien `PEXELS_API_KEY` (lay tai https://www.pexels.com/api)

### 1.4. (Tuy chon) Them nhac nen
Tai vai file nhac free (YouTube Audio Library / Pixabay Music) cho vao thu muc `assets/music/`.
Cong cu se tu chon ngau nhien 1 bai va ha am luong duoi giong noi. Khong co nhac van chay binh thuong.

---

## 2. Sử dụng (Đầy đủ tính năng)

### Chạy Local
```powershell
.\venv\Scripts\Activate.ps1
pip install streamlit
streamlit run app.py
```

**Tính năng đầy đủ (all):**
- Tạo đơn lẻ với chỉnh sửa kịch bản
- **Batch** nhiều video cùng lúc
- **Thư viện** xem lại video + thumbnail
- Chọn khung hình, thời lượng, voice VN/EN đầy đủ
- **Người que siêu nhanh** (mặc định) + Pollinations khi cần
- Nhạc nền, upload nhạc, tùy chỉnh voice rate/pitch
- Tích hợp chủ đề có sẵn (messi, story, topics)
- Xuất đầy đủ file thành phần

### Deploy Hoàn chỉnh MIỄN PHÍ (quan trọng nhất)

**Repo:** https://github.com/Thien222/MMO-GenVideo

1. Push code:
   ```powershell
   git add .
   git commit -m "ready"
   git push
   ```

2. Deploy tại https://share.streamlit.io → chọn repo của bạn → app.py

3. Thêm `GROQ_API_KEY` vào Secrets

Xem **DEPLOY.md** + tab "🚀 Hướng dẫn Deploy" ngay trong app để có hướng dẫn chi tiết.

**Để video nhanh nhất:**
- Chọn **🚀 NGƯỜI QUE NHANH**
- Tick **Chế độ SIÊU NHANH**
- 45-65 giây

---

Giao diện web hiện đại cho phép:
- Nhập yêu cầu
- Chọn **khung hình** (9:16 / 16:9...)
- Chọn **thời lượng**
- Chọn **voice** Tiếng Việt & Tiếng Anh
- Chọn **style**: Người que nhanh (khuyến nghị), Cartoon, Whiteboard...
- Chỉnh sửa kịch bản trước khi render (quan trọng nhất)
- Tự động lồng nhạc + tạo điểm nhấn viral

---

### CLI cũ (vẫn dùng được)

Tao 1 video tu 1 chu de:
```powershell
python -m src.pipeline --topic "3 English phrases natives use instead of very good"
```

Tao hang loat tu danh sach chu de:
```powershell
python -m src.pipeline --batch topics.txt
```

Video xuat ra nam trong `output/<ten-chu-de>/video.mp4`.

> Lan dau chay, faster-whisper se tai model (~140MB) - cho 1 lan.

---

## 2b. Video WHITEBOARD ke chuyen (facts/mystery)

Dang video "ve tay" ke chuyen su that/bi an, dai 1-3 phut, cho khan gia nuoc ngoai.
Dung Groq (kich ban) + edge-tts (giong ke) + Pollinations (hinh line-art, free khong key)
+ OpenCV (hieu ung ve tay) + faster-whisper (phu de) + FFmpeg.

Tao 1 video:
```powershell
python -m src.pipeline_whiteboard --topic "the mystery of the Bermuda Triangle"
```

Tao hang loat:
```powershell
python -m src.pipeline_whiteboard --batch topics_story.txt
```

Luu y: Pollinations tier free gioi han ~1 anh/15 giay, nen 1 video (7 canh) mat ~2-6 phut
(phan lon la cho tai anh). Video xuat ra `output\wb-<chu-de>\video.mp4`.

Tuy chinh trong `config.yaml`:
- `story.num_scenes`: so canh (6-9 cho 1-3 phut)
- `images.style`: phong cach net ve
- `whiteboard`: toc do ve (`draw_ratio`), co cay but (`pen`), le (`margin`)
- `captions_story`: style phu de cho video ke chuyen
- Doi giong ke: `voice.name` (vd `en-US-GuyNeural` nam, tram, hop ke chuyen)

---

## 3. Tuy chinh

Mo `config.yaml` de doi:
- `voice.name`: giong doc (vd `en-US-GuyNeural`)
- `captions`: mau/size/vi tri phu de
- `llm.model`: doi sang `llama-3.1-8b-instant` neu muon nhanh hon
- `audio.music_volume`: am luong nhac nen

Doi chu de: sua file `topics.txt`.

---

## 4. Quy trinh "chinh chu" truoc khi dang

Cong cu cho ra ban hoan chinh. De them "loi cuon", co the mo MP4 trong **CapCut (free)** va:
- Them sound effect (whoosh/pop) khi chuyen y
- Them chu hook to o 1-2 giay dau
- Cat bo khoang lang thua

Xem checklist day du trong cuoc tro chuyen huong dan.

---

## 5. Cau truc du an
```
MMO/
  config.yaml          # cau hinh
  topics.txt           # danh sach chu de
  requirements.txt
  .env                 # API key (tu tao)
  topics_story.txt     # chu de cho video whiteboard ke chuyen
  src/
    script.py          # Groq -> kich ban English shorts
    story.py           # Groq -> kich ban whiteboard ke chuyen (nhieu canh)
    voice.py           # edge-tts -> giong noi
    captions.py        # faster-whisper -> phu de karaoke .ass
    visuals.py         # Pexels -> B-roll doc (English shorts)
    images.py          # Pollinations -> hinh line-art (whiteboard)
    whiteboard.py      # OpenCV -> hieu ung ve tay
    assemble.py        # FFmpeg -> ghep MP4
    pipeline.py            # dieu phoi English shorts
    pipeline_whiteboard.py # dieu phoi whiteboard ke chuyen
  assets/music/        # nhac nen (tu them)
  output/              # video ket qua
```
