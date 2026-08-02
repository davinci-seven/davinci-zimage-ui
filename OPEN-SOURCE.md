# 前端开源与共建说明（达芬七 · Z-Image UI）

## 结论先说

| 问题 | 建议 |
|------|------|
| **以前版本要不要 git？** | **要。** 不是为了「备份 45G 模型」，而是为了：**前端/装配可 diff、可回滚、可 PR、可打补丁标签**。 |
| **开什么源？** | 优先开 **UI + 装配脚本 + 风格 JSON + 文档**（本目录 `davinci-zimage` 思路）。**不要**把 `engine/` 权重、用户 `userdata/`、发行整包打进公开仓库。 |
| **皮肤 / 共建？** | 合理。主题在 `app/ui/themes.py` + `theme.css`；风格在 `assets/styles/`。有清晰边界就容易收 PR。 |

## 推荐仓库边界

```
开源仓库（建议名：davinci-zimage-ui 或 zimage-pack-ui）
  app/                 Gradio UI + core
  assets/styles/       styles.json + prompt_styles.json + covers（小图）
  assets/prompts/      灵感预设
  *.md / README / 启动脚本（不含大模型）
  .gitignore           排除 userdata、output、__pycache__、大权重

不开源 / 仅私有
  engine/              Comfy + python + 模型（45G 级）
  release/ 整包
  userdata/            用户图库与密钥
  ComfyUI-zimage/      本地引擎 sibling（若存在）
```

用户仍用「整包下载」；开发者 `git clone` 前端后指向已有 engine（`ENGINE_ROOT` 或 sibling）。

## Git 策略（本机）

1. **只在 `davinci-zimage/` 建仓**（或 monorepo 但 ignore 大目录）  
2. **Tag**：`v1.4.0` 发行点、`v1.4.5-dev` 补丁开发点  
3. **不要**把 `release/达芬七-ZImage-一键出图包-*` 当 git 历史  
4. 旧版本：有 tag 就够；不必为每个网盘 7z 留 git 副本  

本树已提供 `.gitignore`；首次：

```powershell
cd E:\z-image\davinci-zimage
git init
git add .
git status   # 确认没有 models / userdata 大文件
git commit -m "chore: baseline UI for v1.4.5-dev style pack"
git tag v1.4.5-dev
```

推到 GitHub/Gitee 前：删掉 token、检查 `userdata/civitai_api_token.txt` 未被 track。

## 欢迎共建什么

- 新 **主题皮肤**（`themes.py` / CSS 变量）  
- 新 **提示词风格**（`prompt_styles.json`，须本地小尺寸自测 + `source` 署名）  
- 无障碍 / 文案 / 启动脚本改进  
- 文档与多语言  

暂不默认收：要求整包重依赖、未验证的巨大 LoRA 二进制、图生图大改（见 1.5 路线）。

## 署名与好友墙

外源风格必须带 `source.credit` + `source.url`。  
关于页会列出致谢——共建即宣传，双向受益。

## 许可证（待你拍板再写死）

建议方向（未最终法律意见）：

- **UI 代码**：MIT 或 Apache-2.0  
- **你写的提示词预设**：与包同许可或 CC-BY  
- **第三方 LoRA / 上游 Skill**：仍归原作者；仓库只放引用与适配说明，不 redistributable 权重则不要提交  

正式开源前：加 `LICENSE`、扫一遍 covers 是否可再分发。

---

*与 RELEASE-1.4.5.md 配套 · 达芬七*
