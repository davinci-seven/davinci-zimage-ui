"""Style / LoRA catalog — supports multi-category per style."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .paths import COVERS_DIR, LORAS_DIR, STYLES_FILE

# 分类展示顺序（可扩展）
CATEGORY_ORDER = [
    "真实",
    "二次元",
    "电影",
    "插画",
    "风景",
    "质感",
    "复古",
    "角色设定",
    "成人向",
    "整体风格",
    "质感增强",
    "其他",
]


@dataclass
class Style:
    id: str
    name: str
    file: str  # relative to models/loras
    cover: str
    tags: list[str]
    default_weight: float
    trigger: str
    nsfw: bool
    tip: str
    featured: bool = False
    category: str = "其他"  # 主分类（兼容旧字段）
    categories: list[str] = field(default_factory=list)  # 可多选
    civitai_url: str = ""
    commercial: str = "许可未标注，使用前请自行确认"

    def cats(self) -> list[str]:
        """All categories this style belongs to (deduped, non-empty)."""
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
        return category in self.cats()

    @property
    def cover_path(self) -> Optional[str]:
        if self.cover:
            p = COVERS_DIR / self.cover
            if p.exists():
                return str(p)
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                alt = COVERS_DIR / f"{Path(self.cover).stem}{ext}"
                if alt.exists():
                    return str(alt)
        # prefer local generated id.jpg
        for name in (f"{self.id}.jpg", "default_card.jpg", "default.jpg", "default.png"):
            fb = COVERS_DIR / name
            if fb.exists():
                return str(fb)
        return None

    def exists(self) -> bool:
        rel = self.file.replace("\\", "/")
        return (LORAS_DIR / Path(rel)).exists()

    def comfy_lora_name(self) -> str:
        """Name as ComfyUI folder_paths lists on Windows: 'zimage\\\\file.safetensors'."""
        rel = self.file.replace("\\", "/").lstrip("/")
        # Prefer exact on-disk relative path under LORAS_DIR
        p = LORAS_DIR / Path(rel)
        if p.exists():
            try:
                rel_os = str(p.relative_to(LORAS_DIR))
            except ValueError:
                rel_os = rel
            return rel_os.replace("/", "\\")
        # fallback: force backslash form Comfy expects in dropdown
        return rel.replace("/", "\\")


def ensure_cover_name(style_id: str, configured: str) -> str:
    preferred = f"{style_id}.jpg"
    if (COVERS_DIR / preferred).exists():
        return preferred
    return configured or preferred


def _parse_categories(raw: dict) -> tuple[str, list[str]]:
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


def load_styles(include_missing: bool = False) -> list[Style]:
    if not STYLES_FILE.exists():
        return []
    data = json.loads(STYLES_FILE.read_text(encoding="utf-8"))
    items = data.get("styles") or data
    styles: list[Style] = []
    for raw in items:
        sid = raw["id"]
        cover = raw.get("cover") or f"{sid}.jpg"
        if (COVERS_DIR / f"{sid}.jpg").exists():
            cover = f"{sid}.jpg"
        primary, cats = _parse_categories(raw)
        s = Style(
            id=sid,
            name=raw["name"],
            file=raw["file"],
            cover=cover,
            tags=list(raw.get("tags") or []),
            default_weight=float(raw.get("default_weight", 0.85)),
            trigger=raw.get("trigger") or "",
            nsfw=bool(raw.get("nsfw", False)),
            tip=raw.get("tip") or "",
            featured=bool(raw.get("featured", False)),
            category=primary,
            categories=cats,
            civitai_url=raw.get("civitai_url") or "",
            commercial=raw.get("commercial") or "许可未标注，使用前请自行确认",
        )
        if include_missing or s.exists():
            styles.append(s)

    def sort_key(x: Style):
        primary = x.cats()[0]
        order = CATEGORY_ORDER.index(primary) if primary in CATEGORY_ORDER else 50
        return (not x.featured, order, x.nsfw, x.name)

    styles.sort(key=sort_key)
    return styles


def styles_by_id() -> dict[str, Style]:
    return {s.id: s for s in load_styles(include_missing=True)}


def style_choices(show_nsfw: bool = True, category: Optional[str] = None) -> list[str]:
    names = ["（无风格）"]
    for s in load_styles():
        if s.nsfw and not show_nsfw:
            continue
        if not s.in_category(category):
            continue
        prefix = "🔒 " if s.nsfw else ("⭐ " if s.featured else "")
        names.append(f"{prefix}{s.name}")
    return names


def style_categories(show_nsfw: bool = True) -> list[str]:
    found: set[str] = set()
    for s in load_styles():
        if s.nsfw and not show_nsfw:
            continue
        for c in s.cats():
            found.add(c)
    ordered = [c for c in CATEGORY_ORDER if c in found]
    rest = sorted(found - set(ordered))
    return ["推荐", "全部"] + ordered + rest


def resolve_style_name(label: str) -> Optional[Style]:
    if not label or str(label).startswith("（无"):
        return None
    clean = (
        str(label)
        .replace("⭐ ", "")
        .replace("🔒 ", "")
        .replace("◆ ", "")
        .strip()
    )
    if " · " in clean:
        clean = clean.split(" · ", 1)[-1].strip()
    for s in load_styles(include_missing=True):
        if s.name == clean or s.id == clean:
            return s
    return None


def catalog_summary() -> dict[str, Any]:
    all_s = load_styles(include_missing=True)
    present = [s for s in all_s if s.exists()]
    by_cat: dict[str, int] = {}
    for s in present:
        for c in s.cats():
            by_cat[c] = by_cat.get(c, 0) + 1
    return {
        "catalog_total": len(all_s),
        "available": len(present),
        "missing": [s.name for s in all_s if not s.exists()],
        "nsfw_available": sum(1 for s in present if s.nsfw),
        "by_category": by_cat,
    }
