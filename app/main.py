"""
达芬七 · Z-Image 一键出图包 — Gradio 前端入口
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure app/ is on sys.path
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ui.app_ui import build_demo, _css  # noqa: E402

FS_JS_PATH = APP_DIR / "ui" / "dv_fs.js"


def _load_fs_js() -> str:
    try:
        return FS_JS_PATH.read_text(encoding="utf-8")
    except Exception:
        return "console.warn('[dv] dv_fs.js missing');"


def main():
    parser = argparse.ArgumentParser(description="达芬七 · Z-Image")
    parser.add_argument("--server_port", type=int, default=int(os.environ.get("GRADIO_SERVER_PORT", 8888)))
    parser.add_argument("--server_name", type=str, default="127.0.0.1")
    parser.add_argument("--share", action="store_true")
    args, _unknown = parser.parse_known_args()

    from core.paths import (  # noqa: E402
        COMFY_OUTPUT,
        COVERS_DIR,
        GALLERY_DIR,
        PACK_OUTPUT,
        PACK_ROOT,
        USERDATA,
        BRAND_FILE,
    )
    try:
        import yaml

        brand = yaml.safe_load(BRAND_FILE.read_text(encoding="utf-8")) or {}
        ver = brand.get("version", "?")
    except Exception:
        ver = "?"
    print("=" * 56, flush=True)
    print(f"  达芬七 · Z-Image  UI  v{ver}", flush=True)
    print(f"  PACK_ROOT = {PACK_ROOT}", flush=True)
    print(f"  app_ui    = {APP_DIR / 'ui' / 'app_ui.py'}", flush=True)
    print(f"  端口      = {args.server_name}:{args.server_port}", flush=True)
    print("=" * 56, flush=True)

    demo = build_demo()
    demo.queue(default_concurrency_limit=1)

    fs_js = _load_fs_js()
    head_snip = f"<script id='dv-fs-js'>\n{fs_js}\n</script>"
    js_fn = f"() => {{\n{fs_js}\n}}"
    # CSS 走 launch 注入，避免只靠 HTML <style> 被结构吃掉
    base_css = _css()

    # Gradio 6 只允许返回 allowed_paths / CWD 内的文件；
    # 生成结果会拷到 userdata/exports，并允许 Comfy output 作兜底。
    allowed = [
        str(PACK_ROOT),
        str(USERDATA),
        str(PACK_OUTPUT),
        str(COVERS_DIR),
        str(GALLERY_DIR),
        str(COMFY_OUTPUT),
    ]

    demo.launch(
        server_name=args.server_name,
        server_port=args.server_port,
        share=args.share,
        inbrowser=False,
        show_error=True,
        allowed_paths=allowed,
        css=base_css,
        js=js_fn,
        head=head_snip,
    )


if __name__ == "__main__":
    main()
