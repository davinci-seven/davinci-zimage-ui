"""Saved prompt favorites for one-click reuse (userdata)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import USERDATA, ensure_runtime_dirs

FAV_FILE = USERDATA / "favorites.json"


def _load() -> list[dict[str, Any]]:
    ensure_runtime_dirs()
    if not FAV_FILE.exists():
        return []
    try:
        data = json.loads(FAV_FILE.read_text(encoding="utf-8"))
        return list(data.get("favorites") or [])
    except Exception:
        return []


def _save(items: list[dict[str, Any]]) -> None:
    ensure_runtime_dirs()
    FAV_FILE.parent.mkdir(parents=True, exist_ok=True)
    FAV_FILE.write_text(
        json.dumps({"favorites": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_favorites() -> list[dict[str, Any]]:
    return _load()


def fav_choices() -> list[str]:
    items = ["（未选收藏）"]
    for f in _load():
        title = (f.get("title") or "未命名").strip()
        fid = f.get("id") or ""
        items.append(f"{title} · {fid}")
    return items


def parse_fav_id(label: str) -> str | None:
    if not label or label.startswith("（未"):
        return None
    return label.rsplit("·", 1)[-1].strip() or None


def get_favorite(fav_id: str) -> dict[str, Any] | None:
    for f in _load():
        if f.get("id") == fav_id:
            return f
    return None


def save_favorite(prompt: str, title: str = "") -> tuple[bool, str]:
    text = (prompt or "").strip()
    if not text:
        return False, "提示词为空，没法收藏"
    items = _load()
    # de-dupe by exact prompt
    for f in items:
        if (f.get("prompt") or "").strip() == text:
            return True, f"已收藏过：{f.get('title') or f.get('id')}"
    fid = uuid.uuid4().hex[:8]
    t = (title or "").strip()
    if not t:
        one = text.replace("\n", " ").strip()
        t = (one[:22] + "…") if len(one) > 22 else one
    items.insert(
        0,
        {
            "id": fid,
            "title": t,
            "prompt": text,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    )
    # cap
    items = items[:80]
    _save(items)
    return True, f"已收藏：{t}"


def delete_favorite(fav_id: str) -> tuple[bool, str]:
    if not fav_id:
        return False, "请先选择一条收藏"
    items = _load()
    n = len(items)
    items = [f for f in items if f.get("id") != fav_id]
    if len(items) == n:
        return False, "没找到这条收藏"
    _save(items)
    return True, "已删除收藏"


def resolve_fav_prompt(label: str) -> str:
    fid = parse_fav_id(label)
    if not fid:
        return ""
    f = get_favorite(fid)
    return (f.get("prompt") if f else "") or ""
