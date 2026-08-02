"""Path resolution for 达芬七 · Z-Image pack."""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
PACK_ROOT = APP_DIR.parent
WORKFLOWS_DIR = APP_DIR / "workflows"
BRAND_FILE = APP_DIR / "brand" / "links.yaml"
DEFAULTS_FILE = APP_DIR / "config" / "defaults.yaml"
STYLES_FILE = PACK_ROOT / "assets" / "styles" / "styles.json"
PROMPT_STYLES_FILE = PACK_ROOT / "assets" / "styles" / "prompt_styles.json"  # legacy
INSPIRATIONS_FILE = PACK_ROOT / "assets" / "prompts" / "inspirations.json"
COVERS_DIR = PACK_ROOT / "assets" / "styles" / "covers"
PROMPTS_FILE = PACK_ROOT / "assets" / "prompts" / "presets.json"
# legacy fallback
PROMPTS_FILE_LEGACY = PACK_ROOT / "assets" / "prompts" / "portrait_presets.json"

# 用户数据（不要塞进 ComfyUI/output）
USERDATA = PACK_ROOT / "userdata"
GALLERY_DIR = USERDATA / "gallery"
PACK_OUTPUT = USERDATA / "exports"  # Gradio 可访问的导出副本
SETTINGS_USER = USERDATA / "settings.yaml"
USER_STYLES_FILE = USERDATA / "styles_user.json"
STYLE_FAVORITES_FILE = USERDATA / "style_favorites.json"
USER_COVERS_DIR = USERDATA / "covers"


def _resolve_engine_root() -> Path:
    env = os.environ.get("ENGINE_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "ComfyUI" / "main.py").exists():
            return p

    packaged = PACK_ROOT / "engine"
    if (packaged / "ComfyUI" / "main.py").exists():
        return packaged.resolve()

    sibling = PACK_ROOT.parent / "ComfyUI-zimage"
    if (sibling / "ComfyUI" / "main.py").exists():
        return sibling.resolve()

    return packaged.resolve()


ENGINE_ROOT = _resolve_engine_root()
COMFY_ROOT = ENGINE_ROOT / "ComfyUI"
COMFY_OUTPUT = COMFY_ROOT / "output"
COMFY_INPUT = COMFY_ROOT / "input"
LORAS_DIR = COMFY_ROOT / "models" / "loras"
DIFFUSION_DIR = COMFY_ROOT / "models" / "diffusion_models"


def ensure_runtime_dirs() -> None:
    COMFY_OUTPUT.mkdir(parents=True, exist_ok=True)
    COMFY_INPUT.mkdir(parents=True, exist_ok=True)
    USERDATA.mkdir(parents=True, exist_ok=True)
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    PACK_OUTPUT.mkdir(parents=True, exist_ok=True)
    USER_COVERS_DIR.mkdir(parents=True, exist_ok=True)


def engine_status() -> dict:
    return {
        "pack_root": str(PACK_ROOT),
        "engine_root": str(ENGINE_ROOT),
        "comfy_main": str(COMFY_ROOT / "main.py"),
        "engine_ok": (COMFY_ROOT / "main.py").exists(),
        "loras_dir": str(LORAS_DIR),
        "gallery_dir": str(GALLERY_DIR),
        "default_unet_exists": (
            DIFFUSION_DIR / "z-image" / "z-image-turbo-fp8-e4m3fn_量化版_低显加速.safetensors"
        ).exists(),
    }
