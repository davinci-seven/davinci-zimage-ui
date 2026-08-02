# 达芬七 · Z-Image v1.1 自检清单

## 已验证（2026-07-26）

- [x] GGUF 文生图：qwen3 文本编码改 safetensors
- [x] **风格应用修复**：选风格时强制 FP8；补齐触发词（如 DisneyIZT）
- [x] Disney 风格 FP8 实测出图成功
- [x] 风格库 33 个 + 分类（整体风格/质感增强/角色/成人向）+ Civitai 链接与商用备注
- [x] 四套界面皮肤：Editorial / Noir / Gallery / Violet
- [x] 顶栏状态 sticky 常驻
- [x] 禁用坏节点：nunchaku / Toolbox / faceanalysis / pulid / instantid（加快启动）
- [x] 关于页改为「一键出图」文案，去掉「傻瓜」
- [x] 图库回填

## 用户验收建议

1. 双击启动.bat，看状态栏「引擎 在线」
2. 默认 FP8 + 无风格，生成一张
3. 选「Realistic Snapshot」+ 强度「中」，再生成
4. 切换 GGUF 无风格，生成一张
5. 图库打开历史 → 一键回填
6. 检查页面无开发碎碎念、路径调试字样

## 已知说明（非阻塞）

- Comfy 日志里 `lora key not loaded` 多为警告：部分层键名不完全匹配，图仍可出；风格请优先 FP8
- 极大体积 LoRA（约 600MB+）加载更慢
