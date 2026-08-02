"""用本地 Z-Image（无 LoRA）为「提示词灵感」出小封面。

依赖：Comfy 7777 在线。

用法：
  python app/tools/gen_inspo_covers.py
  python app/tools/gen_inspo_covers.py --only inspo_r01,dv_neon_thriller
  python app/tools/gen_inspo_covers.py --force --limit 20
  python app/tools/gen_inspo_covers.py --quality "512 · 省显存"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.comfy_client import is_comfy_ready  # noqa: E402
from core.generate import txt2img  # noqa: E402
from core.inspirations import load_inspirations  # noqa: E402
from core.paths import COVERS_DIR  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", type=str, default="", help="comma ids")
    ap.add_argument("--limit", type=int, default=0, help="max to generate (0=all)")
    ap.add_argument("--quality", type=str, default="512 · 省显存")
    ap.add_argument("--aspect", type=str, default="正方形 1:1")
    ap.add_argument("--mode", type=str, default="标准 FP8（推荐）")
    ap.add_argument("--skip-text-cards", action="store_true", default=True,
                    help="skip regenerating if cover is already a photo (>80KB)")
    args = ap.parse_args()

    if not is_comfy_ready():
        print("Comfy not ready on :7777 — start 启动.bat first")
        return 2

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    items = load_inspirations()
    if only:
        items = [x for x in items if x.id in only]
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = 0
    for i, ins in enumerate(items, 1):
        if ins.user:
            continue
        cover_name = ins.cover or f"{ins.id}.jpg"
        dest = COVERS_DIR / cover_name
        # 达芬七精选已有真图则默认跳过
        if dest.exists() and not args.force:
            # 512 缩略 JPEG 常 <80KB，用 20KB 区分「真出图」与极小占位
            if dest.stat().st_size > 20_000:
                print(f"[{i}/{len(items)}] SKIP {ins.id} (exists {dest.stat().st_size}B)")
                skip += 1
                continue
        prompt = (ins.prompt or "").strip()
        if not prompt:
            print(f"[{i}/{len(items)}] SKIP {ins.id} (empty prompt)")
            skip += 1
            continue
        # 封面用短主体，避免过长
        short = prompt if len(prompt) < 280 else prompt[:280]
        print(f"[{i}/{len(items)}] GEN {ins.id} / {ins.name} ...", flush=True)
        try:
            path = txt2img(
                prompt_text=short,
                aspect_label=args.aspect,
                quality_label=args.quality,
                style1=None,
                weight1=0.0,
                style2=None,
                weight2=0.0,
                seed=-1,
                model_mode_label=args.mode,
                save_to_gallery=False,
            )
            from PIL import Image

            im = Image.open(path).convert("RGB")
            im.thumbnail((512, 640))
            tmp = dest.with_suffix(".tmp.jpg")
            im.save(tmp, quality=88)
            tmp.replace(dest)
            print(f"  OK -> {dest.name}", flush=True)
            ok += 1
        except Exception as e:
            print(f"  FAIL {ins.id}: {e}", flush=True)
            fail += 1
    print(f"done ok={ok} skip={skip} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
