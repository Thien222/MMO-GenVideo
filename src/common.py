"""Tien ich dung chung: doc config, doc .env, tao duong dan, slugify."""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

def _get_st_secret(name: str) -> str:
    """Hỗ trợ Streamlit secrets khi deploy."""
    try:
        import streamlit as st
        val = st.secrets.get(name)
        if val:
            return str(val).strip()
    except Exception:
        pass
    return ""


def load_config() -> dict:
    """Doc config.yaml o thu muc goc."""
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_env(name: str, required: bool = True) -> str:
    """Lay bien moi truong tu .env (ho tro Streamlit secrets khi deploy)."""
    value = os.getenv(name, "").strip() or _get_st_secret(name)
    if required and (not value or value.startswith("your_")):
        raise RuntimeError(
            f"Thieu {name}. Hay tao file .env (copy tu .env.example) va dien key that. "
            "Khi deploy tren Streamlit Cloud thi dien vao Secrets."
        )
    return value


def slugify(text: str, max_len: int = 60) -> str:
    """Bien chu de thanh ten thu muc an toan."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:max_len].strip("-") or "video"


def workdir_for(topic: str) -> Path:
    """Tao thu muc lam viec rieng cho 1 video trong output/."""
    d = ROOT / "output" / slugify(topic)
    d.mkdir(parents=True, exist_ok=True)
    return d
