# Davinci Seven · Z-Image UI

达芬七的本地 Z-Image 图形界面：一键出图、LoRA 与提示词灵感双轨、图库回填、诊断工具。

本仓库只放 **UI 与装配层**，不含模型权重、LoRA、ComfyUI 引擎、用户图库和整合包本体。
想开箱即用请下载完整整合包；开发者或 AI Agent 可按下面的说明在已有引擎旁边跑起来。

- 版本：`v1.4.5`（以 `app/brand/links.yaml` 为准）
- 目标硬件：Windows + NVIDIA CUDA，8GB 显存为主，6GB 可用 512 档
- 图生图不在 1.4.5 范围内，见 `UPGRADE-BACKLOG-v1.5.md`

---

## 给 AI Agent 的部署说明

把仓库链接交给 Agent，照下面顺序做即可。

### 1. 目录结构

UI 和引擎是两个平级目录：

```
<任意根目录>/
  ComfyUI-zimage/          ← 引擎（自备，见第 2 步）
    ComfyUI/main.py
    python/python.exe      ← 便携版 Python
  davinci-zimage/          ← 本仓库
    启动.bat
    app/
```

也可以把引擎放在本仓库内的 `engine/`，或用环境变量 `ENGINE_ROOT` 指定绝对路径。
查找顺序：`ENGINE_ROOT` → `./engine` → `../ComfyUI-zimage`。

### 2. 引擎与依赖

需要一个能跑 Z-Image 的 ComfyUI（建议便携版，自带 `python/python.exe`）。
UI 侧依赖：`gradio`、`requests`、`pyyaml`、`pillow`、`tqdm`、`psutil`、`websockets`
（`websockets` 用于读取真实出图进度，缺了会自动退回轮询，不影响出图）。

自定义节点：`ComfyUI-GGUF`（仅「极低显存 GGUF」档需要），其余档位用原生节点即可。

### 3. 模型文件放置

放到 `ComfyUI/models/` 下，文件名要一致，否则对应档位会报「引擎拒绝了这次任务」：

| 档位 | 文件 | 位置 |
|------|------|------|
| 标准 FP8（推荐） | `z-image-turbo-fp8-e4m3fn_量化版_低显加速.safetensors` | `models/diffusion_models/z-image/` |
| 高质量 BF16 | `z_image_turbo_bf16_完整版_效果更好.safetensors` | `models/diffusion_models/z-image/` |
| 极低显存 GGUF | `z_image_turbo-Q4_K_M.gguf` | `models/diffusion_models/` |
| 文本编码器（都要） | `qwen_3_4b.safetensors` | `models/text_encoders/z-image/` |
| VAE（都要） | `z-image-qwen.safetensors` | `models/vae/` |

基础模型来自 [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)。
文件名可在 `app/config/defaults.yaml` 里改成你自己的。

LoRA 放 `models/loras/`；`assets/styles/styles.json` 记录了每个风格对应的文件名与 Civitai 链接，
缺失的风格会自动从界面隐藏，不会报错。

### 4. 启动

```powershell
# 一步到位（自己拉起引擎并等待就绪）
.\启动.bat

# 或只起界面（引擎需另行启动在 7777）
& <引擎>\python\python.exe app\main.py --server_port 8888
```

端口：界面 `8888`、引擎 `7777`。端口被占用时会让你选「关掉 / 复用 / 退出」，不会直接杀进程。

### 5. 验证跑通

1. 打开 `http://127.0.0.1:8888`，顶部状态显示 **引擎 在线**
2. 「文生图」写一句提示词 → 点「生成画面」→ 能出图
3. 「提示词灵感」能看到 100 张封面卡，点一张会把提示词填进输入框
4. 「图库」能看到刚才那张图和它的参数

出错时双击 `导出诊断信息.bat`，会生成一份已脱敏的诊断 TXT（自动遮挡用户名和电脑名），可直接交给 AI 排查。

---

## 目录速查

| 路径 | 说明 |
|------|------|
| `app/main.py` | 入口 |
| `app/ui/app_ui.py` | 界面 |
| `app/ui/theme.css` · `app/ui/themes.py` | 布局与 7 套皮肤 |
| `app/core/generate.py` | 组工作流、调引擎 |
| `app/core/comfy_client.py` | 提交任务、读真实进度、按 prompt_id 取结果 |
| `app/config/defaults.yaml` | 模型档位、分辨率档、端口 |
| `assets/styles/styles.json` | LoRA 风格库 |
| `assets/prompts/inspirations.json` | 提示词灵感库（100 条） |
| `_dev_tools/make_release_pack.ps1` | 打发行包（补丁 / UI / 完整） |

## 安全边界

不要提交 `userdata/`、API token、生成结果、模型权重、整合包压缩文件或本机日志。
第三方 LoRA 的许可、署名与再分发条件以作者页面为准；成人向内容仅供本地合法使用。
