from __future__ import annotations

import base64
import html as html_lib
import json
import os
import sys
from io import BytesIO
from pathlib import Path

import gradio as gr
from PIL import Image

from brand.header import about_markdown, header_html, load_brand
from core.favorites import (
    delete_favorite,
    fav_choices,
    parse_fav_id,
    resolve_fav_prompt,
    save_favorite,
)
from core.generate import (
    get_model_mode,
    load_defaults,
    model_mode_choices,
    normalize_quality_label,
    preview_size,
    txt2img,
)
from core.comfy_client import free_comfy_memory, interrupt_comfy
from core.history import (
    choice_for_id,
    format_record_md,
    gallery_choices,
    get_record,
    list_records,
    parse_choice_id,
    resolve_image,
)
from core.paths import GALLERY_DIR, PROMPTS_FILE, ensure_runtime_dirs
from core.settings import (
    get_filename_prefix,
    get_theme,
    load_settings,
    save_settings,
    set_filename_prefix,
    set_theme,
)
from core.styles import (
    load_styles,
    resolve_style_name,
    style_categories,
    style_choices,
)
from core.system_stats import format_stats_html
from ui.themes import LABEL_TO_KEY, THEME_LABELS, THEMES, theme_vars_css


def _css() -> str:
    try:
        return Path(__file__).with_name("theme.css").read_text(encoding="utf-8")
    except Exception:
        return ""

def _weight_choices() -> list[str]:
    d = load_defaults()
    return list((d.get("weight_presets") or {"中 (0.85)": 0.85}).keys())


def _weight_value(label: str) -> float:
    d = load_defaults()
    presets = d.get("weight_presets") or {}
    if label in presets:
        return float(presets[label])
    # tolerate old labels
    if str(label).startswith("轻"):
        return 0.6
    if str(label).startswith("重"):
        return 1.0
    return 0.85


def _aspect_choices() -> list[str]:
    d = load_defaults()
    return list((d.get("aspect_ratios") or {"正方形 1:1": "1:1"}).keys())


def _quality_choices() -> list[str]:
    d = load_defaults()
    return list((d.get("quality_presets") or {"均衡": {}}).keys())


def _thumb_uri(path: str | None, size=(240, 320)) -> str:
    if not path or not Path(path).exists():
        return ""
    try:
        im = Image.open(path).convert("RGB")
        im.thumbnail(size)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def progress_html(pct: float, text: str) -> str:
    pct = max(0.0, min(1.0, float(pct)))
    w = f"{pct * 100:.1f}%"
    return (
        f'<div class="dv-progress" id="dv-progress">'
        f'<div class="dv-progress-label">{html_lib.escape(text)} · {int(pct * 100)}%</div>'
        f'<div class="dv-progress-wrap" role="progressbar" aria-valuenow="{int(pct * 100)}" '
        f'aria-valuemin="0" aria-valuemax="100">'
        f'<span class="dv-progress-fill" style="width:{w}"></span></div></div>'
    )


def size_badge_html(aspect: str, quality: str) -> str:
    try:
        q_label = normalize_quality_label(quality)
        w, h = preview_size(aspect, q_label)
        q = (load_defaults().get("quality_presets") or {}).get(q_label) or {}
        steps = q.get("steps", "—")
        return (
            f'<div class="dv-size">输出约 <b>{w} × {h}</b> px'
            f' · 长边 {q.get("long_edge", "—")} · 步数 {steps}</div>'
        )
    except Exception:
        return '<div class="dv-size">尺寸预览不可用</div>'


def image_dims_html(path: str | None) -> str:
    """Actual pixel size of a generated image file."""
    if not path:
        return '<div class="dv-dims dim">生成后显示实际像素</div>'
    p = Path(path)
    if not p.exists():
        return '<div class="dv-dims dim">生成后显示实际像素</div>'
    try:
        with Image.open(p) as im:
            w, h = im.size
        return f'<div class="dv-dims">实际输出 <b>{w} × {h}</b> px · {html_lib.escape(p.name)}</div>'
    except Exception:
        return '<div class="dv-dims dim">无法读取尺寸</div>'


def style_preview_html(label: str) -> str:
    style = resolve_style_name(label)
    if not style:
        return (
            '<div class="dv-style-empty">尚未选择风格。可在下方图库点选，或保持「无风格」。</div>'
        )
    src = _thumb_uri(style.cover_path, (200, 260))
    image = (
        f'<img src="{src}" alt="{html_lib.escape(style.name)}"/>'
        if src
        else '<div style="width:88px;height:110px;background:var(--bg-deep);border-radius:10px"></div>'
    )
    tags = " · ".join(style.tags[:3])
    badge = " · NSFW" if style.nsfw else ""
    trig = (
        html_lib.escape(style.trigger[:90] + ("…" if len(style.trigger) > 90 else ""))
        if style.trigger
        else "（无额外触发词，靠 LoRA 权重）"
    )
    link = (
        f'<a href="{html_lib.escape(style.civitai_url)}" target="_blank" rel="noopener">Civitai</a>'
        if style.civitai_url
        else "无外链"
    )
    return (
        f'<div class="dv-style-preview-card">{image}<div>'
        f"<div><strong>{html_lib.escape(style.name)}</strong>{badge}</div>"
        f"<span>{html_lib.escape(' / '.join(style.cats()))} · {html_lib.escape(tags)}</span>"
        f"<p>{html_lib.escape(style.tip or '')}</p>"
        f"<p>触发词：{trig}</p>"
        f"<p>商用：{html_lib.escape(style.commercial)} · {link}</p>"
        f"</div></div>"
    )


def gallery_html(show_nsfw: bool = True, category: str = "全部") -> str:
    cards = []
    for s in load_styles():
        if s.nsfw and not show_nsfw:
            continue
        if not s.in_category(category):
            continue
        src = _thumb_uri(s.cover_path)
        badge = (
            '<span class="dv-badge nsfw">NSFW</span>'
            if s.nsfw
            else ('<span class="dv-badge">推荐</span>' if s.featured else "")
        )
        cat_label = " / ".join(s.cats()[:2])
        cat = f'<span class="dv-badge cat">{html_lib.escape(cat_label)}</span>'
        tags = " · ".join(s.tags[:2]) if s.tags else ""
        img = (
            f'<img src="{src}" alt="{html_lib.escape(s.name)}" loading="lazy"/>'
            if src
            else '<div style="aspect-ratio:3/4;display:flex;align-items:center;justify-content:center;opacity:.5">暂无封面</div>'
        )
        link = (
            f'<a href="{html_lib.escape(s.civitai_url)}" target="_blank" rel="noopener">模型主页</a>'
            if s.civitai_url
            else "无外链"
        )
        trig = (
            html_lib.escape(s.trigger[:60] + ("…" if len(s.trigger) > 60 else ""))
            if s.trigger
            else "—"
        )
        cards.append(
            f'<div class="dv-card">{img}<div class="body">'
            f'<p class="title">{badge}{cat}{html_lib.escape(s.name)}</p>'
            f'<p class="meta">{html_lib.escape(tags)}<br/>强度 {s.default_weight}<br/>'
            f"触发词：{trig}<br/>商用：{html_lib.escape(s.commercial)}<br/>{link}</p>"
            f"</div></div>"
        )
    return f'<div class="dv-gallery">{"".join(cards) or "<p>该分类下暂无风格</p>"}</div>'


def _fallback_cover() -> str:
    from core.paths import COVERS_DIR

    for name in ("default_card.jpg", "default.jpg", "default.png"):
        p = COVERS_DIR / name
        if p.exists():
            return str(p)
    return ""


def _style_gallery_data(show_nsfw: bool = True, category: str = "全部"):
    """Return gallery items [(path, caption), ...] and parallel choice labels."""
    items: list[tuple[str, str]] = []
    labels: list[str] = []
    fb = _fallback_cover()

    none_path = fb
    items.append((none_path, "无风格"))
    labels.append("（无风格）")

    for s in load_styles():
        if s.nsfw and not show_nsfw:
            continue
        if not s.in_category(category):
            continue
        lab = ("🔒 " if s.nsfw else ("⭐ " if s.featured else "")) + s.name
        path = s.cover_path or fb
        if not path:
            continue
        # caption bottom: short name for 右下角/下方可读
        items.append((path, s.name))
        labels.append(lab)
    return items, labels


def _hist_gallery_data(limit: int = 48):
    """Return gallery items [(path, caption), ...] and ids aligned 1:1."""
    recs = list_records(limit)
    items: list[tuple[str, str]] = []
    ids: list[str] = []
    for r in recs:
        img = resolve_image(r.image_path)
        if not img.exists():
            continue
        cap = (r.prompt or "").replace("\n", " ").strip()
        if len(cap) > 18:
            cap = cap[:18] + "…"
        if not cap:
            cap = r.created_at[-8:]
        items.append((str(img), cap))
        ids.append(r.id)
    return items, ids

def load_prompt_presets() -> list[dict]:
    from core.paths import PROMPTS_FILE_LEGACY

    path = PROMPTS_FILE if PROMPTS_FILE.exists() else PROMPTS_FILE_LEGACY
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("presets") or [])
    except Exception:
        return []


def prompt_preset_choices() -> list[str]:
    items = ["（不使用预设）"]
    for p in load_prompt_presets():
        cat = p.get("category") or "通用"
        items.append(f"[{cat}] {p.get('title', p.get('id'))} · {p.get('id')}")
    return items


def resolve_preset_prompt(label: str) -> str:
    if not label or label.startswith("（不"):
        return ""
    pid = label.rsplit("·", 1)[-1].strip()
    for p in load_prompt_presets():
        if p.get("id") == pid:
            return p.get("prompt") or ""
    return ""


def theme_style_html(theme_key: str = "editorial") -> str:
    key = theme_key if theme_key in THEMES else "editorial"
    return f"<style id='dv-theme-live'>{theme_vars_css(key)}</style>"


def chrome_title_html(theme_key: str = "editorial") -> str:
    """Fixed title bar only — rarely updates (theme change)."""
    key = theme_key if theme_key in THEMES else "editorial"
    return (
        f'<div id="dv-title-fixed"><div id="dv-title-inner">'
        f"{header_html(key)}"
        f"</div></div>"
    )


def stats_shell_html() -> str:
    """Static fixed stats background — never polled (avoids whole-bar flash)."""
    return '<div id="dv-stats-shell" aria-hidden="true"></div>'


def stats_pills_html() -> str:
    """Only the pills row — timer updates this, not the shell."""
    return f'<div id="dv-stats-pills">{format_stats_html()}</div>'


def build_demo() -> gr.Blocks:
    brand = load_brand()
    ensure_runtime_dirs()
    modes = model_mode_choices()
    default_mode = "标准 FP8（推荐）" if "标准 FP8（推荐）" in modes else modes[0]
    aspects = _aspect_choices()
    qualities = _quality_choices()
    weights = _weight_choices()
    default_w = "中 (0.85)" if "中 (0.85)" in weights else weights[0]
    default_w_light = "轻 (0.6)" if "轻 (0.6)" in weights else weights[0]
    user_settings = load_settings()
    saved_theme = get_theme()
    show_nsfw0 = bool(user_settings.get("show_nsfw", False))
    styles0 = style_choices(show_nsfw0)
    cats = style_categories(show_nsfw0)
    hist_items, hist_ids = _hist_gallery_data()

    with gr.Blocks(title=brand.get("product_short", "达芬七 Z-Image")) as demo:
        theme_state = gr.State(saved_theme)
        hist_id_map = gr.State(hist_ids)

        # base CSS / 顶栏 / 状态：全部 elem_id，CSS 把文档流高度压成 0
        gr.HTML(f"<style id='dv-base-css'>{_css()}</style>", elem_id="dv-base-css-host")
        theme_css_box = gr.HTML(theme_style_html(saved_theme), elem_id="dv-theme-css-host")
        chrome_title = gr.HTML(chrome_title_html(saved_theme), elem_id="dv-title-host")
        gr.HTML(stats_shell_html(), elem_id="dv-stats-shell-host")  # never updated
        stats_pills = gr.HTML(stats_pills_html(), elem_id="dv-stats-live")
        refresh_sys = gr.Timer(value=3.0)
        refresh_sys.tick(fn=stats_pills_html, outputs=stats_pills)
        # 全屏灯箱改为纯前端 dv_fs.js（挂 body），不再走 Gradio HTML

        with gr.Tabs(elem_id="dv-main-tabs"):
            # ========== 文生图 ==========
            with gr.Tab("文生图"):
                with gr.Row(equal_height=False, elem_id="dv-workspace", elem_classes=["dv-workspace"]):
                    # 左 60%：提示词 / 收藏 / 风格
                    with gr.Column(scale=6, elem_id="dv-controls", min_width=340, elem_classes=["dv-controls"]):
                        gr.HTML(
                            '<div class="dv-section-head compact">'
                            "<h2>写提示词 · 选风格</h2></div>"
                        )
                        with gr.Column(elem_id="dv-prompt-panel"):
                            preset = gr.Dropdown(
                                choices=prompt_preset_choices(),
                                value="（不使用预设）",
                                label="灵感预设",
                            )
                            prompt = gr.Textbox(
                                label="提示词",
                                lines=5,
                                max_lines=12,
                                placeholder="人物、场景、光影、镜头、氛围…",
                                value=(
                                    "真实手机随拍，侧窗柔光，25–30岁东亚女性坐在窗边微侧脸，"
                                    "肩线放松看向镜头外，棉质上衣碎发，生活感自然皮肤质感，"
                                    "室内暗部保留，轻微颗粒，写实照片"
                                ),
                            )

                        def _apply_preset(lab):
                            t = resolve_preset_prompt(lab)
                            return t if t else gr.update()

                        preset.change(fn=_apply_preset, inputs=preset, outputs=prompt)

                        with gr.Accordion("提示词收藏（可选）", open=False, elem_id="dv-fav-box"):
                            with gr.Row(elem_id="dv-fav-row", equal_height=True):
                                fav_dd = gr.Dropdown(
                                    choices=fav_choices(),
                                    value="（未选收藏）",
                                    label="收藏提示词",
                                    show_label=False,
                                    scale=4,
                                    container=True,
                                    elem_id="dv-fav-dd",
                                )
                                fav_save_btn = gr.Button(
                                    "收藏当前", scale=1, min_width=88, elem_id="dv-fav-save"
                                )
                                fav_del_btn = gr.Button(
                                    "删除所选", scale=1, min_width=88, elem_id="dv-fav-del"
                                )
                            fav_status = gr.HTML("")

                        def _fav_save(p):
                            ok, msg = save_favorite(p or "")
                            cls = "ok" if ok else "err"
                            return (
                                gr.update(choices=fav_choices()),
                                f'<div class="dv-status {cls}">{html_lib.escape(msg)}</div>',
                            )

                        def _fav_load(lab):
                            t = resolve_fav_prompt(lab)
                            return t if t else gr.update()

                        def _fav_del(lab):
                            ok, msg = delete_favorite(parse_fav_id(lab or "") or "")
                            cls = "ok" if ok else "err"
                            return (
                                gr.update(choices=fav_choices(), value="（未选收藏）"),
                                f'<div class="dv-status {cls}">{html_lib.escape(msg)}</div>',
                            )

                        fav_save_btn.click(
                            fn=_fav_save, inputs=prompt, outputs=[fav_dd, fav_status]
                        )
                        fav_dd.change(fn=_fav_load, inputs=fav_dd, outputs=prompt)
                        fav_del_btn.click(
                            fn=_fav_del, inputs=fav_dd, outputs=[fav_dd, fav_status]
                        )

                        style_card_items, style_card_labels = _style_gallery_data(
                            show_nsfw0, "全部"
                        )
                        style1_state = gr.State("（无风格）")
                        # 隐藏：图库回填仍写这个；界面只靠图卡 + State
                        style1 = gr.Dropdown(
                            choices=styles0,
                            value="（无风格）",
                            visible=False,
                            elem_id="dv-style1",
                        )

                        with gr.Column(elem_id="dv-style-panel"):
                            gr.HTML(
                                '<div class="dv-group-label">风格（可选）</div>'
                                '<p class="dv-help" style="margin:0 0 10px">点下方图卡选择；8GB 一次只挂 1 个。点「无风格」清除。</p>'
                            )
                            # 左一半：已选预览；右一半：强度
                            with gr.Row(elem_id="dv-style-selected-row"):
                                with gr.Column(scale=1, min_width=160, elem_id="dv-style-selected-col"):
                                    gr.HTML(
                                        '<div class="dv-field-label">已选风格</div>'
                                    )
                                    style1_preview = gr.HTML(
                                        style_preview_html("（无风格）"),
                                        elem_id="dv-style-selected",
                                    )
                                with gr.Column(scale=1, min_width=140, elem_id="dv-style-weight-col"):
                                    gr.HTML(
                                        '<div class="dv-field-label">风格强度</div>'
                                    )
                                    w1 = gr.Radio(
                                        choices=weights,
                                        value=default_w,
                                        label="风格强度",
                                        show_label=False,
                                        elem_id="dv-style-weight",
                                    )

                            style_cards = gr.Gallery(
                                value=style_card_items,
                                label="风格图库 · 点选即可",
                                columns=6,
                                rows=2,
                                height=280,
                                object_fit="cover",
                                allow_preview=False,
                                interactive=True,
                                selected_index=0,
                                elem_id="dv-style-cards",
                            )

                        # 兼容图库回填；生成时忽略第二风格
                        style2 = gr.Dropdown(
                            choices=styles0, value="（无风格）", visible=False
                        )
                        w2 = gr.Dropdown(
                            choices=weights, value=default_w_light, visible=False
                        )

                    # 右 40%：预览在上 + 生成参数
                    with gr.Column(scale=4, elem_id="dv-canvas", min_width=320, elem_classes=["dv-canvas"]):
                        gr.HTML(
                            '<div class="dv-section-head compact"><h2>生成</h2></div>'
                        )
                        with gr.Column(elem_id="dv-preview-card"):
                            # 预览 + 右上角图标（全屏 / 复制）；点图也可全屏
                            with gr.Column(elem_id="dv-preview-wrap", elem_classes=["dv-preview-wrap"]):
                                out = gr.Image(
                                    label="结果",
                                    type="filepath",
                                    height=320,
                                    show_label=False,
                                    elem_id="dv-output",
                                    buttons=["download"],
                                    interactive=False,
                                    container=True,
                                )
                                with gr.Row(elem_id="dv-preview-icons"):
                                    fs_btn = gr.Button(
                                        "⛶",
                                        variant="secondary",
                                        elem_id="dv-fs-open-btn",
                                        size="sm",
                                        scale=0,
                                        min_width=36,
                                    )
                                    copy_btn = gr.Button(
                                        "⧉",
                                        variant="secondary",
                                        elem_id="dv-copy-btn",
                                        size="sm",
                                        scale=0,
                                        min_width=36,
                                    )
                            dims_box = gr.HTML(image_dims_html(None))

                        default_q = (
                            "1024 · 推荐"
                            if "1024 · 推荐" in qualities
                            else qualities[0]
                        )
                        with gr.Column(elem_id="dv-run-box"):
                            with gr.Row(elem_id="dv-param-row"):
                                model_mode = gr.Dropdown(
                                    choices=modes,
                                    value=default_mode,
                                    label="模型",
                                    scale=2,
                                )
                                aspect = gr.Dropdown(
                                    choices=aspects,
                                    value=aspects[0],
                                    label="比例",
                                    scale=1,
                                )
                            quality = gr.Radio(
                                choices=qualities,
                                value=default_q,
                                label="分辨率",
                                elem_id="dv-res-radio",
                            )
                            size_box = gr.HTML(size_badge_html(aspects[0], default_q))

                            def _on_size(ar, q):
                                return size_badge_html(ar, q)

                            quality.change(
                                fn=_on_size, inputs=[aspect, quality], outputs=size_box
                            )
                            aspect.change(
                                fn=_on_size, inputs=[aspect, quality], outputs=size_box
                            )

                            # 小白默认只需做两个明确选择；种子放到高级区，避免参数挤在一起。
                            with gr.Row(elem_id="dv-simple-options"):
                                creativity = gr.Radio(
                                    choices=["稳定（推荐）", "轻微变化", "明显变化"],
                                    value="稳定（推荐）",
                                    label="变化程度",
                                    elem_id="dv-variation",
                                )
                                num_images = gr.Radio(
                                    choices=["1 张", "2 张", "4 张"],
                                    value="1 张",
                                    label="一次生成",
                                    elem_id="dv-image-count",
                                )
                            with gr.Accordion("高级设置（可选）", open=False, elem_id="dv-advanced"):
                                seed = gr.Number(
                                    value=-1,
                                    label="固定种子（-1 为随机）",
                                    precision=0,
                                )
                                release_vram_btn = gr.Button(
                                    "释放显存",
                                    variant="secondary",
                                    elem_id="dv-release-vram-btn",
                                )
                                gr.Markdown(
                                    "换模型、停止或显存不足后可点。会卸载已加载模型，下一次生成需要重新加载。"
                                )
                            with gr.Row(elem_id="dv-gen-row"):
                                gen_btn = gr.Button(
                                    "生成画面",
                                    variant="primary",
                                    elem_id="dv-gen-btn",
                                    scale=2,
                                )
                                stop_btn = gr.Button(
                                    "停止",
                                    variant="secondary",
                                    elem_id="dv-stop-btn",
                                    scale=1,
                                )
                                open_btn = gr.Button(
                                    "导出文件夹",
                                    variant="secondary",
                                    scale=1,
                                )
                            # 进度只在 prog；status 只写结果/错误，避免两条一样的进度文案
                            prog = gr.HTML(
                                progress_html(0, "等待开始"), elem_id="dv-prog"
                            )
                            status = gr.HTML(
                                '<div class="dv-status dim">就绪</div>',
                                elem_id="dv-status",
                            )

                def _weight_label_for_style(lab: str) -> str:
                    """Map style default_weight → 轻/中/重 label."""
                    st = resolve_style_name(lab)
                    if not st:
                        return default_w
                    w = float(st.default_weight or 0.85)
                    if w <= 0.7:
                        return default_w_light if default_w_light in weights else weights[0]
                    if w >= 0.95:
                        heavy = "重 (1.0)"
                        return heavy if heavy in weights else weights[-1]
                    return default_w if default_w in weights else weights[len(weights) // 2]

                def _sync_style_from_dd(lab: str):
                    """Hidden dropdown（图库回填）→ state + 预览；不改强度，保留回填权重。"""
                    lab = lab or "（无风格）"
                    return lab, style_preview_html(lab)

                style1.change(
                    fn=_sync_style_from_dd,
                    inputs=style1,
                    outputs=[style1_state, style1_preview],
                )

                def _on_pick_style_card(evt: gr.SelectData):
                    """Gallery index → 风格标签；兼容 int / (row,col)。"""
                    idx = evt.index
                    try:
                        if isinstance(idx, (list, tuple)):
                            if len(idx) >= 2:
                                idx = int(idx[0]) * 6 + int(idx[1])
                            else:
                                idx = int(idx[0])
                        else:
                            idx = int(idx)
                    except Exception:
                        empty = "（无风格）"
                        return empty, gr.update(value=empty), style_preview_html(empty), default_w
                    _, labels = _style_gallery_data(show_nsfw0, "全部")
                    if idx < 0 or idx >= len(labels):
                        empty = "（无风格）"
                        return empty, gr.update(value=empty), style_preview_html(empty), default_w
                    chosen = labels[idx]
                    print(f"[style] card idx={idx} -> {chosen!r}", flush=True)
                    return (
                        chosen,
                        gr.update(value=chosen),
                        style_preview_html(chosen),
                        _weight_label_for_style(chosen),
                    )

                style_cards.select(
                    fn=_on_pick_style_card,
                    inputs=None,
                    outputs=[style1_state, style1, style1_preview, w1],
                )

                # 多张生成可中断：点「停止」后本张可能仍会跑完，后续张不再开
                stop_flag = {"stop": False}

                def _request_stop():
                    stop_flag["stop"] = True
                    try:
                        d = load_defaults().get("comfy") or {}
                        interrupt_comfy(
                            host=d.get("host", "127.0.0.1"),
                            port=int(d.get("port", 7777)),
                        )
                        free_comfy_memory(
                            host=d.get("host", "127.0.0.1"),
                            port=int(d.get("port", 7777)),
                        )
                    except Exception:
                        pass
                    return (
                        progress_html(0, "已请求停止"),
                        '<div class="dv-status">已请求停止：当前这张结束后不再继续多张。</div>',
                    )

                stop_btn.click(fn=_request_stop, outputs=[prog, status])

                def _release_vram():
                    d = load_defaults().get("comfy") or {}
                    ok = free_comfy_memory(
                        host=d.get("host", "127.0.0.1"),
                        port=int(d.get("port", 7777)),
                    )
                    if ok:
                        return (
                            '<div class="dv-status ok">已请求释放显存。'
                            "下次生成会重新加载模型，首张会慢一些。</div>"
                        )
                    return '<div class="dv-status err">释放失败：请先确认引擎在线。</div>'

                release_vram_btn.click(fn=_release_vram, outputs=status)

                # 全屏由 dv_fs.js 拦截角标/点图，无需服务端事件

                def _run_t2i(p, mm, ar, q, s1, ww1, s2, ww2, sd, creat, n_img):
                    import threading
                    import time as _time

                    stop_flag["stop"] = False
                    # 8GB：只挂 1 个风格 LoRA
                    s2 = "（无风格）"
                    ww2 = "轻 (0.6)"
                    empty_dims = image_dims_html(None)
                    st = resolve_style_name(s1)
                    print(
                        f"\n[gen] start  model={mm}  {ar}  {q}  n={n_img}  "
                        f"style={s1!r} -> {st.name if st else None}  "
                        f"lora={st.file if st else None}  w={ww1}",
                        flush=True,
                    )
                    try:
                        total = max(1, min(4, int(str(n_img or "1").split()[0])))
                    except Exception:
                        total = 1
                    creat_i = {
                        "稳定（推荐）": 0,
                        "轻微变化": 25,
                        "明显变化": 55,
                    }.get(str(creat), 0)
                    q = normalize_quality_label(q)

                    if not (p or "").strip():
                        yield (
                            None,
                            empty_dims,
                            progress_html(0, "等待开始"),
                            '<div class="dv-status err">请先填写提示词</div>',
                            gr.skip(),
                            gr.skip(),
                            gr.skip(),
                        )
                        return

                    paths: list[str] = []
                    fixed_seed = None
                    try:
                        if sd is not None and int(sd) >= 0:
                            fixed_seed = int(sd)
                    except Exception:
                        fixed_seed = None

                    for i in range(total):
                        if stop_flag["stop"]:
                            break

                        state = {
                            "pct": 0.05,
                            "msg": f"准备中（{i+1}/{total}）",
                            "done": False,
                            "err": None,
                            "path": None,
                        }

                        def on_prog(pct: float, msg: str, _i=i):
                            # 网页进度；CMD 用 comfy_client 里原生 tqdm
                            state["pct"] = pct
                            state["msg"] = f"[{_i+1}/{total}] {msg}"

                        use_seed = -1 if fixed_seed is None else fixed_seed + i

                        def worker(_seed=use_seed):
                            try:
                                state["path"] = str(
                                    txt2img(
                                        p,
                                        ar,
                                        q,
                                        resolve_style_name(s1),
                                        _weight_value(ww1),
                                        resolve_style_name(s2),
                                        _weight_value(ww2),
                                        seed=_seed,
                                        model_mode_label=mm,
                                        on_progress=on_prog,
                                        style1_label=s1,
                                        style2_label=s2,
                                        weight1_label=ww1,
                                        weight2_label=ww2,
                                        creativity=creat_i,
                                    )
                                )
                            except Exception as e:
                                state["err"] = str(e)
                            finally:
                                state["done"] = True

                        threading.Thread(target=worker, daemon=True).start()
                        show = paths[-1] if paths else None
                        yield (
                            show,
                            image_dims_html(show) if show else empty_dims,
                            progress_html(0.08, state["msg"]),
                            gr.skip(),  # 生成中不重复刷 status，避免双进度条
                            gr.skip(),
                            gr.skip(),
                            gr.skip(),
                        )
                        while not state["done"]:
                            if stop_flag["stop"]:
                                try:
                                    d = load_defaults().get("comfy") or {}
                                    interrupt_comfy(
                                        host=d.get("host", "127.0.0.1"),
                                        port=int(d.get("port", 7777)),
                                    )
                                except Exception:
                                    pass
                            _time.sleep(0.4)
                            show = paths[-1] if paths else None
                            yield (
                                show,
                                image_dims_html(show) if show else empty_dims,
                                progress_html(state["pct"], state["msg"]),
                                (
                                    '<div class="dv-status">已请求停止…</div>'
                                    if stop_flag["stop"]
                                    else gr.skip()
                                ),
                                gr.skip(),
                                gr.skip(),
                                gr.skip(),
                            )

                        if state["err"]:
                            if stop_flag["stop"]:
                                break
                            err_text = str(state["err"])
                            if "显存不足" in err_text or "oom" in err_text.lower():
                                d = load_defaults().get("comfy") or {}
                                free_comfy_memory(
                                    host=d.get("host", "127.0.0.1"),
                                    port=int(d.get("port", 7777)),
                                )
                            show = paths[-1] if paths else None
                            yield (
                                show,
                                image_dims_html(show) if show else empty_dims,
                                progress_html(0, "失败"),
                                f'<div class="dv-status err">第 {i+1} 张失败：{html_lib.escape(err_text)}</div>',
                                gr.skip(),
                                gr.skip(),
                                gr.skip(),
                            )
                            return

                        if state["path"]:
                            paths.append(state["path"])
                            print(
                                f"[gen] done {i+1}/{total}  {Path(state['path']).name}",
                                flush=True,
                            )
                            yield (
                                state["path"],
                                image_dims_html(state["path"]),
                                progress_html((i + 1) / total, f"已完成 {i+1}/{total}"),
                                f'<div class="dv-status ok">第 {i+1}/{total} 张完成 · {Path(state["path"]).name}</div>',
                                gr.skip(),
                                gr.skip(),
                                gr.skip(),
                            )

                        if stop_flag["stop"]:
                            break

                    choices = gallery_choices()
                    hitems, hids = _hist_gallery_data()
                    applied = []
                    if s1 and not str(s1).startswith("（无"):
                        applied.append(str(s1))
                    if s2 and not str(s2).startswith("（无"):
                        applied.append(str(s2))
                    extra = (" · 风格 " + " + ".join(applied)) if applied else " · 无风格"
                    creat_tip = f" · {creat}" if creat_i else ""
                    last = paths[-1] if paths else None
                    if stop_flag["stop"]:
                        msg = (
                            f'<div class="dv-status">已停止 · 共完成 {len(paths)}/{total} 张'
                            f"{extra}{creat_tip}</div>"
                        )
                        print(f"[gen] stopped {len(paths)}/{total}", flush=True)
                    else:
                        msg = (
                            f'<div class="dv-status ok">完成 {len(paths)} 张'
                            f"{extra}{creat_tip}</div>"
                        )
                        print(f"[gen] all done count={len(paths)}", flush=True)
                    # choices 与 value 必须成对，且 value 一定在 choices 里
                    dd_val = choices[0] if choices else None
                    yield (
                        last,
                        image_dims_html(last),
                        progress_html(
                            1.0 if paths and not stop_flag["stop"] else 0,
                            "完成" if not stop_flag["stop"] else "已停止",
                        ),
                        msg,
                        gr.update(choices=choices, value=dd_val),
                        gr.update(value=hitems),
                        hids,
                    )

            # ========== 图库 ==========
            with gr.Tab("图库"):
                gr.HTML(
                    '<div class="dv-section-head"><span class="eyebrow">LIBRARY</span>'
                    "<h2>图库</h2><p>点击图片查看详情并回填。数据在 userdata/gallery。</p></div>"
                )
                hist_gallery = gr.Gallery(
                    value=hist_items,
                    label="点击缩略图查看详情",
                    columns=10,
                    rows=1,
                    height=132,
                    object_fit="cover",
                    fit_columns=False,
                    allow_preview=False,
                    elem_id="dv-hist-gallery",
                )
                hist_dd = gr.Dropdown(
                    choices=gallery_choices(),
                    label="历史记录（同步）",
                    value=None,
                    interactive=True,
                    allow_custom_value=True,
                )
                with gr.Row():
                    with gr.Column(scale=1):
                        with gr.Column(elem_id="dv-hist-preview-wrap"):
                            hist_img = gr.Image(
                                label="预览",
                                type="filepath",
                                height=380,
                                buttons=["download"],
                                interactive=False,
                                elem_id="dv-hist-preview",
                            )
                            with gr.Row(elem_id="dv-hist-preview-icons"):
                                hist_fs_btn = gr.Button(
                                    "⛶",
                                    variant="secondary",
                                    elem_id="dv-hist-fs-btn",
                                    size="sm",
                                    scale=0,
                                    min_width=36,
                                )
                                hist_copy_btn = gr.Button(
                                    "⧉",
                                    variant="secondary",
                                    elem_id="dv-hist-copy-btn",
                                    size="sm",
                                    scale=0,
                                    min_width=36,
                                )
                    hist_md = gr.HTML(
                        '<div class="dv-hist-meta">点击缩略图查看参数；点预览图可全屏。</div>',
                        elem_id="dv-hist-meta",
                    )
                with gr.Row():
                    apply_btn = gr.Button("一键回填到文生图", variant="primary")
                    hist_refresh = gr.Button("刷新", variant="secondary")
                    open_gal = gr.Button("打开图库文件夹", variant="secondary")
                # 图库全屏同样走前端灯箱

                def _on_pick_dd(label):
                    rid = parse_choice_id(label or "")
                    rec = get_record(rid) if rid else None
                    if not rec:
                        return None, "未找到记录"
                    return str(resolve_image(rec.image_path)), format_record_md(rec)

                def _on_pick_gal(evt: gr.SelectData):
                    """Always re-read gallery order from disk so index never drifts."""
                    idx = evt.index
                    if isinstance(idx, (list, tuple)):
                        idx = idx[0]
                    try:
                        idx = int(idx)
                    except Exception:
                        return gr.update(), None, "未找到记录", []
                    items, ids = _hist_gallery_data()
                    if idx < 0 or idx >= len(ids):
                        return gr.update(), None, "未找到记录", ids
                    rid = ids[idx]
                    rec = get_record(rid)
                    if not rec:
                        try:
                            path = items[idx][0]
                            for r in list_records(80):
                                if str(resolve_image(r.image_path)) == path:
                                    rec = r
                                    rid = r.id
                                    break
                        except Exception:
                            pass
                    if not rec:
                        return gr.update(), None, "未找到记录", ids
                    # 必须同时更新 choices + value，否则新图 value 不在旧列表里会炸
                    ch, lab = choice_for_id(rid)
                    return (
                        gr.update(choices=ch, value=lab),
                        str(resolve_image(rec.image_path)),
                        format_record_md(rec),
                        ids,
                    )

                hist_dd.change(fn=_on_pick_dd, inputs=hist_dd, outputs=[hist_img, hist_md])
                hist_gallery.select(
                    fn=_on_pick_gal,
                    inputs=None,
                    outputs=[hist_dd, hist_img, hist_md, hist_id_map],
                )

                def _refresh_hist():
                    ch = gallery_choices()
                    hitems, hids = _hist_gallery_data()
                    return (
                        gr.update(value=hitems),
                        hids,
                        gr.update(choices=ch, value=ch[0] if ch else None),
                    )

                hist_refresh.click(
                    fn=_refresh_hist, outputs=[hist_gallery, hist_id_map, hist_dd]
                )

                def _apply(label):
                    rid = parse_choice_id(label or "")
                    rec = get_record(rid) if rid else None
                    if not rec:
                        return (
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            "（无风格）",
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            gr.update(),
                            '<div class="dv-status err">没有可回填的记录</div>',
                        )

                    def style_label(name: str) -> str:
                        if not name or str(name).startswith("（无"):
                            return "（无风格）"
                        for c in style_choices(True):
                            clean = c.replace("⭐ ", "").replace("🔒 ", "")
                            if clean == name or name in c:
                                return c
                        return "（无风格）"

                    def wlab(w: str) -> str:
                        if w in weights:
                            return w
                        if str(w).startswith("轻"):
                            return default_w_light
                        if str(w).startswith("重"):
                            return "重 (1.0)" if "重 (1.0)" in weights else weights[-1]
                        return default_w

                    s1_lab = style_label(rec.style1)
                    return (
                        rec.prompt or "",
                        rec.model_mode if rec.model_mode in modes else default_mode,
                        rec.aspect if rec.aspect in aspects else aspects[0],
                        normalize_quality_label(rec.quality)
                        if normalize_quality_label(rec.quality) in qualities
                        else default_q,
                        s1_lab,
                        s1_lab,  # style1_state
                        style_preview_html(s1_lab),
                        wlab(rec.weight1),
                        style_label(rec.style2),
                        wlab(rec.weight2),
                        rec.seed if rec.seed is not None else -1,
                        '<div class="dv-status ok">已回填到「文生图」</div>',
                    )

                apply_btn.click(
                    fn=_apply,
                    inputs=[hist_dd],
                    outputs=[
                        prompt,
                        model_mode,
                        aspect,
                        quality,
                        style1,
                        style1_state,
                        style1_preview,
                        w1,
                        style2,
                        w2,
                        seed,
                        status,
                    ],
                )

                def _open_gal():
                    ensure_runtime_dirs()
                    if sys.platform.startswith("win"):
                        os.startfile(str(GALLERY_DIR))  # type: ignore
                    hitems, hids = _hist_gallery_data()
                    return gr.update(value=hitems), hids

                open_gal.click(fn=_open_gal, outputs=[hist_gallery, hist_id_map])

            # ========== 风格 ==========
            with gr.Tab("风格"):
                gr.HTML(
                    '<div class="dv-section-head"><span class="eyebrow">STYLES</span>'
                    "<h2>风格库</h2>"
                    "<p>分类、触发词、商用备注与 Civitai 链接。</p></div>"
                )
                with gr.Row():
                    nsfw_gal = gr.Checkbox(value=False, label="显示成人向")
                    cat_gal = gr.Dropdown(choices=cats, value="全部", label="分类")
                gal = gr.HTML(gallery_html(False, "全部"))
                nsfw_gal.change(
                    fn=lambda s, c: gallery_html(s, c),
                    inputs=[nsfw_gal, cat_gal],
                    outputs=gal,
                )
                cat_gal.change(
                    fn=lambda s, c: gallery_html(s, c),
                    inputs=[nsfw_gal, cat_gal],
                    outputs=gal,
                )

            # ========== 设置 ==========
            with gr.Tab("设置"):
                gr.HTML(
                    '<div class="dv-section-head"><span class="eyebrow">SETTINGS</span>'
                    "<h2>设置</h2></div>"
                )
                theme_dd = gr.Radio(
                    choices=list(THEME_LABELS.values()),
                    value=THEME_LABELS.get(saved_theme, THEME_LABELS["editorial"]),
                    label="界面皮肤",
                    elem_id="dv-theme-picker",
                )

                def _on_theme(label: str):
                    key = set_theme(LABEL_TO_KEY.get(label, "editorial"))
                    return key, theme_style_html(key), chrome_title_html(key)

                theme_dd.change(
                    fn=_on_theme,
                    inputs=theme_dd,
                    outputs=[theme_state, theme_css_box, chrome_title],
                )

                gr.Markdown(
                    "#### 导出文件名前缀\n"
                    "生成图在引擎 `output` 与 `userdata\\gallery` 里的文件名前缀。"
                    "默认 `davincilab`，可改成 `zimage` 等（仅字母数字和 `_` `-`）。"
                )
                prefix_tb = gr.Textbox(
                    value=get_filename_prefix(),
                    label="文件名前缀",
                    placeholder="davincilab",
                    max_lines=1,
                    elem_id="dv-filename-prefix",
                )
                prefix_status = gr.Markdown("")

                def _on_prefix(val: str):
                    clean = set_filename_prefix(val)
                    return clean, f"已保存：后续生成将使用 `{clean}_00001_.png` 这类名字"

                prefix_tb.blur(
                    fn=_on_prefix,
                    inputs=prefix_tb,
                    outputs=[prefix_tb, prefix_status],
                )
                prefix_tb.submit(
                    fn=_on_prefix,
                    inputs=prefix_tb,
                    outputs=[prefix_tb, prefix_status],
                )

            # ========== 关于 ==========
            with gr.Tab("关于"):
                gr.Markdown(about_markdown())
        # wire generate after hist widgets exist
        gen_btn.click(
            fn=_run_t2i,
            inputs=[
                prompt,
                model_mode,
                aspect,
                quality,
                style1_state,  # 用 State，避免隐藏控件丢值
                w1,
                style2,
                w2,
                seed,
                creativity,
                num_images,
            ],
            outputs=[out, dims_box, prog, status, hist_dd, hist_gallery, hist_id_map],
        )

        def _copy_image_to_clipboard(path: str | None) -> bool:
            """Copy result image to Windows clipboard for paste elsewhere."""
            if not path:
                return False
            p = Path(path)
            if not p.exists() or not sys.platform.startswith("win"):
                return False
            try:
                import subprocess

                ps_path = str(p.resolve()).replace("'", "''")
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "Add-Type -AssemblyName System.Drawing; "
                    f"$img = [System.Drawing.Image]::FromFile('{ps_path}'); "
                    "[System.Windows.Forms.Clipboard]::SetImage($img); "
                    "$img.Dispose();"
                )
                r = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        ps,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return r.returncode == 0
            except Exception:
                return False

        def _copy_result(image_path: str | None):
            if not image_path:
                return '<div class="dv-status err">还没有图可复制，请先生成。</div>'
            if _copy_image_to_clipboard(image_path):
                return (
                    '<div class="dv-status ok">图片已复制到剪贴板，到别处 Ctrl+V 即可粘贴。</div>'
                )
            return (
                f'<div class="dv-status err">复制失败，请到导出文件夹手动复制：'
                f"{html_lib.escape(str(image_path))}</div>"
            )

        copy_btn.click(fn=_copy_result, inputs=out, outputs=status)
        hist_copy_btn.click(fn=_copy_result, inputs=hist_img, outputs=status)

        def _open_out():
            ensure_runtime_dirs()
            if sys.platform.startswith("win"):
                os.startfile(str(GALLERY_DIR))  # type: ignore
            return f'<div class="dv-status">已打开 {GALLERY_DIR}</div>'

        open_btn.click(fn=_open_out, outputs=status)

    return demo
