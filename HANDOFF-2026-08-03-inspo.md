# HANDOFF · 达芬七 Z-Image UI · 2026-08-03

---

## ✅ CC 已完成（2026-08-03 · dev.18）

**做法：全部 113 张封面用人眼过了一遍**（做成编号联络表 `_dev_scratch/qa/sheet_*.jpg`，
可疑的 10 张再放大到 500px 复核，不靠脚本打分）。

| 项 | 结果 |
|----|------|
| 删除 | **23 条**（12 擦边/裸露 · 11 名图严重不符或米色毛衣模板刷屏） |
| 改名 | **40 条**（去术语黑话，改成看图就能说出的名字） |
| 改分类 | **12 条**（`超现实` 是个筐，人像/风光/绘本全被塞进去了） |
| 重出封面 | **2 条**（连带改掉致命 prompt，见下） |
| 总数 | 113 → **90** |
| 版本 | `links.yaml` + `README.txt` → **1.4.5-dev.18** |
| 备份 | `inspirations.json.bak_cc_20260803_142115` |

**擦边删除清单**（放大复核确认）：烟雾发丝油画(裸胸油画)、孔版朋克、药铺古画、
偶像PV静帧、傻瓜机闪光夜、八十年代动画静帧、特艺彩情节剧、粗野混凝土巨构、
黄金时刻麦田(湿身透视)、妖精微光林间(薄纱透视)、拍立得刚显影(全裸肩)。

**根因（比逐条修更重要）**：
1. RSE 那批条目的 prompt 全是 `通用美女半身像 + 一个风格关键词`，
   风格关键词经常没渲染出来 → 名字写着「传真噪点/PS1雾夜/邵氏武侠」，图却是同一张棚拍美妆人像。
   **这类条目已整批清掉**，不要再用这个模板造新条目。
2. 「米色针织毛衣」接替了牛仔外套成为新模板，一度 7 张同款 → 只留风格真的成立的 4 张。
3. **prompt 里出现「留标题区」「留白诗意」「留白处保持纯净空白背景」，
   模型就会照做**：前者让它写乱码报头（车站告别 BIDYERS/HOFEY LUAND），
   后者让它画半张白纸（绘本雨夜咖啡馆）。两条 prompt 已重写为
   「表面为纯色无标识」「四边出血不留白边」，重出后干净。

**遗留（下次可做）**：
- 「气泡蓝天杂志封面」刊头是 `FR◦◦UR` 半遮字样，判定为风格化刊头予以保留，介意可重出。
- 「车站告别」重出后画面里是 3 个人（prompt 写的是 2 人），不影响可读性。
- 人像占比已够（职业/年龄/性别较分散），若要再加，**照 `insp_x_*` 那批的做法**：
  具体职业 + 完整着装 + 真实场景，那批 13 条全部一次通过。

---

**给 Claude Code（CC）/ 下一任 Agent 读这份就够开工。**  
Owner 诉求（原话大意）：**审美与图文对齐不行 → 请 CC 接手；先摸清进度，把「提示词灵感」图库的名字搞正确。**

---

## 0. 一句话现状

| 项 | 值 |
|----|-----|
| 产品 | 达芬七 · Z-Image 本地文生图壳（Gradio 6 + ComfyUI） |
| 工程路径 | `E:\z-image\davinci-zimage` |
| 版本号 | `app/brand/links.yaml` → **`1.4.5-dev.17`**（启动 bat/ps1 读这里） |
| 端口 | Comfy **7777** · UI **8888** |
| 启动 | 包根 `启动.bat` → `start_ui.ps1` |
| 当前焦点 | **提示词灵感库**质量与 **名 / 图 / 提示词** 三元一致 |
| 明确不做 | 图生图（img2img）→ 1.5；本 handoff 不扩功能面 |

---

## 1. 产品结构（别搞混）

主 Tab：

1. **文生图** — 主路径：提示词 + **提示词灵感**图卡 + **LoRA** 图卡  
2. **LoRA 风格** — 浏览 + 收藏  
3. **提示词灵感** — 浏览 + 收藏 / 自建 / 编辑  
4. 历史 / 设置 …

双轨：

- **提示词灵感** = 只填提示词框，**不挂 LoRA**  
- **LoRA** = 加载 safetensors，占显存  

用户自建灵感：`userdata/inspirations_user.json` + 可选封面 `userdata/covers/`  
内置灵感：`assets/prompts/inspirations.json` + 封面 `assets/styles/covers/`

核心代码：

| 文件 | 职责 |
|------|------|
| `app/ui/app_ui.py` | 界面、灵感/LoRA 图卡、收藏、一键存提示词 |
| `app/core/inspirations.py` | 加载/收藏/自建；**名称可空自动起名；封面可空自动文字卡** |
| `app/core/styles.py` | LoRA 目录、收藏、高级自定义 LoRA |
| `app/core/generate.py` | 调 Comfy 出图 |
| `app/config/defaults.yaml` | 分辨率档 512…2048、VRAM soft/hard |
| `app/tools/gen_inspo_covers.py` | 按灵感 prompt 批量小封面 |

---

## 2. 1.4.5 已落地（相对 1.4.0）

- 自定义尺寸 + VRAM 预警；质量档含大分辨率  
- LoRA / 提示词灵感拆开；默认分类 **全部**（已去掉「推荐 / 达芬七精选」入口）  
- 灵感预览不重复贴全文  
- 文生图 + 浏览页：收藏 / 只看收藏 / 自建 / 编辑用户项  
- **★ 把当前提示词存为灵感**（不必上传封面）  
- 高级：自定义 LoRA 登记到「我的」  
- 灵感库多次重建：RSE-24h / Multiverse / 本地重出 / X 向条目  

**图生图：不做。**

---

## 3. 灵感库：数据从哪来、踩过哪些坑

### 3.1 数据源（本机）

| 源 | 路径 | 说明 |
|----|------|------|
| RSE-24h curated | `F:\ClaudeCode\AI-Factory-Outputs\rse-24h\curated\` | 6 族 × 10 风格，每风格约 10 张精选 + json |
| Multiverse-6H | `F:\ClaudeCode\AI-Factory-Outputs\explore\multiverse_image_6h_20260802\` | 中文 prompt；`06_finalists/` 精选 |
| 本地 ZIT 重出 | Comfy `:7777` + `txt2img` | 封面应 **等于** 当前 `prompt` 的生成结果 |

### 3.2 当前文件

- 主库：`assets/prompts/inspirations.json`  
- 封面：`assets/styles/covers/{id}.jpg`（以及大量历史残留 jpg，勿全信文件名）  
- 备份一堆：`inspirations.json.bak_pre_*`（`matchfix` / `sfw` / `fullrse` / `diverse` …）  
- 脏脚本：`_dev_scratch/rebuild_*.py`、`fix_covers_match_prompts.py`、`restore_and_regen_broken.py`、`clean_sfw_inspo.py`  

### 3.3 已知灾难（必须读）

1. **名 ≠ 图（用户截图）**  
   - 例：「小队群像」显示面包、「办公室紧急会议」显示唱片机、「男女主双人互动」显示剪纸树。  
   - 原因：Multiverse 图文件与 `use_case`/prompt **匹配错误** 或旧封面未按新 prompt 覆盖；后来虽「按 prompt 重出」过，**审美与语义仍不可信，需人工/视觉验收**。  

2. **NSFW 漏进库**  
   - 例：`录像带跟踪线` 曾出现裸上身（RSE glamorous bust + VHS）。  
   - 用户要求：**灵感库全正经 SFW**，禁止擦边/裸露/漆皮 fetish。  

3. **同质化**  
   - RSE 大量 subject 模板是 `denim jacket + hoop earrings` → 曾一度 ~1/3 牛仔外套。  
   - 「材质裹人像」（裂纹漆金/全息/水银当衣服）用户明确说 **丑，要删**。  

4. **Agent 自伤 bug**  
   - 加固词写了「禁止裸露」，过滤器用 `裸 in prompt` → **误杀**，把大量 prompt 换成  
     `tasteful SFW scene for inspiration titled {name}`  
     导致图更对不上名。  
   - 已用 `inspirations.json.bak_pre_matchfix` 恢复 prompt 并再重出封面（dev.17）。  
   - **以后禁止用单字「裸」做 NSFW 检测。**  

5. **审美**  
   - 用户原话级评价：当前 Agent **审美不行、图识别不行** → **命名与选图请 CC 用人眼过一遍**，不要只信脚本 score。  

---

## 4. 当前任务（CC 优先）

### P0 — 把灵感图库「名字搞正确」

验收标准（用户级）：

1. 图卡上的 **中文名** 必须让人 **一眼说出画面内容**。  
2. **名 ↔ 封面像素内容 ↔ `prompt` 语义** 三者一致。  
3. **零 NSFW**（裸露、明显性暗示、fetish 材质人像）。  
4. 分类名是「好看灵感」语气，不是工艺术语堆砌；也 **不要** 名是 A 图却是 B。  

建议流程：

```
1. 导出清单：id | name | cover路径 | prompt前80字 | category
2. 批量打开 covers（或 contact sheet），人眼标：
   OK / 改名 / 换图 / 删除
3. 改名规则：
   - 看图起名，不要照搬 Multiverse use_case 若图已偏题
   - 短、中文、可点选理解（≤12～16 字）
4. 图不对：
   - 优先：用「当前正确 prompt」本地 512 重出封面
   - 或：从 RSE 同 style 文件夹挑「非牛仔、着装完整、好看」的另一张，并同步改 prompt 为该 json 的 prompt
5. 删：仍丑 / 仍擦边 / 仍同质刷屏
6. 写回 inspirations.json；bump version → 1.4.5-dev.18+
7. 冷启动 + Ctrl+F5 验收（Gradio 缩略图会缓存）
```

### P1 — 正经人像占比

用户明确：**别光找风景，要人像。**  
要求：着装完整、多样年龄/职业/情绪，禁止网红 bust 擦边。  
可参考已加的 `insp_x_*` 人像条目，但需视觉复核。

### P2 — 质量数量

宁缺毋滥。不必硬凑 100；**全绿比凑数重要**。  
RSE `film_cinema` 等 10 风格可以留，但每张都要过眼。

---

## 5. 技术约定（别再踩）

```text
inspirations.json 条目字段（关键）
  id, name, prompt, cover, category, categories[], tags[],
  tip, source{credit,url,note}, featured, kind=inspiration

封面解析
  app/core/inspirations.py → Inspiration.cover_path
  先 assets/styles/covers，再 userdata/covers，再 default_card

出图
  Comfy 必须 :7777 ready
  python app/tools/gen_inspo_covers.py --only id1,id2
  或 _dev_scratch 脚本（历史债务多，优先小步）

NSFW 检测
  禁止：if "裸" in text
  应用：nude/naked/topless/lingerie/latex fetish 等词 + 人眼

PowerShell
  多行 python -c 易炸；写 .py 再跑
```

UI 相关（已基本可用，非本 handoff 主线）：

- 默认分类「全部」；无「推荐/达芬七精选」  
- 一键存灵感；自建不强制上传图  
- LoRA 收藏 + 只看收藏  

---

## 6. 建议 CC 第一小时 checklist

- [ ] 读本文件 + 扫一眼 `inspirations.json` 条数与字段  
- [ ] 列 20 张「名气很大但易错」：小队群像、办公室紧急会议、男女主双人、车站告别、录像带跟踪线、两名女性协作、各 RSE 电影档  
- [ ] 打开对应 `assets/styles/covers/*.jpg` **看图**  
- [ ] 对不对：改名 / 重出 / 删除  
- [ ] 全库快速扫：NSFW、牛仔刷屏、材质裹人  
- [ ] 提交：`inspirations.json` + 变更封面 + `links.yaml` 版本 + 本 handoff 勾选更新  

---

## 7. 版本与发布

| 文件 | 作用 |
|------|------|
| `app/brand/links.yaml` | UI 显示版本（权威） |
| `README.txt` / `diagnostics.ps1` | 应同步末位 |
| `RELEASE-1.4.5.md` | 产品说明（可能落后于 dev 号） |

Git：UI 仓可能是 `davinci-zimage-ui`；**大图封面是否进 git 看体积**——可只提交 json + 精选封面。

---

## 8. 用户红线（摘要）

1. 灵感库 **正经 SFW only**  
2. **名字必须对得上图**  
3. 不要材质衣服刷脸、不要牛仔模板刷屏  
4. 要 **人像**，不要只剩风景静物  
5. 宁少好看，不要多而蠢  
6. 图生图先别做  

---

## 9. 交接语气

上一任 Agent 已把功能壳（收藏/自建/双轨/分辨率）堆得差不多，但 **灵感内容策展失败**。  
请 CC **以视觉验收为第一优先级**，把 `name` 校正到与封面一致；需要删库重建也可以，只要最终用户点开不再骂「名不对图 / 还有裸图」。

---

*写于 2026-08-03 · 版本线索 1.4.5-dev.17 · 路径 E:\z-image\davinci-zimage*  
*下一版 handoff 请更新本节版本号与「未关闭问题」列表。*
