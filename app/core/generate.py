"""Build workflows and run generation."""
from __future__ import annotations

import json
import random
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from .comfy_client import run_workflow
from .paths import (
    COMFY_OUTPUT,
    DEFAULTS_FILE,
    PACK_OUTPUT,
    WORKFLOWS_DIR,
    ensure_runtime_dirs,
)
from .history import GenRecord, save_generation
from .settings import get_filename_prefix
from .styles import Style


def _copy_to_pack_output(src: Path | str) -> Path:
    """Copy Comfy output into pack userdata/exports so Gradio can serve it.

    Gradio 6 blocks files outside allowed_paths / CWD; Comfy writes under
    engine/ComfyUI/output which is often a sibling path — always return a
    path under PACK_ROOT.
    """
    ensure_runtime_dirs()
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"生成图不存在: {src}")
    PACK_OUTPUT.mkdir(parents=True, exist_ok=True)
    dest = PACK_OUTPUT / src.name
    # unique if same name already there
    if dest.exists() and dest.resolve() != src.resolve():
        stem, suf = dest.stem, dest.suffix
        n = 1
        while dest.exists():
            dest = PACK_OUTPUT / f"{stem}_{n}{suf}"
            n += 1
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest.resolve()


def load_defaults() -> dict:
    with open(DEFAULTS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_workflow(name: str) -> dict[str, Any]:
    path = WORKFLOWS_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def model_mode_choices() -> list[str]:
    d = load_defaults()
    return list((d.get("model_modes") or {"标准 FP8（推荐）": {}}).keys())


def get_model_mode(label: str) -> dict:
    d = load_defaults()
    modes = d.get("model_modes") or {}
    if label in modes:
        return modes[label]
    # fallback first
    if modes:
        return next(iter(modes.values()))
    return {
        "backend": "fp8",
        "workflow": "txt2img.json",
        "unet_name": (d.get("model") or {}).get("unet_name"),
        "weight_dtype": (d.get("model") or {}).get("weight_dtype"),
        "clip_name": (d.get("model") or {}).get("clip_name"),
    }


def normalize_quality_label(label: str) -> str:
    """Map legacy 省显存/均衡/高清 → 新分辨率档名."""
    d = load_defaults()
    presets = d.get("quality_presets") or {}
    if label in presets:
        return label
    legacy = d.get("quality_legacy_map") or {}
    if label in legacy and legacy[label] in presets:
        return legacy[label]
    # fuzzy: "1024" in label
    for k in presets:
        if str(label) in k or k.startswith(str(label)):
            return k
    return "1024 · 推荐" if "1024 · 推荐" in presets else next(iter(presets), label)


def calculate_size(aspect: str, long_edge: int) -> tuple[int, int]:
    w_r, h_r = map(int, aspect.split(":"))
    if w_r >= h_r:
        width = int(long_edge)
        height = max(64, int(long_edge * h_r / w_r))
    else:
        height = int(long_edge)
        width = max(64, int(long_edge * w_r / h_r))
    width = width - (width % 8)
    height = height - (height % 8)
    return width, height


def _inject_model(wf: dict, mode: dict, defaults: dict) -> None:
    base = defaults.get("model") or {}
    unet = mode.get("unet_name") or base.get("unet_name")
    dtype = mode.get("weight_dtype") or base.get("weight_dtype")
    clip = mode.get("clip_name") or base.get("clip_name")
    vae = base.get("vae_name") or "z-image-qwen.safetensors"

    for node in wf.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        ct = node.get("class_type")
        if ct == "UNETLoader":
            if unet:
                inputs["unet_name"] = unet
            if dtype:
                inputs["weight_dtype"] = dtype
        elif ct == "UnetLoaderGGUF":
            if unet:
                inputs["unet_name"] = unet
        elif ct in ("CLIPLoader", "CLIPLoaderGGUF"):
            if clip:
                inputs["clip_name"] = clip
        elif ct == "VAELoader" and vae:
            inputs["vae_name"] = vae


def _apply_filename_prefix(wf: dict, mode_suffix: str = "") -> None:
    """Set SaveImage filename_prefix from user settings (default davincilab)."""
    base = get_filename_prefix()
    prefix = f"{base}_{mode_suffix}" if mode_suffix else base
    for node in wf.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "SaveImage":
            continue
        inputs = node.setdefault("inputs", {})
        inputs["filename_prefix"] = prefix


def _apply_loras(wf: dict, node_id: str, loras: list[tuple[Style, float]]) -> None:
    """Apply at most one LoRA via native Comfy LoraLoader (node 23).

    rgthree stack is fine when present, but native LoraLoader is more reliable
    for path resolution and model+clip wiring on Z-Image. No LoRA → bypass 23.
    """
    loras = list(loras[:1])

    def _bypass_lora_node() -> None:
        # KSampler / CLIPTextEncode 直接接 UNet + CLIP
        if "4" in wf and "inputs" in wf["4"]:
            wf["4"]["inputs"]["model"] = ["1", 0]
        if "5" in wf and "inputs" in wf["5"]:
            wf["5"]["inputs"]["clip"] = ["2", 0]
        # 创造性仍接 prompt 节点 5
        if "24" in wf and "inputs" in wf["24"]:
            wf["24"]["inputs"]["conditioning"] = ["5", 0]
        print("[lora] bypass (no style)", flush=True)

    if not loras:
        _bypass_lora_node()
        return

    style, weight = loras[0]
    lora_path = style.comfy_lora_name()
    w = float(weight)
    if not style.exists():
        print(f"[lora] ERROR file missing: {lora_path!r} — skip LoRA", flush=True)
        _bypass_lora_node()
        return

    # 原生 LoraLoader：model+clip 都挂上，风格 LoRA 更稳
    wf[node_id] = {
        "inputs": {
            "lora_name": lora_path,
            "strength_model": w,
            "strength_clip": w,
            "model": ["1", 0],
            "clip": ["2", 0],
        },
        "class_type": "LoraLoader",
        "_meta": {"title": "LoRA"},
    }
    if "4" in wf and "inputs" in wf["4"]:
        wf["4"]["inputs"]["model"] = [node_id, 0]
    if "5" in wf and "inputs" in wf["5"]:
        wf["5"]["inputs"]["clip"] = [node_id, 1]
    print(
        f"[lora] LoraLoader name={lora_path!r} strength={w} exists=True "
        f"style={style.name!r}",
        flush=True,
    )


def _compose_prompt(user_prompt: str, loras: list[tuple[Style, float]]) -> str:
    """Inject style trigger keywords in front of user prompt (does not replace it)."""
    triggers = []
    for style, _ in loras:
        t = (style.trigger or "").strip()
        if not t:
            continue
        # avoid duplicate injection
        if t.lower() in user_prompt.lower():
            continue
        # also skip if main trigger token already present
        first = t.split(",")[0].strip()
        if first and first.lower() in user_prompt.lower():
            continue
        triggers.append(t)
    if triggers:
        return ", ".join(triggers) + ", " + user_prompt
    return user_prompt


def _apply_creativity(wf: dict, creativity: int) -> None:
    """SeedVarianceEnhancer (node 24) on the positive conditioning."""
    level = max(0, min(100, int(creativity or 0)))
    if "24" not in wf:
        return
    inputs = wf["24"].setdefault("inputs", {})
    if level > 0:
        inputs["randomize_percent"] = level
        inputs["strength"] = 20
        inputs["seed"] = int(time.time() * 1000) % 100_000_000 + random.randint(0, 9999)
    else:
        inputs["randomize_percent"] = 0
        inputs["strength"] = 0
    # keep positive path through enhancer when present
    if "4" in wf and "inputs" in wf["4"]:
        wf["4"]["inputs"]["positive"] = ["24", 0]


def txt2img(
    prompt_text: str,
    aspect_label: str,
    quality_label: str,
    style1: Optional[Style],
    weight1: float,
    style2: Optional[Style],
    weight2: float,
    seed: int = -1,
    model_mode_label: str = "标准 FP8（推荐）",
    on_progress=None,
    style1_label: str = "（无风格）",
    style2_label: str = "（无风格）",
    weight1_label: str = "中",
    weight2_label: str = "轻",
    save_to_gallery: bool = True,
    creativity: int = 0,
) -> Path:
    defaults = load_defaults()
    mode = get_model_mode(model_mode_label)
    aspects = defaults.get("aspect_ratios") or {}
    aspect = aspects.get(aspect_label, "1:1")
    q_label = normalize_quality_label(quality_label)
    q = (defaults.get("quality_presets") or {}).get(q_label) or {
        "long_edge": 1024,
        "steps": 9,
        "cfg": 1.0,
    }
    # GGUF: force smaller default edge if user picked 高清 by accident
    if mode.get("backend") == "gguf" and int(q["long_edge"]) > 1024:
        q = {**q, "long_edge": 1024}

    loras: list[tuple[Style, float]] = []
    if style1:
        loras.append((style1, float(weight1)))
    # 第二风格：仅在显式传入且与第一不同时启用；UI 默认清空，避免双 LoRA 卡死
    if style2 and style1 and style2.id != style1.id:
        # 暂时禁用第二槽（8GB 稳定优先）；需要时再开
        print(
            f"[lora] ignore style2={style2.name!r} (single-lora mode)",
            flush=True,
        )

    # GGUF 也可挂 LoRA（用户实测可行）；路径用标准注入即可
    wf_name = mode.get("workflow") or "txt2img.json"
    wf = load_workflow(wf_name)
    _inject_model(wf, mode, defaults)

    text = _compose_prompt(prompt_text.strip(), loras)
    if loras:
        names = " + ".join(f"{s.name}@{w:.2f}" for s, w in loras)
        trig = "；触发词已注入" if any((s.trigger or "").strip() for s, _ in loras) else ""
        print(f"[lora] apply {names}{trig}", flush=True)
        print(f"[lora] prompt head: {text[:120]!r}...", flush=True)
        if on_progress:
            on_progress(0.1, f"应用风格：{names}{trig}")
    else:
        print("[lora] no style resolved — generating base model only", flush=True)
    width, height = calculate_size(aspect, int(q["long_edge"]))
    steps = int(q["steps"])
    cfg = float(q["cfg"])
    if seed is None or int(seed) < 0:
        seed = int(time.time()) % 2_000_000_000 + random.randint(0, 9999)

    if "5" in wf:
        wf["5"]["inputs"]["text"] = text
    if "4" in wf:
        wf["4"]["inputs"]["seed"] = int(seed)
        wf["4"]["inputs"]["steps"] = steps
        wf["4"]["inputs"]["cfg"] = cfg
    if "7" in wf:
        wf["7"]["inputs"]["width"] = width
        wf["7"]["inputs"]["height"] = height
        wf["7"]["inputs"]["batch_size"] = 1  # multi via sequential gens (8G 友好)
    _apply_loras(wf, "23", loras)
    _apply_creativity(wf, creativity)
    suffix = "GGUF" if mode.get("backend") == "gguf" else ""
    _apply_filename_prefix(wf, suffix)

    host = (defaults.get("comfy") or {}).get("host", "127.0.0.1")
    port = int((defaults.get("comfy") or {}).get("port", 7777))
    timeout = int((defaults.get("comfy") or {}).get("timeout_sec", 300))

    result = run_workflow(
        wf,
        host=host,
        port=port,
        timeout_sec=timeout,
        output_dir=COMFY_OUTPUT,
        on_progress=on_progress,
    )
    out = _copy_to_pack_output(result)
    if save_to_gallery:
        try:
            save_generation(
                out,
                GenRecord(
                    id="",
                    created_at="",
                    image_path="",
                    prompt=prompt_text.strip(),
                    mode="txt2img",
                    model_mode=model_mode_label,
                    quality=q_label,
                    aspect=aspect_label,
                    style1=style1.name if style1 else (style1_label or "（无风格）"),
                    weight1=weight1_label or _weight_label_from_value(weight1),
                    style2=style2.name if style2 else (style2_label or "（无风格）"),
                    weight2=weight2_label or _weight_label_from_value(weight2),
                    seed=int(seed),
                ),
            )
        except Exception as e:
            print("history save failed:", e)
    print(f"[gen] pack export: {out}", flush=True)
    return out


def _weight_label_from_value(w: float) -> str:
    if w <= 0.7:
        return "轻 (0.6)"
    if w >= 0.95:
        return "重 (1.0)"
    return "中 (0.85)"


def preview_size(aspect_label: str, quality_label: str) -> tuple[int, int]:
    defaults = load_defaults()
    aspects = defaults.get("aspect_ratios") or {}
    aspect = aspects.get(aspect_label, "1:1")
    q_label = normalize_quality_label(quality_label)
    q = (defaults.get("quality_presets") or {}).get(q_label) or {"long_edge": 1024}
    return calculate_size(aspect, int(q["long_edge"]))
