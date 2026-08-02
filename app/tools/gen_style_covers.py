"""用本地 ComfyUI + 各风格 LoRA 生成封面预览图（不用网页/Civitai 图）。

依赖：Comfy 已在 7777 就绪；用一键出图包 engine 的 python 运行。

用法：
  python app/tools/gen_style_covers.py
  python app/tools/gen_style_covers.py --only snap,skin,aesthetic
  python app/tools/gen_style_covers.py --force
  python app/tools/gen_style_covers.py --force --quality \"720 · 快\" --mode \"标准 FP8（推荐）\"
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.comfy_client import is_comfy_ready  # noqa: E402
from core.generate import txt2img  # noqa: E402
from core.paths import COVERS_DIR  # noqa: E402
from core.styles import load_styles  # noqa: E402

# 封面向提示词：短主体 + 能看出该 LoRA 气质（触发词由 txt2img 自动注入）
PROMPT_BY_ID = {
    "snap": "东亚年轻女性室内自拍半身，手机直闪轻微过曝，碎发与自然瑕疵，日常出租屋背景，candid 抓拍感",
    "skin": "东亚女性面部特写，清晰毛孔与皮肤纹理，柔和侧窗光，写真摄影，无美颜磨皮",
    "aesthetic": "时尚杂志人像，东亚女性高级感妆容，胶片柔调，优雅半身构图，干净背景",
    "realistic": "东亚年轻女性半身像，自然素颜，窗边柔光，极致写实人像摄影，生活感",
    "detail": "精致人像特写，发丝与衣料纹理清晰，柔光，高细节但仍像照片",
    "atmosphere": "夜色窗边女性侧脸，电影感体积光，冷暖对比，浅景深氛围",
    "nvdi": "华丽东方服饰的女帝气质女性，金饰与丝绸，庄严半身像",
    "cartoon3d": "3D 卡通少女半身，圆润立体渲染，干净背景，可爱表情",
    "disney": "DisneyIZT, original princess-like young woman, fairytale gown with soft silk folds, delicate tiara, large expressive eyes, round soft features 3D animation style, warm magical castle-light glow, gentle smile, half body portrait, clean dreamy background, not any real Disney character",
    "instant": "拍立得风格人像，暖色偏色与柔闪，生活感，白色边框感构图",
    "nice": "东亚美女写实半身，干净五官自然笑容，商业写真柔光",
    "toloveru": "二次元美少女半身，鲜艳配色，动漫插画构图，清晰主体",
    "anime": "精细二次元少女半身，清晰线稿与干净上色，动漫插画",
    "ink": "中国水墨写意女性侧影，宣纸肌理与留白，墨晕层次",
    "linework": "干净黑白线稿少女半身，清晰轮廓，白底，无上色",
    "couture": "高定时装秀造型，华美礼服半身，影棚轮廓光，高级时尚摄影",
    "oot": "街头穿搭全身展示，时尚 lookbook，城市背景虚化",
    "fantasy80": "1980 年代奇幻海报女战士，高饱和复古印刷感，披风与金属",
    "moonlight": "月光下的少女与猫咪氛围插画，冷蓝月光，安静夜色",
    "glowing": "暗调霓虹发光人像，赛博暗部与高光边缘，戏剧感",
    "granblue": "日系手游立绘感角色半身，鲜明配色，清晰剪影",
    "moriime": "柔和插画风少女半身，清新配色，温柔光线",
    "lenovo": "清爽写实人像半身，轻微质感增强，干净背景",
    # 成人向：偏 fine-art / 杂志美感，避免丑怪直白
    "nsfw_core": "fine art nude photography, elegant East Asian woman half body, soft Rembrandt lighting, tasteful museum aesthetic, beautiful natural pose, smooth skin, dark velvet background, artistic and sensual not vulgar",
    "nsfwmaster": "high-end boudoir portrait, elegant woman in silk robe half-slipped shoulder, soft window light, film grain, refined makeup, magazine cover composition, sensual atmosphere, beautiful face, artistic not explicit",
    "oiled": "studio beauty close-up, glossy healthy skin on collarbone and shoulder, soft beauty dish lighting, elegant jewelry, fashion editorial, sensual texture, refined not vulgar",
    "b3tter": "artistic nude silhouette against warm gradient light, graceful body curve, soft haze, fine art photography, elegant museum mood, tasteful and beautiful",
    "steep": "fashion illustration style woman, elegant exaggerated silhouette, chic outfit, clean pastel background, high fashion editorial beauty, stylish and polished",
    "afrobull": "力量感角色肖像半身，鲜明风格，强轮廓光",
    "prison": "戏剧性角色肖像，电影构图，硬侧光",
    "luneva": "电影感女性肖像，体积光与浅景深，胶片颗粒，半身",
    "cyberhd": "超清晰人像特写，锐利发丝与皮肤细节，高级质感",
    "detail_slider": "高细节人像半身，发丝与布料纹理清晰，柔光",
    "detail_daemon": "极致细节人像，锐利但不硬，发丝与皮肤层次",
    "melancholy": "忧郁氛围女性肖像，冷色调，艺术摄影，浅景深",
    "analog2000": "2000年代家用摄像机抓拍感，东亚年轻女性半身，暖色偏色轻微颗粒，生活室内",
    "grainscape": "胶片颗粒写实人像，东亚女性，柔和日光，细颗粒与真实肤色",
    "amateur_aes": "43stet1c, beautiful young East Asian woman 22 years old, candid aesthetic portrait, soft golden hour light, glossy magazine vibe, elegant half body, natural makeup, wind-blown hair, shallow depth of field, high end amateur photography, flattering angle, stunning face, clean background bokeh",
    "cinematic": "zy_cinematic, stunning East Asian woman 25 years old, cinematic film still, dramatic Rembrandt side light, shallow depth of field, anamorphic bokeh, elegant evening dress, beautiful face looking slightly off-camera, rich color grade teal and orange, movie poster quality half body, glamorous and sharp",
    "charsheet": "CharacterDesignIZT, character design sheet of a stylish girl, full body front, headshot, clean white background",
    "neurocore": "in the style of cksc, anime girl half body, sci-fi shadow circuit aesthetic, dark elegant illustration",
    "comic_tome": "Bradhamel art style, comic book cover portrait of a heroine, bold inks, dramatic lighting",
    "anime_art": "Bradhamel art style, beautiful anime girl half body portrait, clean colors, detailed eyes",
    "watercolor": "VarcoterolV7 art style, watercolor painting of a quiet lakeside landscape, soft pigments, paper texture",
    "midjz": "cinematic portrait of an East Asian woman, beautiful lighting, midjourney aesthetic, half body",
    "retro90": "retro_scifi_90s, retro_artstyle, 90s anime girl half body, cyberpunk neon, cel shading nostalgia",
    "nudeart": "fine art nude photography portrait, elegant pose, soft Rembrandt lighting, museum aesthetic, beautiful skin, half body, not vulgar",
    "teenymood": "东亚年轻女性半身，小情绪氛围，安静表情，柔和窗光，生活感写真",
}

DEFAULT_PROMPT = "东亚年轻女性半身像，清晰主体，柔和光线，适合作为风格展示封面"


def wait_comfy(timeout=180) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if is_comfy_ready():
            return True
        print("waiting comfy...")
        time.sleep(2)
    return False


def main():
    ap = argparse.ArgumentParser(description="本地 LoRA 生成风格封面")
    ap.add_argument("--only", type=str, default="", help="comma-separated style ids")
    ap.add_argument("--force", action="store_true", help="已有封面也强制重生成")
    ap.add_argument("--quality", type=str, default="720 · 快")
    ap.add_argument("--aspect", type=str, default="竖屏 3:4")
    ap.add_argument("--mode", type=str, default="标准 FP8（推荐）")
    args = ap.parse_known_args()[0]

    if not wait_comfy():
        print("ERROR: ComfyUI not ready on :7777")
        sys.exit(1)

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    styles = load_styles(include_missing=False)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    ok, fail, skip = 0, 0, 0
    for s in styles:
        if only and s.id not in only:
            continue
        if not s.exists():
            print(f"SKIP {s.id} (LoRA file missing)")
            skip += 1
            continue

        cover_path = COVERS_DIR / f"{s.id}.jpg"
        if cover_path.exists() and not args.force and cover_path.stat().st_size > 40_000:
            print(f"SKIP {s.id} (cover exists, use --force to redo)")
            skip += 1
            continue

        prompt = PROMPT_BY_ID.get(s.id, DEFAULT_PROMPT)
        print(f"GEN {s.id} / {s.name}  weight={s.default_weight} ...", flush=True)
        try:
            path = txt2img(
                prompt_text=prompt,
                aspect_label=args.aspect,
                quality_label=args.quality,
                style1=s,
                weight1=float(s.default_weight),
                style2=None,
                weight2=0.0,
                seed=-1,
                model_mode_label=args.mode,
                save_to_gallery=False,
            )
            from PIL import Image

            im = Image.open(path).convert("RGB")
            im.thumbnail((768, 1024))
            # 原子写入，避免半截文件
            tmp = cover_path.with_suffix(".tmp.jpg")
            im.save(tmp, quality=90)
            tmp.replace(cover_path)
            print(f"  OK -> {cover_path.name} from {Path(path).name}", flush=True)
            ok += 1
        except Exception as e:
            print(f"  FAIL {s.id}: {e}", flush=True)
            fail += 1

    print(f"done ok={ok} fail={fail} skip={skip}")
    sys.exit(0 if fail == 0 else 2)


if __name__ == "__main__":
    main()
