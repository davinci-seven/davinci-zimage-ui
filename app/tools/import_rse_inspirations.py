"""从 AI-Factory RSE / Multiverse 精选池导入「提示词灵感」。

原则：只收已精选/定稿案例，封面直接用原图缩略，不滥竽充数。

来源：
  - multiverse_image_6h：60 分类精选 + 20 黑马（中文 prompt）
  - rse-24h/curated：60 风格 × 每风格 top1–2
  - rse-4h-v2：每风格 1 张（多样材质/工艺）

用法：
  python app/tools/import_rse_inspirations.py
  python app/tools/import_rse_inspirations.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image

PACK = Path(__file__).resolve().parents[2]
INSPO_JSON = PACK / "assets" / "prompts" / "inspirations.json"
COVERS = PACK / "assets" / "styles" / "covers"

MV = Path(r"F:\ClaudeCode\AI-Factory-Outputs\explore\multiverse_image_6h_20260802")
RSE24 = Path(r"F:\ClaudeCode\AI-Factory-Outputs\rse-24h")
RSE4H = Path(r"F:\ClaudeCode\AI-Factory-Outputs\rse-4h-v2-20260802")

# multiverse 分类 → 中文类
MV_CAT = {
    "01_anime": "二次元",
    "02_multi_person": "多人叙事",
    "03_occupation": "职业人像",
    "04_nature": "自然风光",
    "05_city_arch": "城市建筑",
    "06_ecommerce_white": "产品商业",
    "07_campaign": "产品商业",
    "08_food": "美食",
    "09_poster": "海报平面",
    "10_picturebook": "绘本",
    "11_surreal": "超现实",
    "12_eastern": "东方视觉",
}

# rse-24h family → 中文类
RSE24_CAT = {
    "era_medium": "画面气质",
    "film_cinema": "电影剧照",
    "light_mood": "光影氛围",
    "material": "材质质感",
    "print_paper": "印刷纸艺",
    "subculture": "亚文化",
}

RSE4H_CAT = {
    "fashion_construction": "时尚结构",
    "folk_graphic": "民俗图形",
    "handcraft_object": "手作器物",
    "historic_photo_process": "古典摄影",
    "obsolete_digital": "复古数码",
    "organic_surface": "有机表面",
    "scientific_imaging": "科学影像",
    "spatial_stage": "空间舞台",
}

# 保留的本地气质卡（原达芬七精选封面，改类名，不删图）
KEEP_DV = [
    "dv_cel_80s",
    "dv_ps1_lowpoly",
    "dv_art_nouveau_glass",
    "dv_early_web_ui",
    "dv_moonlight_silhouette",
    "dv_crackled_gold",
    "dv_neon_thriller",
    "dv_clay_stopmotion",
]


def _thumb(src: Path, dest: Path, max_side: int = 640) -> bool:
    try:
        im = Image.open(src).convert("RGB")
        im.thumbnail((max_side, max_side))
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp.jpg")
        im.save(tmp, quality=88, optimize=True)
        tmp.replace(dest)
        return dest.exists() and dest.stat().st_size > 8_000
    except Exception as e:
        print(f"  thumb fail {src.name}: {e}")
        return False


def _load_existing() -> list[dict]:
    if not INSPO_JSON.exists():
        return []
    data = json.loads(INSPO_JSON.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("inspirations") or [])


def _short_name(text: str, limit: int = 18) -> str:
    t = re.sub(r"\s+", "", (text or "").strip())
    if len(t) <= limit:
        return t or "未命名"
    return t[: limit - 1] + "…"


def import_multiverse(out: list[dict], used_ids: set[str]) -> int:
    if not MV.exists():
        print("SKIP multiverse (path missing)")
        return 0
    # job_id / prefix → prompt record
    by_key: dict[str, dict] = {}
    for p in (MV / "prompts").glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        jid = str(d.get("job_id") or p.stem)
        by_key[jid] = d
        by_key[p.stem] = d
        # also index lower / without round prefix variants
        by_key[jid.lower()] = d

    n = 0
    # 60 categorized
    cat_root = MV / "06_finalists" / "60_categorized"
    for folder in sorted(cat_root.iterdir() if cat_root.exists() else []):
        if not folder.is_dir():
            continue
        cat = MV_CAT.get(folder.name, "画面灵感")
        for img in sorted(folder.glob("*.png")):
            # 00_b_0216_s0_00001_.png → B_0216_...
            m = re.match(r"\d+_([a-z])_(\d+)_s(\d+)_", img.stem, re.I)
            rec = None
            if m:
                letter, num, seedn = m.group(1).upper(), m.group(2), m.group(3)
                # try several key shapes
                for key in list(by_key.keys()):
                    if f"_{num}_" in key and key.upper().startswith(letter):
                        rec = by_key[key]
                        break
                    if num in key and f"s{seedn}" in key.lower():
                        rec = by_key[key]
                        break
                # glob prompts
                if rec is None:
                    hits = list((MV / "prompts").glob(f"*{num}*s{seedn}*.json"))
                    if hits:
                        rec = json.loads(hits[0].read_text(encoding="utf-8"))
            if not rec:
                # fallback: filename use_case only
                prompt = ""
                use = img.stem
            else:
                prompt = (rec.get("prompt_zh") or rec.get("prompt") or "").strip()
                use = (rec.get("use_case") or rec.get("route") or img.stem).strip()

            if not prompt or len(prompt) < 12:
                continue
            sid = f"mv_{folder.name}_{img.stem[:24]}"
            sid = re.sub(r"[^a-zA-Z0-9_]+", "_", sid)[:48]
            if sid in used_ids:
                continue
            cover_name = f"{sid}.jpg"
            if not _thumb(img, COVERS / cover_name):
                continue
            name = _short_name(str(use).replace("_", " "), 16)
            out.append(
                {
                    "id": sid,
                    "name": name,
                    "kind": "inspiration",
                    "cover": cover_name,
                    "tags": [cat, "Multiverse精选"],
                    "featured": False,
                    "category": cat,
                    "categories": [cat],
                    "prompt": prompt,
                    "tip": f"Multiverse-6H 定稿 · {cat}",
                    "source": {
                        "credit": "Multiverse-6H 精选",
                        "url": "https://x.com/davinci_seven",
                        "note": f"explore/multiverse_image_6h · {folder.name}",
                    },
                    "commercial": "达芬七本地探索精选",
                }
            )
            used_ids.add(sid)
            n += 1

    # blackhorse 20
    bh = MV / "06_finalists" / "20_blackhorse"
    for img in sorted(bh.glob("*.png") if bh.exists() else []):
        # bh_00_c_0030_s0_00001_.png
        m = re.search(r"([bc])_(\d+)_s(\d+)", img.stem, re.I)
        rec = None
        if m:
            num, seedn = m.group(2), m.group(3)
            hits = list((MV / "prompts").glob(f"*{num}*s{seedn}*.json"))
            if hits:
                rec = json.loads(hits[0].read_text(encoding="utf-8"))
        prompt = (rec.get("prompt_zh") if rec else "") or ""
        if not prompt or len(prompt) < 12:
            continue
        use = (rec.get("use_case") if rec else None) or "黑马精选"
        cat = "超现实"
        route = (rec.get("route") if rec else "") or ""
        for k, v in MV_CAT.items():
            if k.split("_", 1)[-1] in route or route.endswith(k):
                cat = v
                break
        if "eastern" in route.lower():
            cat = "东方视觉"
        if "papercraft" in route.lower() or "picture" in route.lower():
            cat = "绘本"
        if "campaign" in route.lower():
            cat = "产品商业"
        if "multi" in route.lower() or "narrative" in route.lower():
            cat = "多人叙事"
        sid = f"mv_bh_{img.stem[:28]}"
        sid = re.sub(r"[^a-zA-Z0-9_]+", "_", sid)[:48]
        if sid in used_ids:
            continue
        cover_name = f"{sid}.jpg"
        if not _thumb(img, COVERS / cover_name):
            continue
        out.append(
            {
                "id": sid,
                "name": _short_name(str(use), 16),
                "kind": "inspiration",
                "cover": cover_name,
                "tags": [cat, "黑马"],
                "featured": True,
                "category": cat,
                "categories": [cat, "黑马精选"],
                "prompt": prompt.strip(),
                "tip": "Multiverse 黑马精选 · 出彩案例",
                "source": {
                    "credit": "Multiverse-6H 黑马",
                    "url": "https://x.com/davinci_seven",
                    "note": "06_finalists/20_blackhorse",
                },
                "commercial": "达芬七本地探索精选",
            }
        )
        used_ids.add(sid)
        n += 1
    print(f"multiverse +{n}")
    return n


def import_rse24(out: list[dict], used_ids: set[str], per_style: int = 2) -> int:
    idx_path = RSE24 / "curated" / "index.json"
    if not idx_path.exists():
        print("SKIP rse-24h (no index)")
        return 0
    index = json.loads(idx_path.read_text(encoding="utf-8"))
    n = 0
    for it in index:
        family = it.get("family") or ""
        style_id = it.get("style_id") or ""
        title_zh = it.get("title_zh") or style_id
        dest = Path(it.get("dest") or "")
        if not dest.exists():
            continue
        cat = RSE24_CAT.get(family, "画面气质")
        picks = sorted(dest.glob("0*_*.json"))[:per_style]
        for j, meta_p in enumerate(picks, 1):
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except Exception:
                continue
            score = float(meta.get("score") or 0)
            # 只收高分；top1 放宽，top2 更严
            if j == 1 and score < 70:
                continue
            if j >= 2 and score < 100:
                continue
            png = dest / (meta.get("export_name") or meta_p.with_suffix(".png").name)
            if not png.exists():
                cand = list(dest.glob(meta_p.stem + "*.png")) or list(
                    dest.glob(f"{meta_p.stem[:20]}*.png")
                )
                png = cand[0] if cand else None
            if not png or not png.exists():
                continue
            prompt = (meta.get("prompt") or "").strip()
            if not prompt or len(prompt) < 20:
                continue
            # 中文可用提示：风格名 + 原英文主体（ZIT 双语均可）
            subject = (meta.get("subject") or "").strip()
            zh_prompt = (
                f"{title_zh}风格。"
                f"{subject}。"
                f"{meta.get('style_phrase') or ''}。"
                "高细节，清晰主体，无文字无水印无标志。"
            ).replace("。。", "。").strip()
            # 优先用原配方（与封面一致）作为主 prompt，中文作 tip 补充
            sid = f"r24_{style_id}_{j:02d}"
            sid = re.sub(r"[^a-zA-Z0-9_]+", "_", sid)[:48]
            if sid in used_ids:
                continue
            cover_name = f"{sid}.jpg"
            if not _thumb(png, COVERS / cover_name):
                continue
            name = title_zh if j == 1 else f"{title_zh} ·{j}"
            out.append(
                {
                    "id": sid,
                    "name": name[:20],
                    "kind": "inspiration",
                    "cover": cover_name,
                    "tags": [cat, title_zh, "RSE-24h"],
                    "featured": j == 1 and score >= 110,
                    "category": cat,
                    "categories": [cat],
                    "prompt": prompt,  # 与封面一致的原配方
                    "tip": f"RSE-24h 精选 score={score:.0f} · {zh_prompt[:80]}",
                    "source": {
                        "credit": f"RSE-24h · {title_zh}",
                        "url": "https://x.com/davinci_seven",
                        "note": f"curated/{family}/{style_id}",
                    },
                    "commercial": "达芬七 RSE 精选",
                }
            )
            used_ids.add(sid)
            n += 1
    print(f"rse-24h +{n}")
    return n


def import_rse4h(out: list[dict], used_ids: set[str], per_style: int = 1) -> int:
    img_root = RSE4H / "images"
    # find nested run folder
    if not img_root.exists():
        print("SKIP rse-4h")
        return 0
    runs = [p for p in img_root.iterdir() if p.is_dir()]
    if not runs:
        print("SKIP rse-4h empty")
        return 0
    base = runs[0]
    # prompts for subject/prompt
    prompt_dirs = list(
        (RSE4H / "runs").glob("*/prompts")
    )
    by_prefix: dict[str, dict] = {}
    for pd in prompt_dirs:
        for jf in pd.glob("*.json"):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            pref = d.get("filename_prefix") or d.get("job_id") or jf.stem
            by_prefix[str(pref)] = d
            by_prefix[jf.stem] = d

    n = 0
    # 只挑「图文件最大」的一张/风格，粗筛清晰度
    for family_dir in sorted(base.iterdir()):
        if not family_dir.is_dir():
            continue
        family = family_dir.name
        cat = RSE4H_CAT.get(family, "画面气质")
        for style_dir in sorted(family_dir.iterdir()):
            if not style_dir.is_dir():
                continue
            style_id = style_dir.name
            pngs = sorted(
                style_dir.glob("*.png"),
                key=lambda p: p.stat().st_size,
                reverse=True,
            )
            if not pngs:
                continue
            # 取最大的 1 张，且 > 400KB 才算过关
            picked = [p for p in pngs if p.stat().st_size > 400_000][:per_style]
            if not picked:
                continue
            for j, png in enumerate(picked, 1):
                # match prompt: rse2_00058_chainmail-lace_00001_.png
                rec = None
                m = re.match(r"(rse2_\d+_[a-z0-9\-]+)_", png.stem, re.I)
                if m:
                    rec = by_prefix.get(m.group(1))
                if rec is None:
                    for k, v in by_prefix.items():
                        if style_id in k or style_id in str(v.get("style_id", "")):
                            if str(v.get("seq", "")) in png.name or True:
                                rec = v
                                # prefer matching style
                                if v.get("style_id") == style_id:
                                    break
                prompt = (rec.get("prompt") if rec else "") or ""
                if not prompt:
                    # synthesize
                    subj = (rec.get("subject") if rec else "") or "精致主体"
                    phrase = (rec.get("style_phrase") if rec else "") or style_id
                    prompt = (
                        f"{subj}, {phrase}, highly detailed, clear silhouette, "
                        "masterpiece, best quality, no text, no watermark"
                    )
                title = style_id.replace("-", " ").title()
                # Chinese display name from style_id
                name_zh = {
                    "chainmail-lace": "锁子甲蕾丝",
                    "glass-bead-reflective": "玻璃珠反光",
                    "needle-felt": "羊毛毡",
                    "paper-quilling": "衍纸",
                    "cyanotype": "蓝晒",
                    "daguerreotype": "达盖尔银版",
                    "gameboy-camera": "GameBoy 相机",
                    "crt-shadow-mask": "CRT 荫罩",
                    "mother-of-pearl": "珍珠母贝",
                    "thermal-imaging": "热成像",
                    "toy-theatre": "玩具剧场",
                    "chinese-window-cut": "中式窗花",
                    "korean-minhwa": "朝鲜民画",
                    "platinum-print": "铂金印相",
                    "butterfly-scale": "蝶翅鳞粉",
                    "electron-micrograph": "电镜显微",
                    "mirror-maze": "镜面迷宫",
                    "planetarium-projection": "天象投影",
                    "wet-plate-collodion": "湿版火棉胶",
                    "autochrome-lumiere": "奥托色",
                    "biofluorescence": "生物荧光",
                    "diatom-glass": "硅藻玻璃",
                    "mycelium-grown": "菌丝生长",
                    "cloisonne-enamel": "景泰蓝",
                    "wood-marquetry": "木镶嵌",
                    "otomi-embroidery": "奥托米刺绣",
                    "peranakan-tile": "娘惹瓷砖",
                    "teletext": "图文电视",
                    "vector-display": "矢量显示",
                    "early-cgi-1987": "早期 CGI",
                    "schlieren-flow": "纹影气流",
                    "carousel-stage": "旋转木马舞台",
                    "puppet-box": "木偶匣",
                    "department-window": "百货橱窗",
                    "inflatable-architecture": "充气建筑",
                    "miniature-cutaway": "微缩剖面",
                    "laser-cut-textile": "激光镂空织物",
                    "thermopleated": "热定型褶皱",
                    "ticket-collage": "票根拼贴",
                    "rope-knot-structure": "绳结结构",
                    "paper-yarn": "纸纱",
                    "transparent-boning": "透明骨架",
                    "madhubani": "马杜巴尼",
                    "mexican-tin-retablo": "墨西哥锡圣画",
                    "petrykivka": "彼得里基夫卡",
                    "wycinanki": "波兰剪纸",
                    "carved-wax": "雕蜡",
                    "pierced-ceramic": "镂空陶瓷",
                    "repousse-metal": "锤揲金属",
                    "salt-dough": "盐陶",
                    "collotype": "珂罗版",
                    "gum-bichromate": "树胶重铬酸盐",
                    "photogravure": "照相凹版",
                    "demoscene-plasma": "Demo 等离子",
                    "dotmatrix-lcd": "点阵液晶",
                    "ega-dither": "EGA 抖动",
                    "biofilm-iridescence": "生物膜虹彩",
                    "coral-porcelain": "珊瑚瓷",
                    "lichen-map": "地衣地图",
                    "seedpod-lattice": "荚果晶格",
                    "oscilloscope-trace": "示波器轨迹",
                    "polarized-microscopy": "偏光显微",
                    "thin-film-interference": "薄膜干涉",
                    "xray-crystallography": "X 射线晶体",
                }.get(style_id, title)
                sid = f"r4_{style_id}_{j:02d}"
                sid = re.sub(r"[^a-zA-Z0-9_]+", "_", sid)[:48]
                if sid in used_ids:
                    continue
                cover_name = f"{sid}.jpg"
                if not _thumb(png, COVERS / cover_name):
                    continue
                out.append(
                    {
                        "id": sid,
                        "name": name_zh[:20],
                        "kind": "inspiration",
                        "cover": cover_name,
                        "tags": [cat, name_zh, "RSE-4h"],
                        "featured": False,
                        "category": cat,
                        "categories": [cat],
                        "prompt": prompt.strip(),
                        "tip": f"RSE-4h-v2 · {cat} · 大图精选",
                        "source": {
                            "credit": f"RSE-4h · {name_zh}",
                            "url": "https://x.com/davinci_seven",
                            "note": f"rse-4h-v2/{family}/{style_id}",
                        },
                        "commercial": "达芬七 RSE 精选",
                    }
                )
                used_ids.add(sid)
                n += 1
    print(f"rse-4h +{n}")
    return n


def keep_local_dv(out: list[dict], used_ids: set[str], old: list[dict]) -> int:
    by_id = {str(x.get("id")): x for x in old}
    n = 0
    for sid in KEEP_DV:
        raw = by_id.get(sid)
        if not raw:
            continue
        # 封面若存在
        cover = raw.get("cover") or f"{sid}.png"
        if not (COVERS / cover).exists():
            # try alt
            for ext in (".png", ".jpg", ".jpeg"):
                if (COVERS / f"{sid}{ext}").exists():
                    cover = f"{sid}{ext}"
                    break
        entry = dict(raw)
        entry["category"] = "画面气质"
        entry["categories"] = ["画面气质"]
        entry["featured"] = False
        entry["tags"] = list(
            {*(entry.get("tags") or []), "画面气质", "经典卡"}
        )
        # 去掉达芬七精选标签
        entry["tags"] = [t for t in entry["tags"] if t not in ("达芬七精选", "封面")]
        entry["tip"] = entry.get("tip") or "经典气质卡 · 点选填入提示词"
        entry["source"] = entry.get("source") or {
            "credit": "达芬七",
            "url": "https://x.com/davinci_seven",
        }
        if sid in used_ids:
            continue
        out.append(entry)
        used_ids.add(sid)
        n += 1
    print(f"keep dv +{n}")
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rse24-per", type=int, default=2)
    ap.add_argument("--rse4-per", type=int, default=1)
    args = ap.parse_args()

    old = _load_existing()
    out: list[dict] = []
    used: set[str] = set()

    keep_local_dv(out, used, old)
    import_multiverse(out, used)
    import_rse24(out, used, per_style=args.rse24_per)
    import_rse4h(out, used, per_style=args.rse4_per)

    # 去重 prompt 过短 / 无封面
    cleaned = []
    for it in out:
        if not (it.get("prompt") or "").strip():
            continue
        cov = COVERS / (it.get("cover") or "")
        if not cov.exists() or cov.stat().st_size < 5_000:
            continue
        # 禁止残留 达芬七精选
        cats = [c for c in (it.get("categories") or []) if c != "达芬七精选"]
        if it.get("category") == "达芬七精选":
            it["category"] = "画面气质"
        if "画面气质" not in cats and it.get("category") == "画面气质":
            cats = ["画面气质"] + cats
        it["categories"] = cats or [it.get("category") or "其他"]
        cleaned.append(it)

    print(f"total cleaned {len(cleaned)}")
    if args.dry_run:
        from collections import Counter

        print(Counter(x.get("category") for x in cleaned))
        return 0

    # backup
    if INSPO_JSON.exists():
        bak = INSPO_JSON.with_suffix(".json.bak_pre_rse")
        shutil.copy2(INSPO_JSON, bak)
        print(f"backup -> {bak.name}")

    payload = {"inspirations": cleaned}
    INSPO_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {INSPO_JSON} count={len(cleaned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
