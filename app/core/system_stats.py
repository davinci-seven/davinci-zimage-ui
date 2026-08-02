"""Host + ComfyUI resource stats for the status bar."""
from __future__ import annotations

import time
from typing import Any

import requests

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None


DEFAULT_COMFY_PORT = 7777


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
