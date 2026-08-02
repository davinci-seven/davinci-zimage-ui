"""提示词灵感：合并原「灵感预设」+「风格灵感」。

点选 → 整段写入提示词框（可再改）；不加载 LoRA。
可分类、收藏、用户自建。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .paths import (
    COVERS_DIR,
    PACK_ROOT,
    USER_COVERS_DIR,
    USERDATA,
    ensure_runtime_dirs,
)

INSPIRATIONS_FILE = PACK_ROOT / "assets" / "prompts" / "inspirations.json"
USER_INSPIRATIONS_FILE = USERDATA / "inspirations_user.json"
INSPO_FAVORITES_FILE = USERDATA / "inspiration_favorites.json"

CATEGORY_ORDER = [
    "达芬七精选",
    "写实写真",
    "电影剧照",
    "场景/环境",
    "画面灵感",
    "文字/海报",
    "产品/商业",
    "角色设定",
    "Civitai精选",
    "我的",
    "其他",
]


@dataclass
class Inspiration:
    id: str
    name: str
    prompt: str
    cover: str = ""
    tags: list[str] = field(default_factory=list)
    tip: str = ""
    featured: bool = False
    category: str = "其他"
    categories: list[str] = field(default_factory=list)
    source: dict = field(default_factory=dict)
    commercial: str = ""
    user: bool = False

    def cats(self) -> list[str]:
        out: list[str] = []
        for c in list(self.categories or []) + ([self.category] if self.category else []):
            c = (c or "").strip()
            if c and c not in out:
                out.append(c)
        return out or ["其他"]

    def in_category(self, category: str | None) -> bool:
        if not category or category in ("全部", ""):
            return True
        if category == "推荐":
            return self.featured
        if category == "我的":
            return self.user
        return category in self.cats()

    @property
    def cover_path(self) -> Optional[str]:
        candidates: list[Path] = []
        if self.cover:
            candidates.append(COVERS_DIR / self.cover)
            candidates.append(USER_COVERS_DIR / self.cover)
            stem = Path(self.cover).stem
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                candidates.append(COVERS_DIR / f"{stem}{ext}")
                candidates.append(USER_COVERS_DIR / f"{stem}{ext}")
        for name in (f"{self.id}.jpg", f"{self.id}.png", "default_card.jpg", "default.jpg"):
            candidates.append(COVERS_DIR / name)
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def label(self) -> str:
        prefix = "👤 " if self.user else ("⭐ " if self.featured else "")
        return f"{prefix}{self.name}"

    def source_credit(self) -> str:
        return ((self.source or {}).get("credit") or "").strip()

    def source_url(self) -> str:
        return ((self.source or {}).get("url") or "").strip()


def _parse_cats(raw: dict) -> tuple[str, list[str]]:
    cats: list[str] = []
    if isinstance(raw.get("categories"), list):
        cats = [str(c).strip() for c in raw["categories"] if str(c).strip()]
    primary = (raw.get("category") or "").strip()
    if primary and primary not in cats:
        cats.insert(0, primary)
    if not cats:
        cats = ["其他"]
    if not primary:
        primary = cats[0]
    return primary, cats


def _from_raw(raw: dict, *, user: bool = False) -> Inspiration:
    sid = str(raw["id"])
    primary, cats = _parse_cats(raw)
    src = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    return Inspiration(
        id=sid,
        name=raw.get("name") or raw.get("title") or sid,
        prompt=(raw.get("prompt") or "").strip(),
        cover=raw.get("cover") or f"{sid}.jpg",
        tags=list(raw.get("tags") or []),
        tip=raw.get("tip") or "",
        featured=bool(raw.get("featured", False)),
        category=primary,
        categories=cats,
        source=dict(src or {}),
        commercial=raw.get("commercial") or "",
        user=user or bool(raw.get("user", False)),
    )


def _read_list(path: Path, key: str = "inspirations") -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return list(data.get(key) or data.get("presets") or data.get("styles") or [])
        return list(data or [])
    except Exception:
        return []


def load_inspirations() -> list[Inspiration]:
    by_id: dict[str, Inspiration] = {}
    for raw in _read_list(INSPIRATIONS_FILE, "inspirations"):
        if "id" not in raw:
            continue
        by_id[str(raw["id"])] = _from_raw(raw, user=False)
    ensure_runtime_dirs()
    for raw in _read_list(USER_INSPIRATIONS_FILE, "inspirations"):
        if "id" not in raw:
            continue
        by_id[str(raw["id"])] = _from_raw(raw, user=True)

    items = list(by_id.values())

    def sort_key(x: Inspiration):
        primary = x.cats()[0]
        order = CATEGORY_ORDER.index(primary) if primary in CATEGORY_ORDER else 50
        return (not x.featured, not x.user, order, x.name)

    items.sort(key=sort_key)
    return items


def inspiration_categories() -> list[str]:
    found: set[str] = set()
    has_user = False
    for s in load_inspirations():
        if s.user:
            has_user = True
        for c in s.cats():
            found.add(c)
    ordered = [c for c in CATEGORY_ORDER if c in found]
    rest = sorted(found - set(ordered))
    base = ["推荐", "全部"]
    if has_user and "我的" not in ordered:
        base.append("我的")
    return base + ordered + rest


def resolve_inspiration(label: str) -> Optional[Inspiration]:
    if not label or str(label).startswith("（无"):
        return None
    clean = (
        str(label)
        .replace("⭐ ", "")
        .replace("👤 ", "")
        .replace("🔒 ", "")
        .strip()
    )
    for s in load_inspirations():
        if s.name == clean or s.id == clean or s.label() == str(label).strip():
            return s
    return None


def _gallery_none_path() -> str:
    for name in ("default_card.jpg", "default.jpg", "default.png"):
        p = COVERS_DIR / name
        if p.exists():
            return str(p)
    return ""


def inspiration_gallery_data(
    category: str = "全部",
    favorites_only: bool = False,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (gallery items, labels) including leading 无."""
    items: list[tuple[str, str]] = []
    labels: list[str] = []
    fb = _gallery_none_path()
    items.append((fb, "无灵感"))
    labels.append("（无）")
    favs = set(list_favorite_ids())
    for s in load_inspirations():
        if favorites_only and s.id not in favs:
            continue
        if not s.in_category(category):
            continue
        path = s.cover_path or fb
        if not path:
            continue
        items.append((path, s.name))
        labels.append(s.label())
    return items, labels


# ----- favorites -----


def _load_fav_ids() -> list[str]:
    ensure_runtime_dirs()
    if not INSPO_FAVORITES_FILE.exists():
        return []
    try:
        data = json.loads(INSPO_FAVORITES_FILE.read_text(encoding="utf-8"))
        return [str(x) for x in (data.get("ids") or []) if x]
    except Exception:
        return []


def _save_fav_ids(ids: list[str]) -> None:
    ensure_runtime_dirs()
    INSPO_FAVORITES_FILE.write_text(
        json.dumps({"ids": ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_favorite_ids() -> list[str]:
    return _load_fav_ids()


def is_favorite(inspo_id: str) -> bool:
    return inspo_id in _load_fav_ids()


def toggle_favorite(inspo_id: str) -> tuple[bool, str]:
    sid = (inspo_id or "").strip()
    if not sid:
        return False, "未选择灵感"
    ids = _load_fav_ids()
    if sid in ids:
        ids = [x for x in ids if x != sid]
        _save_fav_ids(ids)
        return False, "已取消收藏"
    ids.insert(0, sid)
    _save_fav_ids(ids[:200])
    return True, "已收藏灵感"


# ----- user CRUD -----


def _load_user_raw() -> list[dict]:
    return _read_list(USER_INSPIRATIONS_FILE, "inspirations")


def _save_user_raw(items: list[dict]) -> None:
    ensure_runtime_dirs()
    USER_INSPIRATIONS_FILE.write_text(
        json.dumps({"inspirations": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_user_inspiration(
    name: str,
    prompt: str,
    category: str = "我的",
    tip: str = "",
) -> tuple[bool, str, Optional[Inspiration]]:
    name = (name or "").strip()
    prompt = (prompt or "").strip()
    if not name:
        return False, "请填写名称", None
    if not prompt:
        return False, "提示词为空", None
    items = _load_user_raw()
    existing = None
    for raw in items:
        if raw.get("user") and raw.get("name") == name:
            existing = raw
            break
    sid = (existing or {}).get("id") or f"user_{uuid.uuid4().hex[:8]}"
    entry = {
        "id": sid,
        "name": name,
        "kind": "inspiration",
        "user": True,
        "cover": "",
        "tags": ["我的"],
        "featured": False,
        "category": category or "我的",
        "categories": [category or "我的", "我的"],
        "prompt": prompt,
        "tip": tip or "用户自建提示词灵感",
        "source": {"credit": "我的", "url": "", "note": "用户自建"},
        "commercial": "用户自建",
    }
    if existing:
        items = [entry if r.get("id") == sid else r for r in items]
        msg = f"已更新：{name}"
    else:
        items.insert(0, entry)
        msg = f"已保存：{name}"
    _save_user_raw(items[:200])
    return True, msg, _from_raw(entry, user=True)


def delete_user_inspiration(inspo_id: str) -> tuple[bool, str]:
    sid = (inspo_id or "").strip()
    if not sid:
        return False, "未指定"
    items = _load_user_raw()
    found = [r for r in items if r.get("id") == sid]
    if not found:
        return False, "只能删除自己保存的灵感"
    if not found[0].get("user") and not str(sid).startswith("user_"):
        return False, "只能删除用户灵感"
    items = [r for r in items if r.get("id") != sid]
    _save_user_raw(items)
    _save_fav_ids([x for x in _load_fav_ids() if x != sid])
    return True, "已删除"


