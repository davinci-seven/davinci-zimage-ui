from __future__ import annotations

import yaml

from core.paths import BRAND_FILE
from core.styles import catalog_summary, friend_credits_markdown


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
    by = cat.get("by_category") or {}
    cat_lines = "\n".join(f"- **{k}**：{v} 个" for k, v in by.items()) or "- （暂无）"
    friends = friend_credits_markdown()
    return f"""
## {b.get('product_name')}

本地 **Z-Image Turbo** 一键出图，面向 **8GB 显存**。  
作者 **{b.get('author')}** · X [{b.get('x_handle')}]({b.get('x_url')}) · 版本 **v{b.get('version', '1.0.0')}**

---

### 它能做什么

1. **文生图**：中文提示词直接画，可选预设与收藏  
2. **风格库**：**LoRA 风格** + **提示词风格**（二选一；提示词风格不加载模型）  
3. **收藏 / 自建**：收藏风格；把当前提示词存成自己的提示词风格  
4. **模型档位**：标准 FP8 / 极低显存 GGUF / 高质量 BF16  
5. **图库**：自动保存参数，支持一键回填  
6. **设置**：界面皮肤会记住  
7. **复制 / 全屏**：预览图可复制到剪贴板，点图可全屏查看  

### 模型怎么选

| 选项 | 适合 |
|------|------|
| 标准 FP8 | 日常首选 |
| 极低显存 GGUF | 电脑吃力时 |
| 高质量 BF16 | 细节更好，更吃显存 |

### 风格库（当前）

- LoRA：**{cat.get('lora_count', 0)}** · 提示词：**{cat.get('prompt_count', 0)}** · 合计可用 **{cat.get('available', 0)}**

{cat_lines}

成人向默认隐藏，可在文生图勾选显示。提示词风格为**本地适配**，不保证与云端 Image 模型同款。

### 好友 / 开源致谢（提示词灵感）

{friends}

署名仅表示风格方向灵感与宣传致谢；样张与提示词已在本地 Z-Image 重适配。欢迎开源作者联系共建皮肤与风格。

### 怎么用

1. 双击 `启动.bat`  
2. 等顶部 **引擎 在线**  
3. 写提示词 → 选 LoRA 或提示词风格 → 右侧点生成  
4. 到「图库」回看、一键回填  

### 你的数据在哪

- 图库：`userdata/gallery/`
- 提示词收藏：`userdata/favorites.json`  
- 风格收藏：`userdata/style_favorites.json`  
- 自建风格：`userdata/styles_user.json`  
- 设置：`userdata/settings.yaml`  

### 开源与第三方

本包 **UI / 装配** 由达芬七整理；生成依赖开源与社区项目，请遵守各自许可证：

| 组件 | 说明 |
|------|------|
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | 本地生成后端 |
| [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) | 基础模型 |
| Gradio | 本界面框架 |
| 第三方 LoRA | 版权归作者；「风格」页有 Civitai 链接 |
| Punk-Skill 等 | 提示词灵感见上表致谢 |

完整清单见包内 `THIRD_PARTY.md`。成人向内容仅供本地合法使用。  
前端开源共建说明见 `OPEN-SOURCE.md`（若随包提供）。

### 反馈

更新与问题 → [{b.get('x_handle')}]({b.get('x_url')})
"""
