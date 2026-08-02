# Davinci Seven · Z-Image UI

达芬七的本地 Z-Image 图形界面、风格系统、启动脚本和诊断工具。

这个仓库只放 UI 与装配层，不包含模型权重、LoRA、ComfyUI 引擎、用户图库或 45GB 发行包。普通用户请使用完整整合包；开发者可以把本仓库放在已有引擎旁边运行。

## 当前状态

- 远端当前快照：`v1.4.5-dev.6`
- 已包含：LoRA / 风格灵感双轨、中文提示词明示、收藏和用户风格、启动时版本与路径提示、诊断工具。
- 图生图不在当前开发快照中，见 `UPGRADE-BACKLOG-v1.5.md`。
- 硬件口径：当前主路径按 Windows + NVIDIA CUDA 设计，8GB 显存是主要目标。

## 开发运行

确保旁边存在 `ComfyUI-zimage` 引擎，然后运行：

```powershell
双击 启动.bat
# 或
 powershell -ExecutionPolicy Bypass -File .\start_ui.ps1
```

发布包、模型和媒体不在本仓库。教程视频原件位于 `E:\z-image\release-media`，风格与发布范围见 `RELEASE-1.4.5.md`、`OPEN-SOURCE.md` 和 `HANDOFF-2026-08-02.md`。

## 安全边界

不要提交 `userdata/`、API token、生成输出、模型权重、整合包压缩文件或本机日志。第三方 LoRA 的许可、署名和再分发条件以作者页面为准。
