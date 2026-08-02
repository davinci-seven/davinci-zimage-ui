"""CivitAI API helpers — token discovery for downloads."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .paths import PACK_ROOT, USERDATA

# 查找顺序：环境变量 → userdata 私密文件（token 只放这两处，绝不写进会打包的文档）
_TOKEN_FILES = [
    USERDATA / "civitai_api_token.txt",
    PACK_ROOT / "_dev_tools" / "civitai_api_token.txt",
]


def get_civitai_token() -> str:
    for key in ("CIVITAI_API_TOKEN", "CIVITAI_TOKEN", "CIVITAI_API_KEY"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v
    for path in _TOKEN_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # bare token file
        text = text.lstrip("\ufeff")
        if path.suffix.lower() == ".txt":
            for line in text.splitlines():
                line = line.strip().lstrip("\ufeff")
                if line and not line.startswith("#"):
                    return line
            continue
    return ""


def auth_headers() -> dict[str, str]:
    tok = get_civitai_token()
    h = {"User-Agent": "DavinciZ-ZImage/1.0"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def ensure_token_file_from_md() -> Path | None:
    """Kept for compatibility: make sure the token lives in userdata only."""
    tok = get_civitai_token()
    if not tok:
        return None
    dest = USERDATA / "civitai_api_token.txt"
    USERDATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_text(tok + "\n", encoding="utf-8")
    return dest
