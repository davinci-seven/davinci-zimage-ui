"""Minimal ComfyUI client: queue a workflow, follow real progress, fetch that job's image."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from PIL import Image
from tqdm import tqdm

from .paths import COMFY_OUTPUT

ProgressCb = Optional[Callable[[float, str], None]]


DEFAULT_COMFY_PORT = 7777


def _api_base(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT) -> str:
    return f"http://{host}:{port}"


def is_comfy_ready(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT, timeout: float = 2.0) -> bool:
    try:
        r = requests.get(f"{_api_base(host, port)}/system_stats", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _friendly_error(raw: str) -> str:
    low = raw.lower()
    if "out of memory" in low or "cuda oom" in low:
        return "显存不足（OOM）。请改用「720 · 快」或 GGUF 档，并只选一个风格。"
    if "lora" in low and ("not" in low or "exist" in low):
        return f"风格文件没找到，请确认 LoRA 还在 models/loras 里。\n原始信息：{raw[:300]}"
    return f"ComfyUI 生成失败：{raw[:400]}"


def _format_node_errors(payload: dict) -> str:
    """Turn Comfy's /prompt validation payload into something a user can act on."""
    lines: list[str] = []
    err = payload.get("error")
    if isinstance(err, dict):
        msg = err.get("message") or err.get("type") or ""
        detail = err.get("details") or ""
        lines.append(f"{msg} {detail}".strip())
    node_errors = payload.get("node_errors") or {}
    if isinstance(node_errors, dict):
        for node_id, info in node_errors.items():
            if not isinstance(info, dict):
                continue
            title = info.get("class_type") or f"节点 {node_id}"
            for e in info.get("errors") or []:
                msg = e.get("message", "")
                detail = e.get("details", "")
                lines.append(f"· [{title}] {msg} {detail}".strip())
    return "\n".join(x for x in lines if x) or json.dumps(payload, ensure_ascii=False)[:400]


def history_item(host: str, port: int, prompt_id: str) -> Optional[dict]:
    if not prompt_id:
        return None
    try:
        r = requests.get(f"{_api_base(host, port)}/history/{prompt_id}", timeout=3)
        if r.status_code != 200:
            return None
        payload = r.json() or {}
        item = payload.get(prompt_id) or next(iter(payload.values()), None)
        return item if isinstance(item, dict) else None
    except Exception:
        return None


def _item_error(item: dict) -> Optional[str]:
    status = item.get("status") or {}
    state = str(status.get("status_str") or "").lower()
    if state not in {"error", "failed"}:
        return None
    raw = str(status.get("messages") or item.get("messages") or "未知错误")
    return _friendly_error(raw)


def _item_images(item: dict, output_dir: Path) -> list[Path]:
    """Resolve exactly the images this prompt produced (never a neighbour's file)."""
    paths: list[Path] = []
    outputs = item.get("outputs") or {}
    if not isinstance(outputs, dict):
        return paths
    for node_out in outputs.values():
        if not isinstance(node_out, dict):
            continue
        for img in node_out.get("images") or []:
            name = img.get("filename")
            if not name:
                continue
            if str(img.get("type") or "output") != "output":
                continue  # skip temp previews
            sub = img.get("subfolder") or ""
            p = output_dir / sub / name if sub else output_dir / name
            paths.append(p)
    return paths


def _wait_readable(path: Path, tries: int = 16) -> bool:
    for _ in range(tries):
        try:
            with Image.open(path) as im:
                im.load()
            return True
        except Exception:
            time.sleep(0.35)
    return False


class _ProgressSocket:
    """Real step progress from ComfyUI's /ws. Degrades to no-op if the socket fails."""

    def __init__(self, host: str, port: int, client_id: str):
        self._ws = None
        try:
            from websockets.sync.client import connect  # type: ignore

            self._ws = connect(
                f"ws://{host}:{port}/ws?clientId={client_id}",
                open_timeout=4,
                max_size=None,
            )
        except Exception as e:  # pragma: no cover - environment dependent
            print(f"[comfy] ws progress unavailable ({e}); falling back to polling", flush=True)

    def poll(self, prompt_id: str) -> tuple[Optional[float], Optional[str]]:
        """Return (fraction 0-1 of sampling steps, error text) since last call."""
        if self._ws is None:
            return None, None
        frac: Optional[float] = None
        err: Optional[str] = None
        for _ in range(64):
            try:
                raw = self._ws.recv(timeout=0.15)
            except Exception:
                break
            if not isinstance(raw, str):
                continue  # binary preview frames
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            data = msg.get("data") or {}
            if prompt_id and data.get("prompt_id") not in (None, prompt_id):
                continue
            mtype = msg.get("type")
            if mtype == "progress":
                mx = float(data.get("max") or 0)
                if mx > 0:
                    frac = float(data.get("value") or 0) / mx
            elif mtype == "execution_error":
                err = _friendly_error(
                    str(data.get("exception_message") or data.get("exception_type") or "未知错误")
                )
        return frac, err

    def close(self) -> None:
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass


def interrupt_comfy(host: str = "127.0.0.1", port: int = DEFAULT_COMFY_PORT) -> bool:
    """Ask ComfyUI to interrupt the current job (best-effort)."""
    for path in ("/interrupt", "/api/interrupt"):
        try:
            r = requests.post(f"{_api_base(host, port)}{path}", timeout=3)
            if r.status_code < 500:
                return True
        except Exception:
            continue
    return False


def free_comfy_memory(
    host: str = "127.0.0.1",
    port: int = DEFAULT_COMFY_PORT,
    unload_models: bool = True,
    free_memory: bool = True,
) -> bool:
    """Use ComfyUI's native memory endpoint; the next run will reload unloaded models."""
    try:
        r = requests.post(
            f"{_api_base(host, port)}/free",
            json={
                "unload_models": bool(unload_models),
                "free_memory": bool(free_memory),
            },
            timeout=5,
        )
        return r.status_code < 400
    except Exception:
        return False


def queue_prompt(
    workflow: dict[str, Any],
    host: str = "127.0.0.1",
    port: int = DEFAULT_COMFY_PORT,
    client_id: Optional[str] = None,
) -> dict:
    payload: dict[str, Any] = {"prompt": workflow}
    if client_id:
        payload["client_id"] = client_id

    last: Optional[requests.Response] = None
    for path in ("/prompt", "/api/prompt"):
        try:
            r = requests.post(f"{_api_base(host, port)}{path}", json=payload, timeout=60)
        except requests.RequestException as e:
            raise RuntimeError(f"连不上引擎（{host}:{port}）：{e}") from e
        if r.status_code == 404:
            last = r
            continue
        if r.status_code >= 400:
            try:
                detail = _format_node_errors(r.json() or {})
            except Exception:
                detail = (r.text or "")[:400]
            raise RuntimeError(f"引擎拒绝了这次任务：\n{detail}")
        return r.json()

    text = (last.text if last is not None else "")[:200]
    raise RuntimeError(f"引擎没有 /prompt 接口，版本可能不兼容。{text}")


def wait_for_result(
    prompt_id: str,
    output_dir: Path,
    timeout_sec: int = 300,
    poll: float = 0.4,
    on_progress: ProgressCb = None,
    host: str = "127.0.0.1",
    port: int = DEFAULT_COMFY_PORT,
    sock: Optional[_ProgressSocket] = None,
) -> Optional[Path]:
    deadline = time.time() + timeout_sec
    t0 = time.time()
    last_n = 0
    step_frac = 0.0
    pbar = tqdm(
        total=100,
        desc="生成",
        unit="%",
        ncols=88,
        leave=True,
        dynamic_ncols=True,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    )
    try:
        while time.time() < deadline:
            if sock is not None:
                frac, ws_err = sock.poll(prompt_id)
                if ws_err:
                    raise RuntimeError(ws_err)
                if frac is not None:
                    step_frac = frac

            item = history_item(host, port, prompt_id)
            if item:
                err = _item_error(item)
                if err:
                    raise RuntimeError(err)
                images = _item_images(item, output_dir)
                if images:
                    if last_n < 100:
                        pbar.update(100 - last_n)
                        last_n = 100
                    if on_progress:
                        on_progress(1.0, "完成")
                    for p in images:
                        if p.exists() and _wait_readable(p):
                            return p
                    return images[0] if images[0].exists() else None

            # 0.10 提交 → 0.90 采样（真实步数）→ 之后是 VAE 解码/保存
            if step_frac > 0:
                soft = 0.10 + step_frac * 0.80
                phase = f"生成中… {int(step_frac * 100)}%"
            else:
                elapsed = time.time() - t0
                soft = min(0.10, 0.02 + elapsed / 30.0 * 0.08)
                phase = "加载模型 / 排队中…"
            if step_frac >= 1.0:
                phase = "正在解码并保存"
            n = int(soft * 100)
            if n > last_n:
                pbar.update(n - last_n)
                last_n = n
            if on_progress:
                on_progress(soft, phase)
            time.sleep(poll)
        return None
    finally:
        pbar.close()


def run_workflow(
    workflow: dict[str, Any],
    host: str = "127.0.0.1",
    port: int = DEFAULT_COMFY_PORT,
    timeout_sec: int = 300,
    output_dir: Optional[Path] = None,
    on_progress: ProgressCb = None,
) -> Path:
    out = output_dir or COMFY_OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    if not is_comfy_ready(host, port):
        raise RuntimeError(
            "引擎还没准备好。请先双击「启动.bat」，等状态栏显示「在线」后再生成。"
        )
    if on_progress:
        on_progress(0.02, "提交任务…")

    client_id = uuid.uuid4().hex
    sock = _ProgressSocket(host, port, client_id)
    try:
        queued = queue_prompt(workflow, host, port, client_id=client_id)
        prompt_id = str(queued.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError("引擎没有返回任务号，无法确认这次出图结果。")
        result = wait_for_result(
            prompt_id,
            out,
            timeout_sec=timeout_sec,
            on_progress=on_progress,
            host=host,
            port=port,
            sock=sock,
        )
    finally:
        sock.close()

    if result is None:
        raise TimeoutError(
            f"等待出图超时（{timeout_sec}s）。可改用「720 · 快」档，并关闭占显存的程序。"
        )
    return result
