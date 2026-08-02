# Z-Image 升级包 backlog · 目标 v1.5.x

状态：进行中（2026-08-02）— 第 1 项代码已落地，待真机验收  
原则：傻瓜、8G 优先、功能可发现但不吓退小白。

> **下一对外可发补丁：v1.4.5 风格增强（无图生图）**  
> 详见 → [`RELEASE-1.4.5.md`](./RELEASE-1.4.5.md)  
> **评论区驱动优先级** → [`COMMENT-FEEDBACK-v1.5.md`](./COMMENT-FEEDBACK-v1.5.md)  
> 本文件仍管 **1.5.x 中长期**。1.4.5 做完再集中冲这里未完成项。  
> 旧原则全部保留；1.4.5 额外纪律见该文档 §0。  
>  
> **1.5 建议排序（评论）：** 更小分辨率/6G 省显存 → 图生图 → FAQ/镜像 → 双 LoRA 槽

---

## 1. 高级设置 · 自定义尺寸 + 显存预警

**状态：已实现（代码）** · 待 8G 真机点验

### 需求

- 高级区增加 **自定义宽高**（或长边 + 比例推导），可比预设更小（6G 友好）或更大（24G）。  
- 根据用户 **CUDA 显存** 给上限预警，而不是静默 OOM。

### 实现摘要

| 项 | 方案 |
|----|------|
| UI | 高级设置：`自定义尺寸` 开关；宽/高 Number（步进 8）；开时从当前预设填入 |
| 默认 | 关 = 仍用 720/1024/1280/1440 档（与 v1.4 一致） |
| 取整 | `clamp_custom_size`：`% step == 0`，min 256 / max 2048（`defaults.yaml`） |
| 显存 | `system_stats.size_vram_advice` + Comfy/torch `vram_total_gb` |
| 文案 | 黄字 warn / 红字 danger；自定义始终显示 tip；预设仅超 soft 才显示 |
| 图库 | `GenRecord.extra` 写 `width`/`height`/`custom_size` |

#### 长边建议上限（FP8 + 单 LoRA 粗算，需 2080 8G 实测校准）

| 检测显存 | 建议 max 长边 | 说明 |
|----------|----------------|------|
| ≤ 6 GB | 768 | 默认引导用更小 |
| 8 GB | 1024（峰值可试 1280） | 现状主力 |
| 12 GB | 1280–1440 | |
| 16 GB+ | 1440–1600 | |
| 24 GB+ | 1600–2048 | 高级用户 |

GGUF 档可再放宽一档建议；BF16 收紧一档。

### 验收

- [ ] 自定义 512² 在 8G 能出  
- [x] 自定义超建议值有可见预警（逻辑/UI 已接，待肉眼看一眼）  
- [x] 关闭自定义后行为与 v1.4 一致（代码路径）  
- [x] 图库记录实际宽高（`extra.width/height`）  

### 涉及文件

- `app/ui/app_ui.py` 高级区 + size badge / vram tip  
- `app/core/generate.py` `clamp_custom_size` / `txt2img` 入参  
- `app/core/system_stats.py` `get_vram_total_gb` / `size_vram_advice`  
- `app/config/defaults.yaml` `custom_size` + `vram_long_edge`  
- `app/core/history.py` 详情展示尺寸  
- `app/ui/theme.css` `.dv-vram-tip`

---

## 2. 风格库编辑系统

> **1.4.5 先做子集**：LoRA / 提示词二分、收藏、自建提示词风格、好友墙署名。  
> 本条完整版（CivitAI 半自动、重编辑表单等）仍属 **1.5**；细节以 `RELEASE-1.4.5.md` 为补丁范围真源。

### 需求

- 用户自实验好的 LoRA：**保存为自己的风格**（名称、文件路径、触发词、默认强度、分类、封面、备注、CivitAI 链接）。  
- **分类**可扩展（用户后续会大批预设；含真实/二次元/… 及个人标签）。  
- 有 **CivitAI 预设** 入口（沿用现有 token / download 工具思路，UI 化或半自动）。  
- 封面：可本地生成（现有 `gen_style_covers`）或上传；灵感：开源/团队向封面（Adrian punk、阿哲等 Stanley 队人设——**仅灵感与授权素材，勿侵权**）。  
- **提示词风格** 与 **LoRA 风格** 数据/UI 分离（1.4.5 起落地）。  

### 建议数据模型

- 内置：`assets/styles/styles.json`（只读或升级时合并）  
- 用户：`userdata/styles_user.json` + `userdata/covers/`  
- 加载：`load_styles()` = 内置 ∪ 用户（用户同 id 可覆盖或强制 `user_` 前缀）  

### UI 草图

- 「风格」Tab 或设置旁：**我的风格**  
  - 列表 / 编辑表单 / 删除  
  - 「从当前选择另存为」  
  - 「扫描 loras 目录添加」  
- 分类筛选已支持 multi-category，编辑器写入 `categories[]`  

### 验收

- [ ] 不改内置 json 也能持久化用户风格  
- [ ] 重启后仍在图卡墙  
- [ ] 坏路径有提示  
- [ ] 打包发行时 **不携带** 用户 styles（空 userdata）  

### 涉及文件（预计）

- `app/core/styles.py`  
- `app/ui/app_ui.py` 新区块  
- `app/core/paths.py` `USER_STYLES`  
- 可选：`app/tools` 仅开发用，用户面不全量塞 download 脚本  

---

## 3. 基础图生图（img2img）

> ⛔ **明确不进 v1.4.5**。1.4.5 只做风格生态 + 轻管理（见 `RELEASE-1.4.5.md`）。

### 需求

- 傻瓜级：上传图 → 提示词 → 强度（弱/中/大改）→ 生成。  
- **8G 可玩但吃力**：默认更小尺寸，UI 明确提示。  

### 技术事实

- 工作流 json 仍有 `img2img.json` / `img2img_lora.json`。  
- `generate.py` 当前 **仅 txt2img**（img2img 函数曾在迭代中拿掉），需恢复并接 UI。  

### 8G 建议默认

| 项 | 建议 |
|----|------|
| 默认长边 | **768** 或 720 档 |
| 推荐上限 | 1024；自定义再跟显存预警 |
| 强度 | 弱改 0.45 / 中 0.65 / 大 0.85（defaults 已有） |
| LoRA | 单槽，与文生图一致 |
| GGUF | 可回落 FP8 img2img（旧逻辑） |

### 验收

- [ ] 上传 → 生成 → 进图库（mode=img2img）  
- [ ] 回填可用  
- [ ] 8G 上 768 连续 2 张不明显炸显存（允许释放按钮）  

### 涉及文件（预计）

- `app/core/generate.py` 恢复 `img2img` + `_apply_filename_prefix` / LoraLoader  
- `app/ui/app_ui.py` Tab 或文生图旁「图生图」  
- `app/workflows/img2img*.json`  

---

## 4. 非目标（本波不做）

- 海外网盘镜像  
- ControlNet / 视频 / 放大全家桶  
- 语音 TTS 进本包（另项目）  
- 自建 BT 分发为主渠道  

---

## 5. 版本与打包

- 功能齐后 bump → **v1.5.0**  
- 同步：`links.yaml`、README、`make_release_pack.ps1`、`slim_release_pack.ps1`  
- 再打整合包前跑 slim  

---

*Backlog owner: 达芬七 · 与 HANDOFF-2026-08-02 联动*
