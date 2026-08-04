from __future__ import annotations

import yaml

from core.paths import BRAND_FILE
from core.styles import catalog_summary


def load_brand() -> dict:
    with open(BRAND_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def header_html(theme: str = "editorial") -> str:
    b = load_brand()
    name = b.get("product_name", "达芬七 · Z-Image")
    tagline = b.get("tagline", "本地一键出图")
    x_url = b.get("x_url", "https://x.com/davinci_seven")
    x_handle = b.get("x_handle", "@davinci_seven")
    version = b.get("version", "1.0.0")
    return f"""
    <div id="dv-chrome" data-theme="{theme}">
      <div id="dv-top">
        <div class="brand">
          <h1>{name}</h1>
          <span class="tag">{tagline} · v{version}</span>
        </div>
        <div class="actions">
          <a class="x" href="{x_url}" target="_blank" rel="noopener">关注 {x_handle}</a>
        </div>
      </div>
    </div>
    """


def about_markdown() -> str:
    b = load_brand()
    cat = catalog_summary()
    try:
        from core.inspirations import load_inspirations

        insp_n = len(load_inspirations())
    except Exception:
        insp_n = 0
    by = cat.get("by_category") or {}
    cat_lines = "\n".join(f"- **{k}**：{v} 个" for k, v in by.items()) or "- （暂无）"
    return f"""
## {b.get('product_name')}

本地 **Z-Image Turbo** 一键出图，面向 **8GB 显存**。  
作者 **{b.get('author')}** · X [{b.get('x_handle')}]({b.get('x_url')}) · 版本 **v{b.get('version', '1.0.0')}**

---

### 它能做什么

1. **文生图**：中文提示词直接画，可选预设与收藏  
2. **提示词灵感**：图卡选提示词（可分类/收藏/自建/编辑），写入输入框  
3. **LoRA · 模型风格**：加载风格文件，占显存；可收藏 / 自建 / 编辑 / 隐藏；可与提示词灵感同开  
4. **收藏 / 自建**：灵感与 LoRA 都能收藏、自建、改名换图；用不上的可隐藏  
5. **模型档位**：标准 FP8 / 极低显存 GGUF / 高质量 BF16  
6. **图库**：自动保存参数，支持一键回填  
7. **设置**：界面皮肤会记住  
8. **复制 / 全屏**：预览图可复制到剪贴板，点图可全屏查看  

### 模型怎么选

| 选项 | 适合 |
|------|------|
| 标准 FP8 | 日常首选 |
| 极低显存 GGUF | 电脑吃力时 |
| 高质量 BF16 | 细节更好，更吃显存 |

### 风格库（当前）

- LoRA：**{cat.get('lora_count', 0)}** 个 · 提示词灵感：**{insp_n}** 条（封面均为本地实际出图）

{cat_lines}

成人向默认隐藏，可在文生图勾选显示。提示词灵感默认「全部」，点选即填入；丑图不进库。

### 怎么用

1. 双击 `启动.bat`  
2. 等顶部 **引擎 在线**  
3. 写提示词或点「提示词灵感」填入 → 可选 LoRA → 右侧生成  
4. 到「图库」回看、一键回填  

### 你的数据在哪

- 图库：`userdata/gallery/`
- 提示词收藏：`userdata/favorites.json`  
- 提示词灵感收藏：`userdata/inspiration_favorites.json`  
- 自建灵感：`userdata/inspirations_user.json`  
- LoRA 收藏：`userdata/style_favorites.json`  
- 设置：`userdata/settings.yaml`  

### 开源与第三方

本包 **UI / 装配** 由达芬七整理；生成依赖开源与社区项目，请遵守各自许可证：

| 组件 | 说明 |
|------|------|
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | 本地生成后端 |
| [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) | 基础模型 |
| Gradio | 本界面框架 |
| 第三方 LoRA | 版权归作者；「风格」页有 Civitai 链接 |

完整清单见包内 `THIRD_PARTY.md`。成人向内容仅供本地合法使用。  
界面源码：[github.com/davinci-seven/davinci-zimage-ui](https://github.com/davinci-seven/davinci-zimage-ui)

### 反馈

更新与问题 → [{b.get('x_handle')}]({b.get('x_url')})
"""
