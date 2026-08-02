"""User settings persistence (theme, etc.)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import SETTINGS_USER, ensure_runtime_dirs

_DEFAULTS: dict[str, Any] = {
    "theme": "editorial",
    "show_nsfw": False,
    # 导出文件名前缀，Comfy SaveImage 用；默认中性名，可在设置里改
    "filename_prefix": "davincilab",
}


def sanitize_filename_prefix(raw: Any, default: str = "davincilab") -> str:
    """Allow letters/digits/_/- only; empty → default."""
    s = str(raw or "").strip()
    if not s:
        return default
    # strip path-ish chars; keep simple ASCII for cross-tool compatibility
    cleaned = "".join(c for c in s if c.isalnum() or c in ("_", "-", "."))
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return default
    # Comfy may append counters; keep prefix short
    return cleaned[:64]


def load_settings() -> dict[str, Any]:
    ensure_runtime_dirs()
    data = dict(_DEFAULTS)
    if SETTINGS_USER.exists():
        try:
            loaded = yaml.safe_load(SETTINGS_USER.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data.update({k: v for k, v in loaded.items() if k in _DEFAULTS or True})
        except Exception:
            pass
    # normalize theme
    from ui.themes import THEMES

    if data.get("theme") not in THEMES:
        data["theme"] = "editorial"
    data["show_nsfw"] = bool(data.get("show_nsfw", False))
    data["filename_prefix"] = sanitize_filename_prefix(
        data.get("filename_prefix"), _DEFAULTS["filename_prefix"]
    )
    return data


def save_settings(**kwargs: Any) -> dict[str, Any]:
    ensure_runtime_dirs()
    data = load_settings()
    data.update(kwargs)
    if "filename_prefix" in data:
        data["filename_prefix"] = sanitize_filename_prefix(data.get("filename_prefix"))
    SETTINGS_USER.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_USER.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return data


def get_theme() -> str:
    return str(load_settings().get("theme") or "editorial")


def set_theme(theme_key: str) -> str:
    from ui.themes import THEMES  # 皮肤清单只有一处真相，加新皮肤不用改这里

    key = theme_key if theme_key in THEMES else "editorial"
    save_settings(theme=key)
    return key


def get_filename_prefix() -> str:
    return sanitize_filename_prefix(load_settings().get("filename_prefix"))


def set_filename_prefix(prefix: str) -> str:
    clean = sanitize_filename_prefix(prefix)
    save_settings(filename_prefix=clean)
    return clean
