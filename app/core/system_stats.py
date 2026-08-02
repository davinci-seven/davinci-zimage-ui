"""Host + ComfyUI resource stats for the status bar + VRAM size tips."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import requests
import yaml

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None


DEFAULT_COMFY_PORT = 7777

# Fallback if defaults.yaml missing tiers
_DEFAULT_VRAM_TIERS = [
    {"max_vram_gb": 6, "soft": 512, "hard": 768},
    {"max_vram_gb": 8, "soft": 1024, "hard": 1280},
    {"max_vram_gb": 12, "soft": 1280, "hard": 1440},
    {"max_vram_gb": 16, "soft": 1440, "hard": 1600},
    {"max_vram_gb": 24, "soft": 1600, "hard": 2048},
    {"max_vram_gb": 999, "soft": 2048, "hard": 2048},
]


def comfy_system_stats(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT) -> dict[str, Any]:
    try:
        r = requests.get(f"http://{host}:{port}/system_stats", timeout=1.5)
        if r.status_code == 200:
            return r.json() or {}
    except Exception:
        pass
    return {}


def collect_stats(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT) -> dict[str, Any]:
    out: dict[str, Any] = {
        "comfy_online": False,
        "cpu_percent": None,
        "ram_used_gb": None,
        "ram_total_gb": None,
        "vram_used_gb": None,
        "vram_total_gb": None,
        "gpu_name": None,
        "torch_vram_used_gb": None,
        "torch_vram_total_gb": None,
    }

    if psutil:
        try:
            out["cpu_percent"] = psutil.cpu_percent(interval=0.0)
            vm = psutil.virtual_memory()
            out["ram_used_gb"] = round(vm.used / (1024**3), 1)
            out["ram_total_gb"] = round(vm.total / (1024**3), 1)
        except Exception:
            pass

    data = comfy_system_stats(host, port)
    if data:
        out["comfy_online"] = True
        devices = data.get("devices") or []
        if devices:
            d0 = devices[0]
            out["gpu_name"] = d0.get("name")
            # comfy reports vram in bytes often
            vram_total = d0.get("vram_total") or d0.get("torch_vram_total")
            vram_free = d0.get("vram_free") or d0.get("torch_vram_free")
            if vram_total:
                total_gb = vram_total / (1024**3)
                free_gb = (vram_free or 0) / (1024**3)
                out["vram_total_gb"] = round(total_gb, 1)
                out["vram_used_gb"] = round(max(0.0, total_gb - free_gb), 1)

    if torch and torch.cuda.is_available():
        try:
            free, total = torch.cuda.mem_get_info(0)
            out["torch_vram_total_gb"] = round(total / (1024**3), 1)
            out["torch_vram_used_gb"] = round((total - free) / (1024**3), 1)
            if out["vram_total_gb"] is None:
                out["vram_total_gb"] = out["torch_vram_total_gb"]
                out["vram_used_gb"] = out["torch_vram_used_gb"]
            if not out["gpu_name"]:
                out["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception:
            pass

    return out


def get_vram_total_gb(
    host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT
) -> Optional[float]:
    """Total CUDA VRAM in GB, or None if unknown."""
    s = collect_stats(host, port)
    v = s.get("vram_total_gb")
    if v is not None:
        return float(v)
    return None


def _load_vram_cfg() -> dict[str, Any]:
    try:
        from .paths import DEFAULTS_FILE

        path = Path(DEFAULTS_FILE)
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return data.get("vram_long_edge") or {}
    except Exception:
        pass
    return {}


def recommended_long_edge_limits(
    vram_gb: Optional[float],
    backend: str = "fp8",
) -> tuple[int, int]:
    """Return (soft_max_long_edge, hard_max_long_edge) for detected VRAM.

    soft = suggested; hard = may work but risk OOM.
    GGUF +bonus, BF16 -penalty (from defaults.yaml).
    """
    cfg = _load_vram_cfg()
    tiers = cfg.get("tiers") or _DEFAULT_VRAM_TIERS
    soft, hard = 1024, 1280
    if vram_gb is None:
        # unknown GPU: conservative 8G-ish
        soft, hard = 1024, 1280
    else:
        for t in tiers:
            if float(vram_gb) <= float(t.get("max_vram_gb", 999)):
                soft = int(t.get("soft", 1024))
                hard = int(t.get("hard", soft + 256))
                break
        else:
            last = tiers[-1] if tiers else {"soft": 2048, "hard": 2048}
            soft = int(last.get("soft", 2048))
            hard = int(last.get("hard", 2048))

    b = (backend or "fp8").lower()
    if b == "gguf":
        bonus = int(cfg.get("gguf_bonus", 128))
        soft = min(2048, soft + bonus)
        hard = min(2048, hard + bonus)
    elif b in ("bf16", "fp16", "default"):
        pen = int(cfg.get("bf16_penalty", 128))
        soft = max(512, soft - pen)
        hard = max(soft, hard - pen)

    return soft, hard


def size_vram_advice(
    width: int,
    height: int,
    *,
    backend: str = "fp8",
    host: str = "127.0.0.1",
    port: int = DEFAULT_COMFY_PORT,
    vram_gb: Optional[float] = None,
) -> dict[str, Any]:
    """Assess custom / preview size against VRAM.

    Returns level: ok | warn | danger | unknown
    """
    if vram_gb is None:
        vram_gb = get_vram_total_gb(host, port)
    long_edge = max(int(width or 0), int(height or 0))
    soft, hard = recommended_long_edge_limits(vram_gb, backend)

    if vram_gb is None:
        level = "unknown"
        msg = (
            f"未能检测 CUDA 显存。当前 {width}×{height}（长边 {long_edge}）。"
            f"8G 卡建议长边 ≤ {soft}，更大可能 OOM。"
        )
    elif long_edge <= soft:
        level = "ok"
        msg = (
            f"当前检测约 {vram_gb:g} GB 显存；建议长边 ≤ {soft}。"
            f"本次 {width}×{height} 在建议范围内。"
        )
    elif long_edge <= hard:
        level = "warn"
        msg = (
            f"当前检测约 {vram_gb:g} GB 显存；建议长边 ≤ {soft}。"
            f"本次 {width}×{height} 偏大，可能 OOM，可先试更小尺寸。"
        )
    else:
        level = "danger"
        msg = (
            f"当前检测约 {vram_gb:g} GB 显存；建议长边 ≤ {soft}（可试上限约 {hard}）。"
            f"本次 {width}×{height} 明显超标，极易 OOM。"
        )

    return {
        "level": level,
        "message": msg,
        "vram_gb": vram_gb,
        "soft": soft,
        "hard": hard,
        "long_edge": long_edge,
        "width": int(width),
        "height": int(height),
    }


def format_vram_size_warning_html(advice: dict[str, Any]) -> str:
    """HTML banner for advanced size area / size badge."""
    level = advice.get("level") or "unknown"
    msg = advice.get("message") or ""
    cls = {
        "ok": "ok",
        "warn": "warn",
        "danger": "danger",
        "unknown": "unknown",
    }.get(level, "unknown")
    return f'<div class="dv-vram-tip {cls}">{msg}</div>'


def format_stats_html(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT) -> str:
    s = collect_stats(host, port)
    online = s["comfy_online"]
    badge = "在线" if online else "离线"
    badge_cls = "ok" if online else "bad"
    cpu = f"{s['cpu_percent']:.0f}%" if s.get("cpu_percent") is not None else "—"
    ram = (
        f"{s['ram_used_gb']}/{s['ram_total_gb']} GB"
        if s.get("ram_used_gb") is not None
        else "—"
    )
    if s.get("vram_used_gb") is not None and s.get("vram_total_gb") is not None:
        vram = f"{s['vram_used_gb']}/{s['vram_total_gb']} GB"
        vratio = min(100, int(100 * s["vram_used_gb"] / max(0.1, s["vram_total_gb"])))
    else:
        vram = "—"
        vratio = 0
    gpu = s.get("gpu_name") or "GPU"
    # shorten long gpu names
    if len(gpu) > 28:
        gpu = gpu[:26] + "…"

    return f"""
    <div class="sysbar">
      <div class="pill"><span class="dot {badge_cls}"></span>引擎 {badge}</div>
      <div class="pill">CPU {cpu}</div>
      <div class="pill">内存 {ram}</div>
      <div class="pill">显存 {vram}
        <span class="mini-bar"><i style="width:{vratio}%"></i></span>
      </div>
      <div class="pill dim">{gpu}</div>
    </div>
    """


def queue_progress(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT) -> dict[str, Any]:
    """Best-effort queue snapshot from ComfyUI."""
    try:
        r = requests.get(f"http://{host}:{port}/queue", timeout=1.5)
        if r.status_code == 200:
            q = r.json() or {}
            running = q.get("queue_running") or []
            pending = q.get("queue_pending") or []
            return {
                "running": len(running),
                "pending": len(pending),
                "busy": bool(running or pending),
            }
    except Exception:
        pass
    return {"running": 0, "pending": 0, "busy": False}
