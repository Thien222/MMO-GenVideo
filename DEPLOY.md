# Hướng dẫn Deploy Free + Tối ưu Tốc độ Video (Rất quan trọng)

## Mục tiêu
- Deploy hoàn toàn miễn phí
- Tạo video **nhanh** (mục tiêu 30-90 giây thay vì >10 phút như bản cũ)

---

## 1. Tối ưu tốc độ (BẮT BUỘC làm trước khi deploy)

### Chọn style "🚀 NGƯỜI QUE NHANH" (procedural_stick)
- Đây là thay đổi quan trọng nhất.
- Không gọi Pollinations → không bị rate limit 15s/ảnh.
- Hoạt hình người que vẽ thủ công + pose tự động theo lời thoại.
- Thời gian giảm mạnh (thường chỉ còn 40-90s cho video 60s).

### Các tối ưu khác đã bật trong Fast Mode:
- Số cảnh thấp (4-6 cảnh)
- Whisper `tiny` + int8
- Giọng nói sinh song song
- Tail ngắn hơn
- FFmpeg ultrafast (có thể chỉnh thêm)

**Mẹo nhanh hơn nữa:**
- Giữ thời lượng 45-65 giây
- Tick "Chế độ SIÊU NHANH"
- Chỉ dùng Pollinations khi bạn cần hình "đẹp hơn" và chấp nhận chậm

---

## 2. Deploy miễn phí dễ nhất: Streamlit Community Cloud

### Bước 1: Push code lên GitHub (repo của bạn)
Repo: https://github.com/Thien222/MMO-GenVideo

```powershell
cd "C:\Users\thien\OneDrive\Desktop\MMO"
git add .
git commit -m "All features ready - Batch, Gallery, Fast procedural, Deploy files"
git push
```

### Bước 2: Deploy
1. Vào https://share.streamlit.io hoặc https://streamlit.io/cloud
2. Đăng nhập bằng GitHub.
3. Chọn repo **Thien222/MMO-GenVideo**
4. Main branch, file `app.py`
5. Click **Deploy**.

### Bước 3: Thêm Secrets (API keys)
Sau khi deploy:
- Vào app → **Manage app** (góc dưới bên phải) → **Secrets**
- Paste nội dung sau (thay key thật):

```toml
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# Tùy chọn (làm Pollinations nhanh gấp 3 lần nếu bạn có)
# POLLINATIONS_TOKEN = "your_token_here"
```

Lưu → Reboot app.

### Bước 4: packages.txt
Đã có sẵn file `packages.txt` chứa `ffmpeg`. Streamlit Cloud sẽ tự cài khi deploy.

---

## 3. Các nền tảng Free khác

| Nền tảng              | Dễ dùng | FFmpeg | Tốc độ | Ghi chú |
|-----------------------|---------|--------|--------|--------|
| **Streamlit Cloud**   | ★★★★★   | Có     | Trung bình | Khuyến nghị #1 |
| **Hugging Face Spaces** | ★★★★    | Có (Docker) | Tốt hơn  | Dùng Docker SDK |
| Render.com            | ★★★     | Cần build | Trung bình | Free tier sleep sau 15p inactivity |
| Railway / Fly.io      | ★★      | Có     | Tốt    | Có credit miễn phí ban đầu |

### Hugging Face Spaces (nếu muốn)
- New Space → Docker → Streamlit
- Hoặc dùng template Streamlit.
- Upload code + thêm secrets.

---

## 4. Lưu ý quan trọng khi deploy

1. **Free tier = tài nguyên chung** → đôi khi chậm hơn local.
2. Không nên để người dùng tạo hàng loạt video liên tục (có thể hết quota Groq/Pollinations).
3. Nên hướng dẫn user:
   - Dùng **procedural stick** để nhanh
   - Cung cấp `POLLINATIONS_TOKEN` nếu muốn dùng hình AI chất lượng cao
4. Video output có thể lưu tạm (không persist lâu dài trên một số nền tảng).
5. Nếu cần ổn định hơn → cân nhắc trả phí nhỏ (Render hobby ~$7/tháng) hoặc tự host VPS rẻ.

## 5. Checklist trước khi Deploy (All)

- [x] Dùng style "procedural_stick" mặc định
- [x] Fast mode ON
- [x] Thời lượng ngắn (45-65s)
- [x] GROQ_API_KEY trong Secrets
- [x] Test local với Ultra Fast trước
- [x] Music folder có file (hoặc tắt nhạc)
- [x] Push code mới nhất

Sau deploy, mở app và thử ngay 1 video ngắn với "NGƯỜI QUE NHANH" để kiểm tra tốc độ.

Nếu gặp lỗi ffmpeg, kiểm tra packages.txt có "ffmpeg".

---

**Làm All = Code đã sẵn sàng cho deploy + tốc độ tối đa + đầy đủ tính năng.**

Bây giờ chỉ cần push và deploy theo trên.

## 5. Test tốc độ sau deploy

Sau khi app chạy:
- Tạo video với:
  - Style: **NGƯỜI QUE NHANH**
  - Fast mode: ON
  - Thời lượng: 55s
  - Nội dung: Life lesson
- Mục tiêu: hoàn thành trong **< 2 phút**.

Nếu vẫn chậm:
- Kiểm tra log xem phần nào mất thời gian (voice / whisper / ffmpeg).
- Giảm số cảnh.
- Kiểm tra xem có đang rơi vào Pollinations không.

---

## 6. Cập nhật code sau deploy

Chỉ cần `git push`. Streamlit Cloud tự redeploy.

---

Chúc bạn có hệ thống tạo video **miễn phí + nhanh**!
