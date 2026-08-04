"""提示词灵感：合并原「灵感预设」+「风格灵感」。

点选 → 整段写入提示词框（可再改）；不加载 LoRA。
可分类、收藏、用户自建。
"""
from __future__ import annotations

import json
import re
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
    "画面气质",
    "电影剧照",
    "光影氛围",
    "材质质感",
    "印刷纸艺",
    "亚文化",
    "二次元",
    "职业人像",
    "多人叙事",
    "自然风光",
    "城市建筑",
    "产品商业",
    "美食",
    "海报平面",
    "绘本",
    "超现实",
    "东方视觉",
    "时尚结构",
    "民俗图形",
    "手作器物",
    "古典摄影",
    "复古数码",
    "有机表面",
    "科学影像",
    "空间舞台",
    "黑马精选",
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
        # 兼容旧数据：推荐/达芬七精选 不再作为筛选入口
        if category in ("推荐", "达芬七精选"):
            return True
        if category == "我的":
            return self.user
        if category == "收藏":
            return is_favorite(self.id)
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
            # 隐藏已废弃分类名
            if c in ("达芬七精选", "推荐", "封面"):
                continue
            found.add(c)
    ordered = [c for c in CATEGORY_ORDER if c in found]
    rest = sorted(found - set(ordered) - {"达芬七精选", "推荐", "封面"})
    base = ["全部", "收藏"]
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
        star = "★ " if s.id in favs else ""
        items.append((path, star + s.name))
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


def _auto_name_from_prompt(prompt: str) -> str:
    t = re.sub(r"\s+", " ", (prompt or "").strip())
    if not t:
        return "我的灵感"
    # 取前 16 字，去掉标点尾巴
    t = t[:16].rstrip("，,。.!！?？;；:： ")
    return t or "我的灵感"


def _make_user_placeholder_cover(sid: str, name: str) -> str:
    """生成纯文字占位封面到 userdata/covers，无需用户上传。返回相对文件名。"""
    ensure_runtime_dirs()
    fname = f"{sid}.jpg"
    dest = USER_COVERS_DIR / fname
    try:
        from PIL import Image, ImageDraw, ImageFont

        w, h = 480, 600
        # 稳定配色：按 id 哈希挑色
        hues = [
            (36, 32, 48),
            (28, 40, 52),
            (48, 32, 36),
            (32, 44, 40),
            (40, 36, 52),
            (44, 36, 28),
        ]
        bg = hues[sum(ord(c) for c in sid) % len(hues)]
        im = Image.new("RGB", (w, h), bg)
        dr = ImageDraw.Draw(im)
        # 顶条
        dr.rectangle([0, 0, w, 8], fill=(212, 168, 90))
        dr.rectangle([24, 24, w - 24, h - 24], outline=(212, 168, 90), width=2)
        title = (name or "我的灵感").strip()[:18]
        # 字体：Windows 常见中文字体
        font = None
        for fp in (
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc",
        ):
            try:
                font = ImageFont.truetype(fp, 36)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        # 居中多行
        lines = []
        buf = ""
        for ch in title:
            buf += ch
            if len(buf) >= 8:
                lines.append(buf)
                buf = ""
        if buf:
            lines.append(buf)
        if not lines:
            lines = ["我的灵感"]
        y = h // 2 - len(lines) * 28
        for line in lines:
            bbox = dr.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            dr.text(((w - tw) / 2, y), line, fill=(245, 240, 230), font=font)
            y += 48
        sub = "用户自建 · 无封面"
        try:
            sfont = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 18)
        except Exception:
            sfont = font
        bbox = dr.textbbox((0, 0), sub, font=sfont)
        tw = bbox[2] - bbox[0]
        dr.text(((w - tw) / 2, h - 64), sub, fill=(180, 170, 150), font=sfont)
        tmp = dest.with_suffix(".tmp.jpg")
        im.save(tmp, quality=88)
        tmp.replace(dest)
        return fname
    except Exception:
        # 兜底：不生成也没关系，gallery 会用 default_card
        return ""


def save_user_inspiration(
    name: str,
    prompt: str,
    category: str = "我的",
    tip: str = "",
    cover_path: str | None = None,
) -> tuple[bool, str, Optional[Inspiration]]:
    """保存用户灵感。名称可空（从提示词自动起名）；封面可选，不传则自动文字卡。"""
    prompt = (prompt or "").strip()
    if not prompt:
        return False, "提示词为空——在上方输入框写好再点保存", None
    name = (name or "").strip() or _auto_name_from_prompt(prompt)
    items = _load_user_raw()
    existing = None
    for raw in items:
        if raw.get("user") and raw.get("name") == name:
            existing = raw
            break
    sid = (existing or {}).get("id") or f"user_{uuid.uuid4().hex[:8]}"
    cover_name = ""
    # 可选：用户上传的本地图片
    if cover_path:
        try:
            from PIL import Image

            src = Path(cover_path)
            if src.exists() and src.is_file():
                ensure_runtime_dirs()
                cover_name = f"{sid}.jpg"
                dest = USER_COVERS_DIR / cover_name
                im = Image.open(src).convert("RGB")
                im.thumbnail((640, 800))
                tmp = dest.with_suffix(".tmp.jpg")
                im.save(tmp, quality=88)
                tmp.replace(dest)
        except Exception:
            cover_name = ""
    if not cover_name:
        # 沿用旧封面或生成占位
        if existing and existing.get("cover"):
            old = USER_COVERS_DIR / str(existing["cover"])
            if old.exists():
                cover_name = str(existing["cover"])
        if not cover_name:
            cover_name = _make_user_placeholder_cover(sid, name)

    entry = {
        "id": sid,
        "name": name,
        "kind": "inspiration",
        "user": True,
        "cover": cover_name,
        "tags": ["我的"],
        "featured": False,
        "category": category or "我的",
        "categories": [category or "我的", "我的"],
        "prompt": prompt,
        "tip": tip or "用户自建 · 可随时改",
        "source": {"credit": "我的", "url": "", "note": "用户自建"},
        "commercial": "用户自建",
    }
    if existing:
        items = [entry if r.get("id") == sid else r for r in items]
        msg = f"已更新：{name}"
    else:
        items.insert(0, entry)
        msg = f"已保存到「我的」：{name}"
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


def update_user_inspiration(
    inspo_id: str,
    name: str,
    prompt: str,
    category: str = "我的",
    tip: str = "",
) -> tuple[bool, str, Optional[Inspiration]]:
    """编辑用户自建灵感（内置只读）。"""
    sid = (inspo_id or "").strip()
    name = (name or "").strip()
    prompt = (prompt or "").strip()
    if not sid:
        return False, "未指定灵感", None
    if not name or not prompt:
        return False, "名称和提示词不能为空", None
    items = _load_user_raw()
    found = None
    for raw in items:
        if raw.get("id") == sid:
            found = raw
            break
    if not found:
        return False, "只能编辑自己保存的灵感", None
    if not found.get("user") and not str(sid).startswith("user_"):
        return False, "内置灵感不可改，可「另存」后再编辑", None
    entry = {
        **found,
        "name": name,
        "prompt": prompt,
        "category": category or "我的",
        "categories": [category or "我的", "我的"],
        "tip": tip if tip is not None else found.get("tip") or "",
        "user": True,
    }
    items = [entry if r.get("id") == sid else r for r in items]
    _save_user_raw(items)
    return True, f"已更新：{name}", _from_raw(entry, user=True)


