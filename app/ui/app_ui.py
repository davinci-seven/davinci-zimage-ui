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
    clamp_custom_size,
    custom_size_limits,
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
from core.inspirations import (
    delete_user_inspiration,
    inspiration_categories,
    inspiration_gallery_data,
    is_favorite as inspo_is_favorite,
    list_favorite_ids as inspo_list_favorite_ids,
    load_inspirations,
    resolve_inspiration,
    save_user_inspiration,
    toggle_favorite as inspo_toggle_favorite,
)
from core.styles import (
    is_favorite,
    list_favorite_ids,
    load_styles,
    resolve_style_name,
    style_categories,
    style_choices,
    toggle_favorite,
)
from core.system_stats import (
    format_stats_html,
    format_vram_size_warning_html,
    size_vram_advice,
)
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


def size_badge_html(
    aspect: str,
    quality: str,
    custom_on: bool = False,
    custom_w: int | None = None,
    custom_h: int | None = None,
    model_mode_label: str = "标准 FP8（推荐）",
) -> str:
    try:
        q_label = normalize_quality_label(quality)
        q = (load_defaults().get("quality_presets") or {}).get(q_label) or {}
        steps = q.get("steps", "—")
        w, h = preview_size(
            aspect,
            q_label,
            custom_size=bool(custom_on),
            custom_width=custom_w,
            custom_height=custom_h,
        )
        if custom_on:
            tag = "自定义"
            edge_txt = f"长边 {max(w, h)}"
        else:
            tag = "预设"
            edge_txt = f"长边 {q.get('long_edge', '—')}"
        return (
            f'<div class="dv-size">输出约 <b>{w} × {h}</b> px'
            f" · {tag} · {edge_txt} · 步数 {steps}</div>"
        )
    except Exception:
        return '<div class="dv-size">尺寸预览不可用</div>'


def vram_tip_html(
    aspect: str,
    quality: str,
    custom_on: bool,
    custom_w,
    custom_h,
    model_mode_label: str,
) -> str:
    """VRAM soft/hard warning for current output size (always useful, louder when custom)."""
    try:
        w, h = preview_size(
            aspect,
            normalize_quality_label(quality),
            custom_size=bool(custom_on),
            custom_width=custom_w,
            custom_height=custom_h,
        )
        mode = get_model_mode(model_mode_label or "标准 FP8（推荐）")
        backend = mode.get("backend") or "fp8"
        d = load_defaults().get("comfy") or {}
        advice = size_vram_advice(
            w,
            h,
            backend=str(backend),
            host=d.get("host", "127.0.0.1"),
            port=int(d.get("port", 7777)),
        )
        # preset sizes only show tip when over soft limit; custom always shows
        if not custom_on and advice.get("level") == "ok":
            return ""
        return format_vram_size_warning_html(advice)
    except Exception:
        return ""


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
            '<div class="dv-style-empty">尚未选择。可在图库点选，或保持为空。</div>'
        )
    src = _thumb_uri(style.cover_path, (200, 260))
    image = (
        f'<img src="{src}" alt="{html_lib.escape(style.name)}"/>'
        if src
        else '<div style="width:88px;height:110px;background:var(--bg-deep);border-radius:10px"></div>'
    )
    tags = " · ".join(style.tags[:3])
    if style.is_prompt():
        badge = " · 风格灵感"
        pre = (style.prompt_prefix or "").strip()
        suf = (style.prompt_suffix or "").strip()
        pre_esc = html_lib.escape(pre) if pre else "（无）"
        suf_esc = html_lib.escape(suf) if suf else "（无）"
        detail = (
            f'<div class="dv-prompt-inject">'
            f'<div class="dv-prompt-inject-label">出图时会拼进提示词（中文）</div>'
            f'<div class="dv-prompt-inject-block"><b>前缀</b>：{pre_esc}</div>'
            f'<div class="dv-prompt-inject-block"><b>后缀</b>：{suf_esc}</div>'
            f'<div class="dv-help" style="margin-top:6px">不加载 LoRA · 几乎不额外占显存</div>'
            f"</div>"
        )
    else:
        badge = " · NSFW" if style.nsfw else " · LoRA 模型"
        trig = (
            html_lib.escape(style.trigger[:90] + ("…" if len(style.trigger) > 90 else ""))
            if style.trigger
            else "（无额外触发词，靠 LoRA 权重）"
        )
        detail = f"<p>触发词：{trig}</p>"
    url = style.source_url() or style.civitai_url
    credit = style.source_credit()
    if url:
        link = (
            f'<a href="{html_lib.escape(url)}" target="_blank" rel="noopener">'
            f"{html_lib.escape(credit or '来源')}</a>"
        )
    elif credit:
        link = html_lib.escape(credit)
    else:
        link = "无外链"
    star = " ★" if is_favorite(style.id) else ""
    return (
        f'<div class="dv-style-preview-card">{image}<div>'
        f"<div><strong>{html_lib.escape(style.name)}</strong>{badge}{star}</div>"
        f"<span>{html_lib.escape(' / '.join(style.cats()))} · {html_lib.escape(tags)}</span>"
        f"<p>{html_lib.escape(style.tip or '')}</p>"
        f"{detail}"
        f"<p>出处：{link} · {html_lib.escape(style.commercial)}</p>"
        f"</div></div>"
    )


def gallery_html(
    show_nsfw: bool = True,
    category: str = "全部",
    kind_filter: str = "全部",
) -> str:
    """Browse-only catalog cards. kind_filter: 全部 | LoRA | 提示词"""
    cards = []
    kf = (kind_filter or "全部").strip()
    kind_arg = None
    if kf == "LoRA":
        kind_arg = "lora"
    elif kf == "提示词":
        kind_arg = "prompt"
    for s in load_styles(kind=kind_arg):
        if s.nsfw and not show_nsfw:
            continue
        if not s.in_category(category):
            continue
        src = _thumb_uri(s.cover_path)
        if s.is_prompt():
            badge = '<span class="dv-badge">风格灵感</span>'
        elif s.nsfw:
            badge = '<span class="dv-badge nsfw">NSFW</span>'
        elif s.featured:
            badge = '<span class="dv-badge">推荐</span>'
        else:
            badge = ""
        cat_label = " / ".join(s.cats()[:2])
        cat = f'<span class="dv-badge cat">{html_lib.escape(cat_label)}</span>'
        tags = " · ".join(s.tags[:2]) if s.tags else ""
        img = (
            f'<img src="{src}" alt="{html_lib.escape(s.name)}" loading="lazy"/>'
            if src
            else '<div style="aspect-ratio:3/4;display:flex;align-items:center;justify-content:center;opacity:.5">暂无封面</div>'
        )
        url = s.source_url() or s.civitai_url
        credit = s.source_credit()
        if url:
            link = (
                f'<a href="{html_lib.escape(url)}" target="_blank" rel="noopener">'
                f"{html_lib.escape(credit or '来源')}</a>"
            )
        else:
            link = html_lib.escape(credit) if credit else "无外链"
        if s.is_prompt():
            head = (s.prompt_prefix or "")[:60]
            detail = f"注入：{html_lib.escape(head)}{'…' if len(s.prompt_prefix or '') > 60 else ''}"
        else:
            trig = (
                html_lib.escape(s.trigger[:60] + ("…" if len(s.trigger) > 60 else ""))
                if s.trigger
                else "—"
            )
            detail = f"强度 {s.default_weight} · 触发词：{trig}"
        cards.append(
            f'<div class="dv-card">{img}<div class="body">'
            f'<p class="title">{badge}{cat}{html_lib.escape(s.name)}</p>'
            f'<p class="meta">{html_lib.escape(tags)}<br/>{detail}<br/>'
            f"商用：{html_lib.escape(s.commercial)}<br/>{link}</p>"
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


def _style_gallery_data(
    show_nsfw: bool = True,
    category: str = "全部",
    kind_filter: str = "全部",
):
    """Return gallery items [(path, caption), ...] and parallel choice labels.

    kind_filter: 全部 | LoRA | 提示词 | 收藏
    """
    items: list[tuple[str, str]] = []
    labels: list[str] = []
    fb = _fallback_cover()

    none_path = fb
    items.append((none_path, "无风格"))
    labels.append("（无风格）")

    fav_ids = set(list_favorite_ids())
    kf = (kind_filter or "全部").strip()
    kind_arg = None
    if kf == "LoRA":
        kind_arg = "lora"
    elif kf == "提示词":
        kind_arg = "prompt"

    for s in load_styles(kind=kind_arg):
        if s.nsfw and not show_nsfw:
            continue
        if kf == "收藏" and s.id not in fav_ids:
            continue
        if not s.in_category(category):
            continue
        lab = s.label()
        path = s.cover_path or fb
        if not path:
            continue
        cap = s.name
        if s.is_prompt():
            cap = "📝 " + cap
        items.append((path, cap))
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

def inspo_preview_html(label: str) -> str:
    """Selected 提示词灵感: show full Chinese prompt that will fill the box."""
    ins = resolve_inspiration(label)
    if not ins:
        return (
            '<div class="dv-style-empty">尚未选择提示词灵感。点选图卡后，'
            "整段中文提示词会写入上方输入框，可再改；可与下方 LoRA 同开。</div>"
        )
    src = _thumb_uri(ins.cover_path, (200, 260))
    image = (
        f'<img src="{src}" alt="{html_lib.escape(ins.name)}"/>'
        if src
        else '<div style="width:88px;height:110px;background:var(--bg-deep);border-radius:10px"></div>'
    )
    prompt_esc = html_lib.escape(ins.prompt or "").replace("\n", "<br/>")
    star = " ★" if inspo_is_favorite(ins.id) else ""
    return (
        f'<div class="dv-style-preview-card">{image}<div>'
        f"<div><strong>{html_lib.escape(ins.name)}</strong> · 提示词灵感{star}</div>"
        f"<span>{html_lib.escape(' / '.join(ins.cats()))}</span>"
        f"<p>{html_lib.escape(ins.tip or '')}</p>"
        f'<div class="dv-prompt-inject">'
        f'<div class="dv-prompt-inject-label">将写入提示词框（中文全文）</div>'
        f'<div class="dv-prompt-inject-block">{prompt_esc}</div>'
        f"</div></div></div>"
    )


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
                            "<h2>写提示词 · 出图</h2></div>"
                        )
                        with gr.Column(elem_id="dv-prompt-panel"):
                            prompt = gr.Textbox(
                                label="提示词",
                                lines=5,
                                max_lines=12,
                                placeholder="人物、场景、光影、镜头、氛围… 或从下方「提示词灵感」点选填入",
                                value=(
                                    "真实手机随拍，侧窗柔光，25–30岁东亚女性坐在窗边微侧脸，"
                                    "肩线放松看向镜头外，棉质上衣碎发，生活感自然皮肤质感，"
                                    "室内暗部保留，轻微颗粒，写实照片"
                                ),
                            )

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

                        lora_card_items, _ = _style_gallery_data(
                            show_nsfw0, "全部", "LoRA"
                        )
                        inspo_cats = inspiration_categories()
                        inspo_items, _ = inspiration_gallery_data("全部", False)
                        inspo_fav_items, _ = inspiration_gallery_data("全部", True)

                        # LoRA 槽
                        style1_state = gr.State("（无风格）")
                        style1 = gr.Dropdown(
                            choices=styles0,
                            value="（无风格）",
                            visible=False,
                            elem_id="dv-style1",
                        )
                        # 提示词灵感槽（点选 → 写入 prompt 框，不注入 generate）
                        inspo_state = gr.State("（无）")

                        # —— 提示词灵感（原预设 + 精选合并）——
                        with gr.Column(
                            elem_id="dv-inspo-block", elem_classes=["dv-style-block"]
                        ):
                            gr.HTML(
                                '<div class="dv-group-label">提示词灵感</div>'
                                '<p class="dv-help" style="margin:0 0 8px">'
                                "点选图卡 → <b>整段中文提示词写入上方输入框</b>（可再改）。"
                                "可分类、收藏、自建。与下方 LoRA <b>可同时用</b>，不加载模型。</p>"
                            )
                            with gr.Row():
                                inspo_preview = gr.HTML(
                                    inspo_preview_html("（无）"),
                                    elem_id="dv-inspo-preview",
                                )
                                with gr.Column(scale=0, min_width=120):
                                    inspo_fav_btn = gr.Button(
                                        "收藏/取消",
                                        variant="secondary",
                                        elem_id="dv-inspo-fav",
                                    )
                                    inspo_clear_btn = gr.Button(
                                        "清除选用",
                                        variant="secondary",
                                        elem_id="dv-inspo-clear",
                                    )
                            with gr.Row():
                                inspo_cat = gr.Dropdown(
                                    choices=inspo_cats,
                                    value="全部",
                                    label="分类",
                                    scale=2,
                                    elem_id="dv-inspo-cat",
                                )
                                inspo_show_fav = gr.Checkbox(
                                    value=False,
                                    label="只看收藏",
                                    elem_id="dv-inspo-only-fav",
                                )
                            style_cards_inspo = gr.Gallery(
                                value=inspo_items,
                                label="提示词灵感 · 点选填入",
                                columns=6,
                                rows=2,
                                height=220,
                                object_fit="cover",
                                allow_preview=False,
                                interactive=True,
                                selected_index=0,
                                elem_id="dv-inspo-cards",
                            )
                            with gr.Row(elem_id="dv-inspo-manage-row"):
                                inspo_save_name = gr.Textbox(
                                    value="",
                                    label="另存名称",
                                    placeholder="我的灵感名",
                                    max_lines=1,
                                    scale=2,
                                    elem_id="dv-inspo-save-name",
                                )
                                inspo_save_btn = gr.Button(
                                    "把当前提示词存为灵感",
                                    variant="secondary",
                                    scale=2,
                                    elem_id="dv-inspo-save",
                                )
                                inspo_del_btn = gr.Button(
                                    "删除用户灵感",
                                    variant="secondary",
                                    scale=1,
                                    elem_id="dv-inspo-del",
                                )
                            inspo_status = gr.HTML("", elem_id="dv-inspo-status")

                        # —— LoRA：模型风格 ——
                        with gr.Column(
                            elem_id="dv-lora-block", elem_classes=["dv-style-block"]
                        ):
                            gr.HTML(
                                '<div class="dv-group-label">LoRA · 模型风格</div>'
                                '<p class="dv-help" style="margin:0 0 8px">'
                                "加载风格模型文件，<b>会占显存</b>。"
                                "与上方提示词灵感分开选，可叠加。8G 建议只挂 1 个。</p>"
                            )
                            with gr.Row():
                                style1_preview = gr.HTML(
                                    style_preview_html("（无风格）"),
                                    elem_id="dv-style-selected",
                                )
                                with gr.Column(scale=0, min_width=120):
                                    style_fav_btn = gr.Button(
                                        "收藏当前LoRA",
                                        variant="secondary",
                                        elem_id="dv-style-fav",
                                    )
                                    style_clear_btn = gr.Button(
                                        "清除 LoRA",
                                        variant="secondary",
                                        elem_id="dv-style-clear",
                                    )
                            with gr.Row(elem_id="dv-lora-filters"):
                                lora_cat = gr.Dropdown(
                                    choices=cats,
                                    value="全部",
                                    label="分类",
                                    scale=2,
                                    elem_id="dv-lora-cat",
                                )
                                lora_nsfw = gr.Checkbox(
                                    value=show_nsfw0,
                                    label="成人向",
                                    elem_id="dv-lora-nsfw",
                                )
                            w1 = gr.Radio(
                                choices=weights,
                                value=default_w,
                                label="LoRA 强度",
                                elem_id="dv-style-weight",
                            )
                            style_cards_lora = gr.Gallery(
                                value=lora_card_items,
                                label="LoRA 图库 · 点选",
                                columns=6,
                                rows=2,
                                height=220,
                                object_fit="cover",
                                allow_preview=False,
                                interactive=True,
                                selected_index=0,
                                elem_id="dv-style-cards-lora",
                            )
                            style_manage_status = gr.HTML(
                                "", elem_id="dv-style-manage-status"
                            )

                        # 兼容图库回填
                        style2 = gr.Dropdown(
                            choices=styles0, value="（无风格）", visible=False
                        )
                        w2 = gr.Dropdown(
                            choices=weights, value=default_w_light, visible=False
                        )
                        # 兼容旧接线占位（已废弃 prompt_style 槽）
                        prompt_style_state = gr.State("（无）")

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
                            _cs = custom_size_limits()
                            size_box = gr.HTML(
                                size_badge_html(aspects[0], default_q)
                            )
                            vram_tip_box = gr.HTML(
                                vram_tip_html(
                                    aspects[0], default_q, False, None, None, default_mode
                                ),
                                elem_id="dv-vram-tip",
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
                                custom_size_ck = gr.Checkbox(
                                    value=False,
                                    label="自定义尺寸（开启后锁定上方比例与分辨率档）",
                                    elem_id="dv-custom-size-ck",
                                )
                                # 不在 Number 上设 minimum：输入 2048 时中间态 2/20/204
                                # 会触发 Gradio 前端 min 校验狂弹 Error。真正钳制在 clamp_custom_size。
                                with gr.Group(visible=False, elem_id="dv-custom-size-group") as custom_size_row:
                                    with gr.Row(elem_id="dv-custom-size-row"):
                                        custom_w = gr.Number(
                                            value=_cs["default_width"],
                                            label="宽（px）",
                                            precision=0,
                                            step=_cs["step"],
                                            elem_id="dv-custom-w",
                                        )
                                        custom_h = gr.Number(
                                            value=_cs["default_height"],
                                            label="高（px）",
                                            precision=0,
                                            step=_cs["step"],
                                            elem_id="dv-custom-h",
                                        )
                                    gr.Markdown(
                                        f"步进 {_cs['step']}，有效范围 {_cs['min']}–{_cs['max']}（生成时自动取整夹紧，"
                                        "输入过程中不必完整才合法）。"
                                        "开启后上方「比例 / 分辨率」会灰掉；步数仍沿用锁定前选中的分辨率档。"
                                        "更小更省显存；更大吃 16G/24G。",
                                        elem_id="dv-custom-size-help",
                                    )
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

                            def _refresh_size_ui(ar, q, c_on, cw, ch, mm):
                                # 输入半截/空值时用 clamp 兜底，避免预览炸掉
                                try:
                                    if c_on and (cw is not None or ch is not None):
                                        cw, ch = clamp_custom_size(
                                            cw if cw is not None else _cs["default_width"],
                                            ch if ch is not None else _cs["default_height"],
                                        )
                                except Exception:
                                    pass
                                return (
                                    size_badge_html(ar, q, c_on, cw, ch, mm),
                                    vram_tip_html(ar, q, c_on, cw, ch, mm),
                                )

                            def _on_custom_toggle(c_on, ar, q, cw, ch, mm):
                                """开自定义：锁定比例/分辨率档，显示宽高；关则恢复。"""
                                locked = bool(c_on)
                                if locked:
                                    try:
                                        pw, ph = preview_size(
                                            ar, normalize_quality_label(q)
                                        )
                                    except Exception:
                                        lim = custom_size_limits()
                                        pw, ph = lim["default_width"], lim["default_height"]
                                    cw, ch = pw, ph
                                    badge, tip = _refresh_size_ui(
                                        ar, q, True, cw, ch, mm
                                    )
                                    return (
                                        gr.update(visible=True),
                                        gr.update(value=cw),
                                        gr.update(value=ch),
                                        gr.update(interactive=False),  # aspect
                                        gr.update(interactive=False),  # quality
                                        badge,
                                        tip,
                                    )
                                badge, tip = _refresh_size_ui(
                                    ar, q, False, cw, ch, mm
                                )
                                return (
                                    gr.update(visible=False),
                                    gr.skip(),
                                    gr.skip(),
                                    gr.update(interactive=True),
                                    gr.update(interactive=True),
                                    badge,
                                    tip,
                                )

                            # size / vram tip refreshers
                            for _comp in (quality, aspect, model_mode):
                                _comp.change(
                                    fn=_refresh_size_ui,
                                    inputs=[
                                        aspect,
                                        quality,
                                        custom_size_ck,
                                        custom_w,
                                        custom_h,
                                        model_mode,
                                    ],
                                    outputs=[size_box, vram_tip_box],
                                )
                            custom_size_ck.change(
                                fn=_on_custom_toggle,
                                inputs=[
                                    custom_size_ck,
                                    aspect,
                                    quality,
                                    custom_w,
                                    custom_h,
                                    model_mode,
                                ],
                                outputs=[
                                    custom_size_row,
                                    custom_w,
                                    custom_h,
                                    aspect,
                                    quality,
                                    size_box,
                                    vram_tip_box,
                                ],
                            )
                            custom_w.change(
                                fn=_refresh_size_ui,
                                inputs=[
                                    aspect,
                                    quality,
                                    custom_size_ck,
                                    custom_w,
                                    custom_h,
                                    model_mode,
                                ],
                                outputs=[size_box, vram_tip_box],
                            )
                            custom_h.change(
                                fn=_refresh_size_ui,
                                inputs=[
                                    aspect,
                                    quality,
                                    custom_size_ck,
                                    custom_w,
                                    custom_h,
                                    model_mode,
                                ],
                                outputs=[size_box, vram_tip_box],
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
                    if not st or st.is_prompt():
                        return default_w
                    w = float(st.default_weight or 0.85)
                    if w <= 0.7:
                        return default_w_light if default_w_light in weights else weights[0]
                    if w >= 0.95:
                        heavy = "重 (1.0)"
                        return heavy if heavy in weights else weights[-1]
                    return default_w if default_w in weights else weights[len(weights) // 2]

                def _sync_style_from_dd(lab: str):
                    lab = lab or "（无风格）"
                    return lab, style_preview_html(lab)

                style1.change(
                    fn=_sync_style_from_dd,
                    inputs=style1,
                    outputs=[style1_state, style1_preview],
                )

                def _gallery_idx(evt: gr.SelectData) -> int:
                    idx = evt.index
                    try:
                        if isinstance(idx, (list, tuple)):
                            if len(idx) >= 2:
                                return int(idx[0]) * 6 + int(idx[1])
                            return int(idx[0])
                        return int(idx)
                    except Exception:
                        return -1

                def _on_pick_inspo(evt: gr.SelectData, cat_f, only_fav):
                    """点选提示词灵感 → 预览 + 写入提示词框。"""
                    empty = "（无）"
                    idx = _gallery_idx(evt)
                    _, labels = inspiration_gallery_data(
                        cat_f or "全部", bool(only_fav)
                    )
                    if idx < 0 or idx >= len(labels):
                        return empty, inspo_preview_html(empty), gr.skip()
                    chosen = labels[idx]
                    if str(chosen).startswith("（无"):
                        return empty, inspo_preview_html(empty), gr.skip()
                    ins = resolve_inspiration(chosen)
                    print(f"[inspo] idx={idx} -> {chosen!r}", flush=True)
                    if ins and (ins.prompt or "").strip():
                        return chosen, inspo_preview_html(chosen), ins.prompt
                    return chosen, inspo_preview_html(chosen), gr.skip()

                def _refresh_inspo_gal(cat_f, only_fav):
                    items, _ = inspiration_gallery_data(
                        cat_f or "全部", bool(only_fav)
                    )
                    return gr.update(value=items)

                def _on_pick_lora(evt: gr.SelectData, cat_f, nsfw_f):
                    empty = "（无风格）"
                    idx = _gallery_idx(evt)
                    _, labels = _style_gallery_data(
                        bool(nsfw_f), cat_f or "全部", "LoRA"
                    )
                    if idx < 0 or idx >= len(labels):
                        return (
                            empty,
                            gr.update(value=empty),
                            style_preview_html(empty),
                            gr.update(value=default_w),
                        )
                    chosen = labels[idx]
                    st = resolve_style_name(chosen)
                    if st and st.is_prompt():
                        return (
                            empty,
                            gr.update(value=empty),
                            style_preview_html(empty),
                            gr.update(value=default_w),
                        )
                    print(f"[style] LoRA idx={idx} -> {chosen!r}", flush=True)
                    return (
                        chosen,
                        gr.update(value=chosen),
                        style_preview_html(chosen),
                        gr.update(value=_weight_label_for_style(chosen)),
                    )

                def _refresh_lora_gal(cat_f, nsfw_f):
                    items, _ = _style_gallery_data(
                        bool(nsfw_f), cat_f or "全部", "LoRA"
                    )
                    return gr.update(value=items)

                inspo_cat.change(
                    fn=_refresh_inspo_gal,
                    inputs=[inspo_cat, inspo_show_fav],
                    outputs=style_cards_inspo,
                )
                inspo_show_fav.change(
                    fn=_refresh_inspo_gal,
                    inputs=[inspo_cat, inspo_show_fav],
                    outputs=style_cards_inspo,
                )
                style_cards_inspo.select(
                    fn=_on_pick_inspo,
                    inputs=[inspo_cat, inspo_show_fav],
                    outputs=[inspo_state, inspo_preview, prompt],
                )

                lora_cat.change(
                    fn=_refresh_lora_gal,
                    inputs=[lora_cat, lora_nsfw],
                    outputs=style_cards_lora,
                )
                lora_nsfw.change(
                    fn=_refresh_lora_gal,
                    inputs=[lora_cat, lora_nsfw],
                    outputs=style_cards_lora,
                )
                style_cards_lora.select(
                    fn=_on_pick_lora,
                    inputs=[lora_cat, lora_nsfw],
                    outputs=[style1_state, style1, style1_preview, w1],
                )

                def _on_inspo_fav(lab: str, cat_f, only_fav):
                    ins = resolve_inspiration(lab)
                    if not ins:
                        return (
                            '<div class="dv-status err">请先点选一条灵感</div>',
                            gr.skip(),
                            inspo_preview_html(lab or "（无）"),
                        )
                    _now, msg = inspo_toggle_favorite(ins.id)
                    items, _ = inspiration_gallery_data(
                        cat_f or "全部", bool(only_fav)
                    )
                    return (
                        f'<div class="dv-status ok">{html_lib.escape(msg)}</div>',
                        gr.update(value=items),
                        inspo_preview_html(lab),
                    )

                def _on_inspo_save(name: str, prompt_text: str, cat_f, only_fav):
                    ok, msg, ins = save_user_inspiration(
                        name=name or "",
                        prompt=prompt_text or "",
                    )
                    cls = "ok" if ok else "err"
                    items, _ = inspiration_gallery_data(
                        cat_f or "全部", bool(only_fav)
                    )
                    if ok and ins:
                        lab = ins.label()
                        return (
                            f'<div class="dv-status {cls}">{html_lib.escape(msg)}</div>',
                            gr.update(value=items),
                            lab,
                            inspo_preview_html(lab),
                            gr.update(value=""),
                        )
                    return (
                        f'<div class="dv-status {cls}">{html_lib.escape(msg)}</div>',
                        gr.update(value=items),
                        gr.skip(),
                        gr.skip(),
                        gr.skip(),
                    )

                def _on_inspo_del(lab: str, cat_f, only_fav):
                    ins = resolve_inspiration(lab)
                    if not ins:
                        return (
                            '<div class="dv-status err">请先选择要删除的用户灵感</div>',
                            gr.skip(),
                            gr.skip(),
                            gr.skip(),
                        )
                    ok, msg = delete_user_inspiration(ins.id)
                    cls = "ok" if ok else "err"
                    items, _ = inspiration_gallery_data(
                        cat_f or "全部", bool(only_fav)
                    )
                    if ok:
                        empty = "（无）"
                        return (
                            f'<div class="dv-status {cls}">{html_lib.escape(msg)}</div>',
                            gr.update(value=items),
                            empty,
                            inspo_preview_html(empty),
                        )
                    return (
                        f'<div class="dv-status {cls}">{html_lib.escape(msg)}</div>',
                        gr.update(value=items),
                        gr.skip(),
                        gr.skip(),
                    )

                def _on_lora_fav(lab: str):
                    st = resolve_style_name(lab)
                    if not st:
                        return (
                            '<div class="dv-status err">请先点选一个 LoRA</div>',
                            style_preview_html(lab or "（无风格）"),
                        )
                    _now, msg = toggle_favorite(st.id)
                    return (
                        f'<div class="dv-status ok">{html_lib.escape(msg)}</div>',
                        style_preview_html(lab),
                    )

                inspo_fav_btn.click(
                    fn=_on_inspo_fav,
                    inputs=[inspo_state, inspo_cat, inspo_show_fav],
                    outputs=[inspo_status, style_cards_inspo, inspo_preview],
                )
                inspo_save_btn.click(
                    fn=_on_inspo_save,
                    inputs=[inspo_save_name, prompt, inspo_cat, inspo_show_fav],
                    outputs=[
                        inspo_status,
                        style_cards_inspo,
                        inspo_state,
                        inspo_preview,
                        inspo_save_name,
                    ],
                )
                inspo_del_btn.click(
                    fn=_on_inspo_del,
                    inputs=[inspo_state, inspo_cat, inspo_show_fav],
                    outputs=[
                        inspo_status,
                        style_cards_inspo,
                        inspo_state,
                        inspo_preview,
                    ],
                )
                inspo_clear_btn.click(
                    fn=lambda: (
                        "（无）",
                        inspo_preview_html("（无）"),
                        '<div class="dv-status">已清除提示词灵感选用</div>',
                    ),
                    outputs=[inspo_state, inspo_preview, inspo_status],
                )
                style_fav_btn.click(
                    fn=_on_lora_fav,
                    inputs=[style1_state],
                    outputs=[style_manage_status, style1_preview],
                )
                style_clear_btn.click(
                    fn=lambda: (
                        "（无风格）",
                        gr.update(value="（无风格）"),
                        style_preview_html("（无风格）"),
                        gr.update(value=default_w),
                        '<div class="dv-status">已清除 LoRA</div>',
                    ),
                    outputs=[
                        style1_state,
                        style1,
                        style1_preview,
                        w1,
                        style_manage_status,
                    ],
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

                def _run_t2i(
                    p, mm, ar, q, s1, ww1, s2, ww2, sd, creat, n_img,
                    c_on, cw, ch,
                ):
                    import threading
                    import time as _time

                    stop_flag["stop"] = False
                    # 8GB：只挂 1 个风格 LoRA；提示词灵感已在 UI 写入 prompt 框
                    s2 = "（无风格）"
                    ww2 = "轻 (0.6)"
                    empty_dims = image_dims_html(None)
                    use_custom = bool(c_on)
                    if use_custom:
                        try:
                            cw_i, ch_i = clamp_custom_size(cw, ch)
                        except Exception:
                            cw_i, ch_i = custom_size_limits()["default_width"], custom_size_limits()["default_height"]
                    else:
                        cw_i, ch_i = None, None
                    st = resolve_style_name(s1)
                    if st and st.is_prompt():
                        st = None
                    pst = None  # 灵感不在 generate 注入，已在文本框
                    size_note = f" custom={cw_i}x{ch_i}" if use_custom else ""
                    print(
                        f"\n[gen] start  model={mm}  {ar}  {q}  n={n_img}  "
                        f"lora={s1!r}->{st.name if st else None}  "
                        f"w={ww1}{size_note}",
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
                                        st,
                                        _weight_value(ww1),
                                        None,
                                        _weight_value(ww2),
                                        seed=_seed,
                                        model_mode_label=mm,
                                        on_progress=on_prog,
                                        style1_label=s1 if st else "（无风格）",
                                        style2_label="（无风格）",
                                        weight1_label=ww1,
                                        weight2_label=ww2,
                                        creativity=creat_i,
                                        custom_size=use_custom,
                                        custom_width=cw_i,
                                        custom_height=ch_i,
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
                    if st:
                        applied.append(f"LoRA:{st.name}")
                    if pst:
                        applied.append(f"灵感:{pst.name}")
                    extra = (
                        (" · " + " + ".join(applied)) if applied else " · 无加料"
                    )
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

            # ========== LoRA 模型风格（浏览）==========
            with gr.Tab("LoRA 风格"):
                gr.HTML(
                    '<div class="dv-section-head"><span class="eyebrow">MODEL STYLE</span>'
                    "<h2>LoRA · 模型风格</h2>"
                    "<p><b>性质：</b>额外加载风格模型文件，会占用显存、略增加出图时间。"
                    "适合把整张图换成某种画风/质感。"
                    "在「文生图」里点卡选用；本页仅浏览详情与来源。</p></div>"
                )
                with gr.Row():
                    nsfw_lora_browse = gr.Checkbox(value=False, label="显示成人向")
                    cat_lora_browse = gr.Dropdown(
                        choices=cats, value="全部", label="分类"
                    )
                gal_lora = gr.HTML(gallery_html(False, "全部", "LoRA"))
                nsfw_lora_browse.change(
                    fn=lambda s, c: gallery_html(s, c, "LoRA"),
                    inputs=[nsfw_lora_browse, cat_lora_browse],
                    outputs=gal_lora,
                )
                cat_lora_browse.change(
                    fn=lambda s, c: gallery_html(s, c, "LoRA"),
                    inputs=[nsfw_lora_browse, cat_lora_browse],
                    outputs=gal_lora,
                )

            # ========== 提示词灵感（浏览）==========
            with gr.Tab("提示词灵感"):
                gr.HTML(
                    '<div class="dv-section-head"><span class="eyebrow">PROMPT INSPO</span>'
                    "<h2>提示词灵感</h2>"
                    "<p>达芬七精选 + 各分类完整中文提示词。点选后<strong>写入文生图提示词框</strong>，"
                    "可再改，可与 LoRA 同开。本页仅浏览；收藏/自建在文生图操作。</p></div>"
                )
                inspo_browse_cat = gr.Dropdown(
                    choices=inspiration_categories(), value="全部", label="分类"
                )

                def _inspo_browse_html(cat_f: str) -> str:
                    cards = []
                    for ins in load_inspirations():
                        if not ins.in_category(cat_f or "全部"):
                            continue
                        src = _thumb_uri(ins.cover_path)
                        img = (
                            f'<img src="{src}" alt="{html_lib.escape(ins.name)}" loading="lazy"/>'
                            if src
                            else '<div style="aspect-ratio:3/4;opacity:.5">无封面</div>'
                        )
                        head = (ins.prompt or "")[:80]
                        cards.append(
                            f'<div class="dv-card">{img}<div class="body">'
                            f'<p class="title">{html_lib.escape(ins.name)}</p>'
                            f'<p class="meta">{html_lib.escape(" / ".join(ins.cats()[:2]))}<br/>'
                            f"{html_lib.escape(head)}{'…' if len(ins.prompt or '') > 80 else ''}</p>"
                            f"</div></div>"
                        )
                    return (
                        f'<div class="dv-gallery">{"".join(cards) or "<p>该分类暂无灵感</p>"}</div>'
                    )

                gal_inspo = gr.HTML(_inspo_browse_html("全部"))
                inspo_browse_cat.change(
                    fn=_inspo_browse_html,
                    inputs=inspo_browse_cat,
                    outputs=gal_inspo,
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
                style1_state,  # LoRA 槽
                w1,
                style2,
                w2,
                seed,
                creativity,
                num_images,
                custom_size_ck,
                custom_w,
                custom_h,
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
