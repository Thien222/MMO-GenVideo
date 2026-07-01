"""Tai B-roll video doc (portrait) tu Pexels theo tu khoa cua kich ban."""
from __future__ import annotations

from pathlib import Path

import requests

from .common import get_env, load_config

PEXELS_URL = "https://api.pexels.com/videos/search"
FALLBACK_QUERIES = ["nature", "city", "abstract background", "people walking"]


def _pick_portrait_file(video: dict, min_width: int) -> str | None:
    """Chon link file portrait co do phan giai phu hop (gan 1080 nhat)."""
    candidates = []
    for vf in video.get("video_files", []):
        w, h = vf.get("width") or 0, vf.get("height") or 0
        if h <= w:  # bo qua file ngang
            continue
        if vf.get("file_type") != "video/mp4":
            continue
        candidates.append(vf)
    if not candidates:
        return None
    # Uu tien file co chieu rong >= min_width, nho nhat trong so do; neu khong co thi lon nhat.
    ok = [vf for vf in candidates if vf["width"] >= min_width]
    if ok:
        chosen = min(ok, key=lambda vf: vf["width"])
    else:
        chosen = max(candidates, key=lambda vf: vf["width"])
    return chosen.get("link")


def _search(query: str, headers: dict, orientation: str, per_page: int) -> list[dict]:
    params = {"query": query, "orientation": orientation, "per_page": per_page}
    resp = requests.get(PEXELS_URL, params=params, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Pexels loi {resp.status_code}: {resp.text}")
    return resp.json().get("videos", [])


def _download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)


def fetch_broll(keywords: list[str], workdir: Path) -> list[Path]:
    """Tai B-roll cho cac tu khoa, tra ve danh sach duong dan clip da tai."""
    cfg = load_config()["pexels"]
    api_key = get_env("PEXELS_API_KEY")
    headers = {"Authorization": api_key}

    workdir = Path(workdir)
    clips_dir = workdir / "broll"
    clips_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    seen_ids: set[int] = set()
    queries = list(dict.fromkeys([k for k in keywords if k.strip()])) or FALLBACK_QUERIES

    for kw in queries:
        videos = _search(kw, headers, cfg["orientation"], cfg["per_keyword"] + 3)
        downloaded = 0
        for video in videos:
            if downloaded >= cfg["per_keyword"]:
                break
            vid = video.get("id")
            if vid in seen_ids:
                continue
            link = _pick_portrait_file(video, cfg["min_width"])
            if not link:
                continue
            dest = clips_dir / f"{vid}.mp4"
            try:
                _download(link, dest)
            except Exception:
                continue
            if dest.exists() and dest.stat().st_size > 0:
                seen_ids.add(vid)
                paths.append(dest)
                downloaded += 1

    # Du phong: neu khong tai duoc gi, thu cac tu khoa chung.
    if not paths:
        for kw in FALLBACK_QUERIES:
            videos = _search(kw, headers, cfg["orientation"], 5)
            for video in videos:
                link = _pick_portrait_file(video, cfg["min_width"])
                if not link:
                    continue
                dest = clips_dir / f"{video['id']}.mp4"
                try:
                    _download(link, dest)
                except Exception:
                    continue
                if dest.exists() and dest.stat().st_size > 0:
                    paths.append(dest)
                    break
            if paths:
                break

    if not paths:
        raise RuntimeError("Khong tai duoc B-roll nao tu Pexels (kiem tra key/ket noi mang).")
    return paths


if __name__ == "__main__":
    out = fetch_broll(["coffee shop", "city street"], Path("output/_broll_test"))
    print("Da tai:", [str(p) for p in out])
