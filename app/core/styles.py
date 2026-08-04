"""Style catalog: LoRA styles + prompt styles + user styles + favorites.

v1.4.5: kind=lora | prompt. Prompt styles never load a safetensors.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .paths import (
    COVERS_DIR,
    LORAS_DIR,
    PROMPT_STYLES_FILE,
    STYLE_FAVORITES_FILE,
    STYLES_FILE,
    USER_COVERS_DIR,
    USER_STYLES_FILE,
    ensure_runtime_dirs,
)

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
    "封面",
    "达芬七精选",
    "好友开源",
    "我的",
    "成人向",
    "整体风格",
    "质感增强",
    "其他",
]

KIND_LORA = "lora"
KIND_PROMPT = "prompt"


@dataclass
class Style:
    id: str
    name: str
    file: str = ""  # relative to models/loras; empty for prompt styles
    cover: str = ""
    tags: list[str] = field(default_factory=list)
    default_weight: float = 0.85
    trigger: str = ""
    nsfw: bool = False
    tip: str = ""
    featured: bool = False
    category: str = "其他"
    categories: list[str] = field(default_factory=list)
    civitai_url: str = ""
    commercial: str = "许可未标注，使用前请自行确认"
    kind: str = KIND_LORA  # lora | prompt
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    negative: str = ""
    source: dict = field(default_factory=dict)
    user: bool = False  # from userdata/styles_user.json

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
        if category == "推荐":  # 兼容旧入口 → 等同全部
            return True
        if category == "我的":
            return self.user
        if category == "收藏":
            return is_favorite(self.id)
        return category in self.cats()

    def is_prompt(self) -> bool:
        return (self.kind or KIND_LORA).lower() == KIND_PROMPT

    def is_lora(self) -> bool:
        return not self.is_prompt()

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
        for name in (f"{self.id}.jpg", f"{self.id}.png", "default_card.jpg", "default.jpg", "default.png"):
            candidates.append(COVERS_DIR / name)
            candidates.append(USER_COVERS_DIR / name)
        for p in candidates:
            if p.exists():
                return str(p)
        return None

    def exists(self) -> bool:
        if self.is_prompt():
            return True
        rel = (self.file or "").replace("\\", "/")
        if not rel:
            return False
        return (LORAS_DIR / Path(rel)).exists()

    def comfy_lora_name(self) -> str:
        """Name as ComfyUI folder_paths lists on Windows."""
        rel = (self.file or "").replace("\\", "/").lstrip("/")
        p = LORAS_DIR / Path(rel)
        if p.exists():
            try:
                rel_os = str(p.relative_to(LORAS_DIR))
            except ValueError:
                rel_os = rel
            return rel_os.replace("/", "\\")
        return rel.replace("/", "\\")

    def source_credit(self) -> str:
        src = self.source or {}
        return (src.get("credit") or "").strip()

    def source_url(self) -> str:
        src = self.source or {}
        return (src.get("url") or self.civitai_url or "").strip()

    def label(self) -> str:
        """UI dropdown / gallery choice label."""
        if self.is_prompt():
            prefix = "📝 "
        elif self.nsfw:
            prefix = "🔒 "
        elif self.featured:
            prefix = "⭐ "
        else:
            prefix = ""
        if self.user:
            prefix = "👤 " + prefix.lstrip()
        return f"{prefix}{self.name}"


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


def _style_from_raw(raw: dict, *, default_kind: str = KIND_LORA, user: bool = False) -> Style:
    sid = str(raw["id"])
    kind = (raw.get("kind") or default_kind or KIND_LORA).lower()
    if kind not in (KIND_LORA, KIND_PROMPT):
        kind = default_kind
    cover = raw.get("cover") or f"{sid}.jpg"
    if (COVERS_DIR / f"{sid}.jpg").exists():
        cover = f"{sid}.jpg"
    elif (COVERS_DIR / f"{sid}.png").exists():
        cover = f"{sid}.png"
    primary, cats = _parse_categories(raw)
    src = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    return Style(
        id=sid,
        name=raw.get("name") or sid,
        file=raw.get("file") or "",
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
        kind=kind,
        prompt_prefix=raw.get("prompt_prefix") or "",
        prompt_suffix=raw.get("prompt_suffix") or "",
        negative=raw.get("negative") or "",
        source=dict(src or {}),
        user=user or bool(raw.get("user", False)),
    )


def _read_json_styles(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("styles") if isinstance(data, dict) else data
        return list(items or [])
    except Exception:
        return []


def _load_builtin_lora() -> list[Style]:
    out: list[Style] = []
    for raw in _read_json_styles(STYLES_FILE):
        if "id" not in raw:
            continue
        out.append(_style_from_raw(raw, default_kind=KIND_LORA, user=False))
    return out


def _load_builtin_prompt() -> list[Style]:
    out: list[Style] = []
    for raw in _read_json_styles(PROMPT_STYLES_FILE):
        if "id" not in raw:
            continue
        out.append(_style_from_raw(raw, default_kind=KIND_PROMPT, user=False))
    return out


def _load_user_styles() -> list[Style]:
    ensure_runtime_dirs()
    out: list[Style] = []
    for raw in _read_json_styles(USER_STYLES_FILE):
        if "id" not in raw:
            continue
        out.append(_style_from_raw(raw, default_kind=raw.get("kind") or KIND_PROMPT, user=True))
    return out


def load_styles(
    include_missing: bool = False,
    kind: Optional[str] = None,
) -> list[Style]:
    """Merge builtin LoRA + builtin prompt + user. User id wins over builtin."""
    by_id: dict[str, Style] = {}
    for s in _load_builtin_lora() + _load_builtin_prompt():
        by_id[s.id] = s
    for s in _load_user_styles():
        by_id[s.id] = s  # user override

    styles = list(by_id.values())
    if kind in (KIND_LORA, KIND_PROMPT):
        styles = [s for s in styles if (s.kind or KIND_LORA) == kind]

    filtered: list[Style] = []
    for s in styles:
        if include_missing or s.exists():
            filtered.append(s)

    def sort_key(x: Style):
        primary = x.cats()[0]
        order = CATEGORY_ORDER.index(primary) if primary in CATEGORY_ORDER else 50
        kind_ord = 0 if x.is_lora() else 1
        return (not x.featured, kind_ord, not x.user, order, x.nsfw, x.name)

    filtered.sort(key=sort_key)
    return filtered


def styles_by_id() -> dict[str, Style]:
    return {s.id: s for s in load_styles(include_missing=True)}


def style_choices(
    show_nsfw: bool = True,
    category: Optional[str] = None,
    kind: Optional[str] = None,
) -> list[str]:
    names = ["（无风格）"]
    for s in load_styles(kind=kind):
        if s.nsfw and not show_nsfw:
            continue
        if not s.in_category(category):
            continue
        names.append(s.label())
    return names


def style_categories(show_nsfw: bool = True) -> list[str]:
    found: set[str] = set()
    has_user = False
    for s in load_styles():
        if s.nsfw and not show_nsfw:
            continue
        if s.user:
            has_user = True
        for c in s.cats():
            found.add(c)
    ordered = [c for c in CATEGORY_ORDER if c in found]
    rest = sorted(found - set(ordered))
    base = ["全部", "收藏"]
    if has_user and "我的" not in ordered:
        base.append("我的")
    return base + ordered + rest


def style_kind_filters() -> list[str]:
    return ["全部", "LoRA", "提示词", "收藏"]


def _strip_label(label: str) -> str:
    clean = str(label or "")
    for p in ("⭐ ", "🔒 ", "📝 ", "👤 ", "◆ "):
        clean = clean.replace(p, "")
    clean = clean.strip()
    if " · " in clean:
        # keep last segment only if it looks like old format
        pass
    return clean


def resolve_style_name(label: str) -> Optional[Style]:
    if not label or str(label).startswith("（无"):
        return None
    clean = _strip_label(label)
    for s in load_styles(include_missing=True):
        if s.name == clean or s.id == clean or s.label() == str(label).strip():
            return s
        if _strip_label(s.label()) == clean:
            return s
    return None


# ----- favorites (style ids) -----


def _load_fav_ids() -> list[str]:
    ensure_runtime_dirs()
    if not STYLE_FAVORITES_FILE.exists():
        return []
    try:
        data = json.loads(STYLE_FAVORITES_FILE.read_text(encoding="utf-8"))
        return [str(x) for x in (data.get("ids") or []) if x]
    except Exception:
        return []


def _save_fav_ids(ids: list[str]) -> None:
    ensure_runtime_dirs()
    STYLE_FAVORITES_FILE.write_text(
        json.dumps({"ids": ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_favorite_ids() -> list[str]:
    return _load_fav_ids()


def is_favorite(style_id: str) -> bool:
    return style_id in _load_fav_ids()


def toggle_favorite(style_id: str) -> tuple[bool, str]:
    """Returns (is_now_favorite, message)."""
    sid = (style_id or "").strip()
    if not sid:
        return False, "未选择风格"
    ids = _load_fav_ids()
    if sid in ids:
        ids = [x for x in ids if x != sid]
        _save_fav_ids(ids)
        return False, "已取消收藏"
    ids.insert(0, sid)
    _save_fav_ids(ids[:200])
    return True, "已收藏风格"


# ----- user prompt styles CRUD -----


def _save_user_raw(items: list[dict]) -> None:
    ensure_runtime_dirs()
    USER_STYLES_FILE.write_text(
        json.dumps({"styles": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_user_raw() -> list[dict]:
    return _read_json_styles(USER_STYLES_FILE)


def save_user_prompt_style(
    name: str,
    prompt_prefix: str,
    prompt_suffix: str = "",
    tip: str = "",
    categories: Optional[list[str]] = None,
) -> tuple[bool, str, Optional[Style]]:
    name = (name or "").strip()
    prefix = (prompt_prefix or "").strip()
    if not name:
        return False, "请填写风格名称", None
    if not prefix:
        return False, "提示词为空，没法保存为风格", None
    items = _load_user_raw()
    # update if same name user style
    existing = None
    for raw in items:
        if raw.get("user") and raw.get("name") == name and (raw.get("kind") or KIND_PROMPT) == KIND_PROMPT:
            existing = raw
            break
    sid = (existing or {}).get("id") or f"user_{uuid.uuid4().hex[:8]}"
    entry = {
        "id": sid,
        "name": name,
        "kind": KIND_PROMPT,
        "user": True,
        "file": "",
        "cover": "",
        "tags": ["我的", "提示词"],
        "default_weight": 0.0,
        "trigger": "",
        "nsfw": False,
        "tip": tip or "用户自建提示词风格",
        "featured": False,
        "category": "我的",
        "categories": categories or ["我的", "提示词"],
        "prompt_prefix": prefix,
        "prompt_suffix": (prompt_suffix or "").strip(),
        "source": {"credit": "我的", "url": "", "note": "用户自建"},
        "commercial": "用户自建",
    }
    if existing:
        items = [entry if r.get("id") == sid else r for r in items]
        msg = f"已更新：{name}"
    else:
        items.insert(0, entry)
        msg = f"已保存：{name}"
    items = items[:200]
    _save_user_raw(items)
    return True, msg, _style_from_raw(entry, default_kind=KIND_PROMPT, user=True)


def delete_user_style(style_id: str) -> tuple[bool, str]:
    sid = (style_id or "").strip()
    if not sid:
        return False, "未指定风格"
    items = _load_user_raw()
    found = [r for r in items if r.get("id") == sid]
    if not found:
        return False, "只能删除自己保存的风格（内置不可删）"
    if not found[0].get("user") and not str(sid).startswith("user_"):
        return False, "只能删除用户风格"
    items = [r for r in items if r.get("id") != sid]
    _save_user_raw(items)
    # drop fav
    favs = [x for x in _load_fav_ids() if x != sid]
    _save_fav_ids(favs)
    return True, "已删除用户风格"


def list_lora_file_choices(limit: int = 200) -> list[str]:
    """Relative paths under models/loras for advanced custom LoRA."""
    if not LORAS_DIR.exists():
        return []
    out: list[str] = []
    for p in sorted(LORAS_DIR.rglob("*.safetensors")):
        try:
            rel = str(p.relative_to(LORAS_DIR)).replace("/", "\\")
        except ValueError:
            continue
        # 优先 zimage 子目录
        out.append(rel)
        if len(out) >= limit:
            break
    # put zimage\\ first
    out.sort(key=lambda s: (0 if s.lower().startswith("zimage") else 1, s.lower()))
    return out


def save_user_lora_style(
    name: str,
    lora_file: str,
    trigger: str = "",
    default_weight: float = 0.85,
    category: str = "我的",
    tip: str = "",
) -> tuple[bool, str, Optional[Style]]:
    """高级：把本地 LoRA 文件登记为我的风格。"""
    name = (name or "").strip()
    lora_file = (lora_file or "").strip().replace("/", "\\")
    if not name:
        return False, "请填写风格名称", None
    if not lora_file:
        return False, "请选择 LoRA 文件", None
    path = LORAS_DIR / Path(lora_file.replace("\\", "/"))
    if not path.exists():
        return False, f"找不到文件：{lora_file}", None
    w = float(default_weight or 0.85)
    w = max(0.1, min(1.5, w))
    items = _load_user_raw()
    sid = f"user_lora_{uuid.uuid4().hex[:8]}"
    entry = {
        "id": sid,
        "name": name,
        "kind": "lora",
        "user": True,
        "file": lora_file,
        "cover": "",
        "tags": ["我的", "自定义"],
        "default_weight": w,
        "trigger": (trigger or "").strip(),
        "nsfw": False,
        "tip": tip or "用户自定义 LoRA",
        "featured": False,
        "category": category or "我的",
        "categories": [category or "我的", "我的"],
        "source": {"credit": "我的", "url": "", "note": "用户添加"},
        "commercial": "用户自建",
    }
    items.insert(0, entry)
    _save_user_raw(items[:200])
    return True, f"已添加：{name}", _style_from_raw(entry, default_kind=KIND_LORA, user=True)


def catalog_summary() -> dict[str, Any]:
    all_s = load_styles(include_missing=True)
    present = [s for s in all_s if s.exists()]
    lora_n = sum(1 for s in present if s.is_lora())
    prompt_n = sum(1 for s in present if s.is_prompt())
    by_cat: dict[str, int] = {}
    for s in present:
        for c in s.cats():
            by_cat[c] = by_cat.get(c, 0) + 1
    return {
        "catalog_total": len(all_s),
        "available": len(present),
        "lora_count": lora_n,
        "prompt_count": prompt_n,
        "missing": [s.name for s in all_s if not s.exists()],
        "nsfw_available": sum(1 for s in present if s.nsfw),
        "by_category": by_cat,
        "friend_credits": sorted(
            {
                (s.source_credit() or "")
                for s in present
                if s.is_prompt() and s.source_credit() and s.source_credit() not in ("达芬七", "我的")
            }
        ),
    }


def friend_credits_markdown() -> str:
    """Bullets for About tab."""
    lines: list[str] = []
    seen: set[str] = set()
    for s in load_styles(include_missing=True):
        if not s.is_prompt():
            continue
        credit = s.source_credit()
        url = s.source_url()
        if not credit or credit in ("达芬七", "我的"):
            continue
        key = credit + "|" + url
        if key in seen:
            continue
        seen.add(key)
        if url:
            lines.append(f"- **{credit}** — [{url}]({url})")
        else:
            lines.append(f"- **{credit}**")
    return "\n".join(lines) if lines else "- （暂无外源提示词风格）"
