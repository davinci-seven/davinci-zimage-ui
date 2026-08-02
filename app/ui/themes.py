"""Theme tokens — applied by injecting CSS variables into :root (no JS).

A theme is 15 colour tokens. Themes listed in THEME_EXTRA_CSS may also ship a
small block of their own rules (type, texture, one signature detail); themes
without an entry there render exactly as they always have.
"""
from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "editorial": {
        "--bg": "#f3eee6",
        "--bg-deep": "#e8e0d4",
        "--card": "#fffcf7",
        "--ink": "#1a1614",
        "--muted": "#6b625a",
        "--faint": "#9a9086",
        "--line": "rgba(26, 22, 20, 0.10)",
        "--line2": "rgba(26, 22, 20, 0.16)",
        "--accent": "#c45c26",
        "--accent2": "#8b3a1a",
        "--accent-soft": "rgba(196, 92, 38, 0.12)",
        "--ok": "#2f6b4f",
        "--danger": "#a33b3b",
        "--shadow": "0 18px 50px rgba(40, 28, 18, 0.10)",
        "--btn-fg": "#ffffff",
    },
    "noir": {
        # 深色但文字够亮；卡片与背景分层，避免死黑
        "--bg": "#141418",
        "--bg-deep": "#1c1c22",
        "--card": "#26262e",
        "--ink": "#faf8f5",
        "--muted": "#d8d0c6",
        "--faint": "#a8a098",
        "--line": "rgba(250, 248, 245, 0.12)",
        "--line2": "rgba(250, 248, 245, 0.22)",
        "--accent": "#f0c67a",
        "--accent2": "#d4a04a",
        "--accent-soft": "rgba(240, 198, 122, 0.22)",
        "--ok": "#8fd9ad",
        "--danger": "#f5a5a0",
        "--shadow": "0 18px 48px rgba(0, 0, 0, 0.45)",
        "--btn-fg": "#1a1614",
    },
    "gallery": {
        "--bg": "#fafafa",
        "--bg-deep": "#f0f0f0",
        "--card": "#ffffff",
        "--ink": "#111111",
        "--muted": "#555555",
        "--faint": "#888888",
        "--line": "rgba(0, 0, 0, 0.08)",
        "--line2": "rgba(0, 0, 0, 0.14)",
        "--accent": "#111111",
        "--accent2": "#333333",
        "--accent-soft": "rgba(0, 0, 0, 0.05)",
        "--ok": "#1b7a4e",
        "--danger": "#b00020",
        "--shadow": "0 8px 30px rgba(0, 0, 0, 0.06)",
        "--btn-fg": "#ffffff",
    },
    "violet": {
        "--bg": "#f6f3ff",
        "--bg-deep": "#ebe4ff",
        "--card": "#ffffff",
        "--ink": "#1c1433",
        "--muted": "#5c5278",
        "--faint": "#8e85a8",
        "--line": "rgba(28, 20, 51, 0.10)",
        "--line2": "rgba(28, 20, 51, 0.16)",
        "--accent": "#6d28d9",
        "--accent2": "#4c1d95",
        "--accent-soft": "rgba(109, 40, 217, 0.10)",
        "--ok": "#0f766e",
        "--danger": "#be123c",
        "--shadow": "0 16px 40px rgba(76, 29, 149, 0.10)",
        "--btn-fg": "#ffffff",
    },
    # ---- 以下三套带专属字体与质感 ----
    "cyanotype": {
        # 氰版照相：手工纸底，全部用普鲁士蓝印刷，连正文墨色都是蓝的
        "--bg": "#e7e1d3",
        "--bg-deep": "#d8d0be",
        "--card": "#f6f3ea",
        "--ink": "#12253f",
        "--muted": "#47607f",
        "--faint": "#6f8296",
        "--line": "rgba(18, 37, 63, 0.14)",
        "--line2": "rgba(18, 37, 63, 0.26)",
        "--accent": "#1d5aa0",
        "--accent2": "#0e3566",
        "--accent-soft": "rgba(29, 90, 160, 0.12)",
        "--ok": "#2a6b5f",
        "--danger": "#8c3a2c",
        "--shadow": "0 16px 40px rgba(18, 37, 63, 0.14)",
        "--btn-fg": "#f6f3ea",
    },
    "mineral": {
        # 青绿山水：绢本作底，石青石绿只落在细节上，朱砂只给印章
        "--bg": "#eae4d4",
        "--bg-deep": "#ded6c2",
        "--card": "#f7f3e8",
        "--ink": "#23282a",
        "--muted": "#55625c",
        "--faint": "#79817a",
        "--line": "rgba(35, 40, 42, 0.13)",
        "--line2": "rgba(35, 40, 42, 0.24)",
        "--accent": "#2f6b7a",
        "--accent2": "#3f7a5f",
        "--accent-soft": "rgba(47, 107, 122, 0.12)",
        "--ok": "#3f7a5f",
        "--danger": "#9e3b2f",
        "--shadow": "0 14px 38px rgba(35, 45, 42, 0.13)",
        "--btn-fg": "#f7f3e8",
    },
    "darkroom": {
        # 暗房安全灯：暖调铁黑，纸白正文，光源在页面顶部
        "--bg": "#16110f",
        "--bg-deep": "#0f0b0a",
        "--card": "#241c19",
        "--ink": "#f7f0e6",
        "--muted": "#cbbdb0",
        "--faint": "#9a8c80",
        "--line": "rgba(247, 240, 230, 0.13)",
        "--line2": "rgba(247, 240, 230, 0.24)",
        "--accent": "#d98b45",
        "--accent2": "#b34a35",
        "--accent-soft": "rgba(217, 139, 69, 0.20)",
        "--ok": "#7fc9a3",
        "--danger": "#f0968a",
        "--shadow": "0 20px 52px rgba(0, 0, 0, 0.55)",
        "--btn-fg": "#16110f",
    },
}

# 每套的专属字体与签名细节。只用 Windows 自带字体，离线可用。
THEME_EXTRA_CSS: dict[str, str] = {
    "cyanotype": """
:root, html, body, .gradio-container {
  --font: "Sitka Banner", Cambria, Constantia, Georgia, "Songti SC", "SimSun", serif !important;
  --font-ui: "Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif !important;
  --radius: 4px !important;
}
/* 印相不匀：中心比边缘浅一点 */
html, body, .gradio-container {
  background-image: radial-gradient(120% 90% at 50% 0%,
      rgba(255, 255, 255, 0.55) 0%, rgba(255, 255, 255, 0) 62%) !important;
}
/* 签名：卡片内侧一道细蓝线，像印好的图版边框 */
.dv-card, .dv-style-preview-card, #dv-style-cards, .dv-hist-meta {
  box-shadow: inset 0 0 0 1px rgba(18, 37, 63, 0.10),
              inset 0 0 0 5px var(--card), inset 0 0 0 6px rgba(29, 90, 160, 0.30),
              var(--shadow) !important;
}
.dv-section-head h2, #dv-top h1 {
  font-weight: 600 !important;
  letter-spacing: 0.01em !important;
}
.dv-section-head .eyebrow, .dv-group-label {
  letter-spacing: 0.22em !important;
  text-transform: uppercase;
}
.gradio-container button, .gradio-container .gr-button { border-radius: 4px !important; }
#dv-gen-btn, #dv-gen-btn button { letter-spacing: 0.16em !important; font-weight: 700 !important; }
""",
    "mineral": """
:root, html, body, .gradio-container {
  --font: "KaiTi", "STKaiti", "Kaiti SC", "Palatino Linotype", Palatino, Georgia, serif !important;
  --font-ui: "Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui, sans-serif !important;
  --radius: 10px !important;
}
/* 绢的横纹，很淡 */
html, body, .gradio-container {
  background-image: repeating-linear-gradient(0deg,
      rgba(35, 40, 42, 0.022) 0px, rgba(35, 40, 42, 0.022) 1px,
      rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 4px) !important;
}
.dv-section-head h2, #dv-top h1 {
  font-size: 24px !important;
  font-weight: 400 !important;
  letter-spacing: 0.06em !important;
}
/* 章节线：石青过石绿 */
.dv-section-head { border-bottom: 1px solid transparent !important;
  border-image: linear-gradient(90deg, #2f6b7a 0%, #3f7a5f 38%, rgba(0,0,0,0) 100%) 1 !important;
  padding-bottom: 6px !important; }
/* 签名：生成按钮右端一枚朱砂印 */
#dv-gen-btn, #dv-gen-btn button { position: relative !important; letter-spacing: 0.18em !important;
  padding-right: 40px !important; }
#dv-gen-btn::after, #dv-gen-btn button::after {
  content: "印";
  position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
  width: 22px; height: 22px; line-height: 22px; text-align: center;
  font-family: "KaiTi", "STKaiti", serif; font-size: 13px;
  color: #f7f3e8; background: #9e3b2f; border-radius: 3px;
  box-shadow: 0 0 0 1px rgba(158, 59, 47, 0.45);
}
""",
    "darkroom": """
:root, html, body, .gradio-container {
  --font: "Bahnschrift SemiCondensed", "Bahnschrift", "Microsoft YaHei", "Segoe UI", sans-serif !important;
  --font-ui: "Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif !important;
  --radius: 6px !important;
}
/* 签名：顶部一盏安全灯，光落在工作区上 */
html, body, .gradio-container {
  background-image:
    radial-gradient(70% 42% at 50% -6%, rgba(179, 74, 53, 0.30) 0%, rgba(179, 74, 53, 0) 70%),
    radial-gradient(38% 26% at 50% -2%, rgba(217, 139, 69, 0.22) 0%, rgba(217, 139, 69, 0) 72%) !important;
  background-attachment: fixed !important;
}
.dv-section-head h2, #dv-top h1, .dv-group-label {
  text-transform: uppercase;
  letter-spacing: 0.10em !important;
}
.dv-section-head .eyebrow { letter-spacing: 0.24em !important; }
/* 显影：进度条像影像从药水里浮出来 */
.dv-progress-wrap > .dv-progress-fill, .dv-progress-wrap > i {
  background: linear-gradient(90deg,
      #5c3227 0%, #b34a35 42%, #d98b45 76%, #f6d3a4 100%) !important;
}
.dv-progress-wrap { background: #0c0908 !important; }
#dv-gen-btn, #dv-gen-btn button { letter-spacing: 0.14em !important; font-weight: 700 !important; }
""",
}

THEME_LABELS = {
    "editorial": "Editorial 杂志",
    "noir": "Noir 影院",
    "gallery": "Gallery 美术馆",
    "violet": "Violet 紫调",
    "cyanotype": "Cyanotype 蓝晒",
    "mineral": "Mineral 青绿",
    "darkroom": "Darkroom 暗房",
}

LABEL_TO_KEY = {v: k for k, v in THEME_LABELS.items()}


def theme_vars_css(theme_key: str) -> str:
    key = theme_key if theme_key in THEMES else "editorial"
    tokens = THEMES[key]
    body = "\n".join(f"  {k}: {v} !important;" for k, v in tokens.items())
    # Force variables onto :root / html / body / gradio root — no JS needed
    css = f"""
:root, html, body, .gradio-container, .main, .app {{
{body}
}}
"""
    return css + THEME_EXTRA_CSS.get(key, "")
