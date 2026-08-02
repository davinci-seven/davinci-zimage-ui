# 从 CivitAI 补风格（需 API Key）

本机无 Key 时，直接下载会跳登录页或 401。

## Token 放哪里（程序会自动找）

按优先级（token 只放这两处，**不要写进任何会打包的文档**）：

1. 环境变量 `CIVITAI_API_TOKEN`
2. **`userdata/civitai_api_token.txt`**（推荐，一行纯 token）

临时用一次可以：

```powershell
$env:CIVITAI_API_TOKEN = "<你的 token>"
```

## 一键下载

```powershell
cd e:\z-image\davinci-zimage
$env:PYTHONPATH = "e:\z-image\ComfyUI-zimage\python\Lib\site-packages"
e:\z-image\ComfyUI-zimage\python\python.exe _dev_tools\download_civitai_loras.py
```

下载完后登记 `assets/styles/styles.json`，再：

```powershell
e:\z-image\ComfyUI-zimage\python\python.exe app\tools\gen_style_covers.py --force --only id1,id2
```

推荐检索：  
https://civitai.com/models?baseModel=ZImageTurbo&types=LORA&sort=Highest+Rated
