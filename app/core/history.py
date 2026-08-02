"""Generation history: save images + sidecar metadata for re-apply."""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .paths import GALLERY_DIR, ensure_runtime_dirs

INDEX_FILE = GALLERY_DIR / "index.json"


def resolve_image(stored: str) -> Path:
    """Records store a bare filename so the pack stays movable across disks.

    Older records kept an absolute path; honour those if they still resolve.
    """
    if not stored:
        return GALLERY_DIR / ""
    p = Path(stored)
    if p.is_absolute():
        return p if p.exists() else GALLERY_DIR / p.name
    return GALLERY_DIR / p


@dataclass
class GenRecord:
    id: str
    created_at: str
    image_path: str  # 相对 userdata/gallery 的文件名
    prompt: str
    mode: str = "txt2img"  # txt2img | img2img
    model_mode: str = "标准 FP8（推荐）"
    quality: str = "均衡"
    aspect: str = "正方形 1:1"
    style1: str = "（无风格）"
    weight1: str = "中"
    style2: str = "（无风格）"
    weight2: str = "轻"
    strength: str = "中改"
    seed: int = -1
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GenRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        data = {k: v for k, v in d.items() if k in known}
        if "extra" not in data:
            data["extra"] = {}
        return cls(**data)


def _load_index() -> list[dict]:
    ensure_runtime_dirs()
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        return []
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_index(items: list[dict]) -> None:
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def save_generation(src_image: Path | str, record: GenRecord) -> GenRecord:
    """Copy image into gallery and append metadata."""
    ensure_runtime_dirs()
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(src_image)
    if not src.exists():
        raise FileNotFoundError(str(src))

    rid = record.id or uuid.uuid4().hex[:12]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = src.suffix.lower() or ".png"
    dest_name = f"{ts}_{rid}{ext}"
    dest = GALLERY_DIR / dest_name
    shutil.copy2(src, dest)

    # also write sidecar next to image
    record.id = rid
    record.image_path = dest_name
    if not record.created_at:
        record.created_at = datetime.now().isoformat(timespec="seconds")
    sidecar = dest.with_suffix(".json")
    sidecar.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    items = _load_index()
    items.insert(0, record.to_dict())
    # cap index size
    items = items[:500]
    _save_index(items)
    return record


def list_records(limit: int = 80) -> list[GenRecord]:
    items = _load_index()[:limit]
    out: list[GenRecord] = []
    for d in items:
        rec = GenRecord.from_dict(d)
        if resolve_image(rec.image_path).exists():
            out.append(rec)
    return out


def get_record(record_id: str) -> Optional[GenRecord]:
    for r in list_records(500):
        if r.id == record_id:
            return r
    return None


def record_choice_label(r: GenRecord) -> str:
    """Stable dropdown label — always truncate the same way."""
    prompt_short = (r.prompt or "").replace("\n", " ").replace("\r", " ").strip()
    if len(prompt_short) > 36:
        prompt_short = prompt_short[:36]
    return f"{r.created_at} · {prompt_short} · [{r.id}]"


def gallery_choices(limit: int = 80) -> list[str]:
    """Human labels for dropdown."""
    return [record_choice_label(r) for r in list_records(limit)]


def choice_for_id(record_id: str, limit: int = 80) -> tuple[list[str], Optional[str]]:
    """Return (choices, matching_label). Always pair value with current choices."""
    recs = list_records(limit)
    choices = [record_choice_label(r) for r in recs]
    label = None
    rid = (record_id or "").strip()
    if rid:
        for r, c in zip(recs, choices):
            if r.id == rid:
                label = c
                break
        if label is None:
            # fallback: id substring in label
            for c in choices:
                if f"[{rid}]" in c:
                    label = c
                    break
    if label is None and choices:
        label = choices[0]
    return choices, label


def parse_choice_id(label: str) -> Optional[str]:
    if not label or "[" not in label:
        return None
    try:
        return label.rsplit("[", 1)[-1].rstrip("]").strip()
    except Exception:
        return None


def gallery_image_paths(limit: int = 48) -> list[str]:
    paths = [resolve_image(r.image_path) for r in list_records(limit)]
    return [str(p) for p in paths if p.exists()]


def format_record_md(r: Optional[GenRecord]) -> str:
    """HTML for 图库详情（gr.HTML）。提示词块强制换行，不用 markdown 代码块。"""
    import html as html_lib

    if not r:
        return '<div class="dv-hist-meta">从上方选择一条记录，查看提示词与参数。</div>'
    prompt_esc = html_lib.escape(r.prompt or "").replace("\n", "<br/>")
    style_line = html_lib.escape(
        f"{r.style1}（{r.weight1}）"
        + (
            f" + {r.style2}（{r.weight2}）"
            if r.style2 and not str(r.style2).startswith("（无")
            else ""
        )
    )
    extra = ""
    if r.mode == "img2img":
        extra = f"<li><b>变化强度</b>：{html_lib.escape(str(r.strength))}</li>"
    size_line = ""
    ex = r.extra or {}
    if ex.get("width") and ex.get("height"):
        custom_tag = " · 自定义" if ex.get("custom_size") else ""
        size_line = (
            f"<li><b>尺寸</b>：{int(ex['width'])} × {int(ex['height'])} px"
            f"{custom_tag}</li>"
        )
    return f"""
<div class="dv-hist-meta">
  <h3>出图参数</h3>
  <ul>
    <li><b>时间</b>：{html_lib.escape(str(r.created_at))}</li>
    <li><b>提示词</b>：</li>
  </ul>
  <div class="dv-prompt-block">{prompt_esc}</div>
  <ul>
    <li><b>模型</b>：{html_lib.escape(str(r.model_mode))}</li>
    <li><b>画质 / 比例</b>：{html_lib.escape(str(r.quality))} · {html_lib.escape(str(r.aspect or '—'))}</li>
    {size_line}
    <li><b>风格</b>：{style_line}</li>
    <li><b>种子</b>：{html_lib.escape(str(r.seed))}</li>
    {extra}
  </ul>
</div>
"""
