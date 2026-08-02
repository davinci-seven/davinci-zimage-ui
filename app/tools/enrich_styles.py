import json
from collections import Counter
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "assets" / "styles" / "styles.json"
data = json.loads(p.read_text(encoding="utf-8"))

extra = {
    "snap": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2268008",
        "commercial": "允许出图商用（以页面许可为准）",
        "trigger": "amateur digital snapshot, candid, smartphone capture",
    },
    "skin": {
        "category": "质感增强",
        "civitai_url": "https://civitai.com/models/580857",
        "commercial": "限制较多，建议仅个人/非商用",
        "trigger": "detailed skin texture, photorealistic, incredibly lifelike",
    },
    "aesthetic": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2214707",
        "commercial": "以 Civitai 页面为准",
    },
    "luneva": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2185167",
        "commercial": "以 Civitai 页面为准",
        "trigger": "cinematic lighting, film still",
    },
    "cyberhd": {
        "category": "质感增强",
        "civitai_url": "https://civitai.com/models/2215818",
        "commercial": "以 Civitai 页面为准",
        "trigger": "ultra detailed, sharp focus",
    },
    "detail_slider": {
        "category": "质感增强",
        "civitai_url": "https://civitai.com/models/2234266",
        "commercial": "以 Civitai 页面为准",
    },
    "detail_daemon": {
        "category": "质感增强",
        "civitai_url": "https://civitai.com/models/2209262",
        "commercial": "以 Civitai 页面为准",
    },
    "melancholy": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2334593",
        "commercial": "以 Civitai 页面为准",
        "trigger": "melancholy mood, muted colors",
    },
    "realistic": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2194714",
        "commercial": "以 Civitai 页面为准（近似写实类）",
    },
    "detail": {
        "category": "质感增强",
        "civitai_url": "https://civitai.com/models/2234266",
        "commercial": "以 Civitai 页面为准",
    },
    "atmosphere": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/432586",
        "commercial": "以 Civitai 页面为准",
        "trigger": "cinematic lighting, volumetric light",
    },
    "nvdi": {
        "category": "角色/题材",
        "civitai_url": "https://civitai.com/models/2175220",
        "commercial": "以 Civitai 页面为准",
    },
    "cartoon3d": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/404277",
        "commercial": "以 Civitai 页面为准",
        "trigger": "3d render, pixar style",
    },
    "disney": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/404277",
        "commercial": "允许 Image/Rent/Sell（作者页，请再确认）",
        "trigger": "DisneyIZT, This image is a Disney-Pixar 3D animation style, featuring a stylized cartoon character, high detailed, ultra 4k, masterpiece",
        "default_weight": 0.95,
    },
    "instant": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/689192",
        "commercial": "以 Civitai 页面为准",
        "trigger": "polaroid photo, instant camera",
    },
    "nice": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/1862761",
        "commercial": "以 Civitai 页面为准",
    },
    "toloveru": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/832858",
        "commercial": "以 Civitai 页面为准",
    },
    "anime": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/832858",
        "commercial": "以 Civitai 页面为准",
        "trigger": "anime style, detailed illustration",
    },
    "ink": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/830230",
        "commercial": "以 Civitai 页面为准",
        "trigger": "chinese ink painting, sumi-e",
    },
    "linework": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/830230",
        "commercial": "以 Civitai 页面为准",
        "trigger": "clean lineart, black and white",
    },
    "couture": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2088956",
        "commercial": "以 Civitai 页面为准",
        "trigger": "haute couture fashion, runway",
    },
    "oot": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2088956",
        "commercial": "以 Civitai 页面为准",
        "trigger": "street style outfit, fashion lookbook",
    },
    "fantasy80": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/599757",
        "commercial": "以 Civitai 页面为准",
        "trigger": "1980s fantasy illustration, retro poster",
    },
    "moonlight": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2205459",
        "commercial": "以 Civitai 页面为准",
        "trigger": "moonlight, cool blue lighting",
    },
    "glowing": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/938811",
        "commercial": "以 Civitai 页面为准",
        "trigger": "glowing neon, dark fantasy",
    },
    "granblue": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/832858",
        "commercial": "以 Civitai 页面为准",
        "trigger": "anime game art style",
    },
    "moriime": {
        "category": "整体风格",
        "civitai_url": "https://civitai.com/models/2256350",
        "commercial": "以 Civitai 页面为准",
    },
    "lenovo": {
        "category": "质感增强",
        "civitai_url": "https://civitai.com/models/1662740",
        "commercial": "以 Civitai 页面为准",
    },
    "nsfw_core": {
        "category": "成人向",
        "civitai_url": "https://civitai.com/models/1344651",
        "commercial": "成人内容，仅本地合法使用",
    },
    "nsfwmaster": {
        "category": "成人向",
        "civitai_url": "https://civitai.com/models/667086",
        "commercial": "以 Civitai 页面为准；成人向",
    },
    "oiled": {
        "category": "成人向",
        "civitai_url": "https://civitai.com/models/1344651",
        "commercial": "成人向，仅本地合法使用",
        "trigger": "oiled skin",
    },
    "b3tter": {
        "category": "成人向",
        "civitai_url": "https://civitai.com/models/667086",
        "commercial": "成人向，仅本地合法使用",
    },
    "steep": {
        "category": "成人向",
        "civitai_url": "https://civitai.com/models/2230417",
        "commercial": "成人向，仅本地合法使用",
    },
}

for s in data["styles"]:
    e = extra.get(s["id"], {})
    s["category"] = e.get("category", s.get("category", "其他"))
    s["civitai_url"] = e.get("civitai_url", s.get("civitai_url", ""))
    s["commercial"] = e.get(
        "commercial", s.get("commercial", "许可未标注，使用前请自行确认")
    )
    if "trigger" in e:
        s["trigger"] = e["trigger"]
    if "default_weight" in e:
        s["default_weight"] = e["default_weight"]

p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok", len(data["styles"]))
print(Counter(s.get("category") for s in data["styles"]))
print("with links", sum(1 for s in data["styles"] if s.get("civitai_url")))
