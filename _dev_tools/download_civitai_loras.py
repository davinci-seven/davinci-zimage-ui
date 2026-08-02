"""Download curated Z-Image Turbo LoRAs using CivitAI API token.

Token resolution (see app/core/civitai.py):
  1. env CIVITAI_API_TOKEN
  2. userdata/civitai_api_token.txt
  (token 不再从任何 md 文档里读)
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.civitai import auth_headers, ensure_token_file_from_md, get_civitai_token  # noqa: E402
from core.paths import LORAS_DIR  # noqa: E402

ZDIR = LORAS_DIR / "zimage"
ZDIR.mkdir(parents=True, exist_ok=True)

# modelVersionId → local filename
DOWNLOADS = [
    (2454927, "zy_CinematicShot_zit.safetensors"),
    (2500612, "CharacterDesign-IZT-V1.safetensors"),
    (2459399, "ck-NeurocoreShadowCircuit-ZIT_000003000.safetensors"),
    (3011352, "Romain_Bonnet_E10.safetensors"),
    (2921054, "Anime_art_v7_E10.safetensors"),
    (2796296, "Watercolor_V7_E10.safetensors"),
    (2794215, "midj-z-1.safetensors"),
    (2463751, "retro_scifi-90s_anime_style_Z_image_turbo.safetensors"),
    (2473980, "Nude_Art_6_E10.safetensors"),
    (2483194, "REDZ15_teenymooddy_lora_v1.1.safetensors"),
]


def download(version_id: int, filename: str) -> bool:
    dest = ZDIR / filename
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"SKIP {filename} ({dest.stat().st_size // 1024 // 1024}MB)")
        return True
    url = f"https://civitai.com/api/download/models/{version_id}"
    print(f"GET {filename} ...")
    try:
        with requests.get(
            url, headers=auth_headers(), stream=True, timeout=600, allow_redirects=True
        ) as r:
            ctype = (r.headers.get("content-type") or "").lower()
            if r.status_code != 200 or "text/html" in ctype:
                print(f"  FAIL status={r.status_code} ctype={ctype}")
                return False
            tmp = dest.with_suffix(dest.suffix + ".part")
            n = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(256 * 1024):
                    if chunk:
                        f.write(chunk)
                        n += len(chunk)
            if n < 100_000:
                tmp.unlink(missing_ok=True)
                print(f"  FAIL too small ({n} bytes)")
                return False
            tmp.replace(dest)
            print(f"  OK {n // 1024 // 1024}MB")
            return True
    except Exception as e:
        print(f"  FAIL {e}")
        return False


def main():
    ensure_token_file_from_md()
    tok = get_civitai_token()
    if not tok:
        print("ERROR: no CivitAI token. Put it in userdata/civitai_api_token.txt")
        print("  or set CIVITAI_API_TOKEN")
        sys.exit(1)
    print(f"token ok (...{tok[-6:]})")
    ok = fail = 0
    for vid, name in DOWNLOADS:
        if download(vid, name):
            ok += 1
        else:
            fail += 1
    print(f"done ok={ok} fail={fail}")
    sys.exit(0 if fail == 0 else 2)


if __name__ == "__main__":
    main()
