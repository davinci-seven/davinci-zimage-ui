# 第三方与开源声明

本一键出图包的 UI 与装配由 **达芬七（@davinci_seven）** 完成。下列组件为第三方开源/社区项目，版权归原作者所有，使用时请遵守各自许可证。

## 核心引擎

| 组件 | 用途 | 许可（请以仓库为准） | 链接 |
|------|------|----------------------|------|
| **ComfyUI** | 本地图像生成后端 | GPL-3.0 | https://github.com/comfyanonymous/ComfyUI |
| **Z-Image / Z-Image-Turbo** | 扩散模型（Tongyi-MAI） | 以 Hugging Face / 官方仓库声明为准 | https://huggingface.co/Tongyi-MAI/Z-Image-Turbo |
| **ComfyUI-GGUF** | GGUF UNet 加载 | 见节点仓库 | ComfyUI custom_nodes |
| **rgthree-comfy** | LoRA Stack 等节点 | 见节点仓库 | custom_nodes/rgthree-comfy |

## 运行时与其它依赖

- Python 及 PyTorch / CUDA 生态（见引擎内 `requirements` / 发行说明）
- Gradio：前端界面框架（Apache-2.0，以 PyPI 包为准）
- 其它 custom_nodes 以 `ComfyUI/custom_nodes/*/LICENSE` 或 README 为准

## 第三方 LoRA / 风格模型

- 风格文件来自 Civitai 等社区平台或本地整理。
- **版权与商用权限归各模型作者**。
- 界面「风格」页卡片中的链接与「是否可商用」为整理备注，**请以 Civitai / 作者页面最新许可为准**。
- 分发本一键出图包时，请勿声称拥有第三方模型的版权。

## 本仓库自有部分

- `davinci-zimage/app/` 一键出图 UI、配置与装配逻辑：达芬七整理
- 品牌文案、默认参数、图库体验：达芬七

若需完整合规再分发，建议：

1. 保留本文件与各上游 LICENSE  
2. 不移除 ComfyUI / 模型原作者署名要求  
3. 第三方权重单独标明来源或改为用户自行下载  

联系：https://x.com/davinci_seven
