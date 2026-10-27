"""Cover photos: rendered by the same engine as the video, so they always match its world."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from . import compose
from .common import fail, ffmpeg, load_profile, ok, read_json, say, warn
from .render import run_node

SIZES = {"9x16": (1080, 1920), "3x4": (1080, 1440), "4x5": (1080, 1350), "1x1": (1080, 1080)}


def make_covers(proj: Path, formats: list[str] | None = None, variants: list[str] | None = None) -> list[Path]:
    prof = load_profile()
    cfg = prof.get("covers", {})
    formats = formats or cfg.get("formats", ["9x16", "3x4", "4x5"])
    variants = variants or cfg.get("variants", ["hero", "type"])
    compose.build(proj, quiet=True)
    sb = read_json(proj / "storyboard.json", {})
    if not (sb.get("cover") or {}).get("headline"):
        warn("storyboard.cover.headline is empty: the cover will use the video title")
    out = proj / "out" / "covers"
    out.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    for v in variants:
        for f in formats:
            if f not in SIZES:
                warn(f"unknown cover format {f}")
                continue
            w, h = SIZES[f]
            dest = out / f"cover_{v}_{f}.png"
            run_node(["--project", str(proj), "--cover", str(dest), "--w", str(w), "--h", str(h), "--variant", v], capture=True)
            made.append(dest)
            ok(f"{dest.name}")
    main = out / f"cover_{variants[0]}_9x16.png"
    if not main.exists() and made:
        main = made[0]
    if main.exists():
        Image.open(main).convert("RGB").save(proj / "out" / "cover.jpg", quality=93)
    return made


def embed(video: Path, cover: Path) -> Path:
    """Attach the cover as the file's thumbnail so players and uploaders show it."""
    tmp = video.with_name(video.stem + "_c.mp4")
    ffmpeg("-i", str(video), "-i", str(cover), "-map", "0", "-map", "1", "-c", "copy", "-disposition:v:1", "attached_pic", "-movflags", "+faststart", str(tmp))
    tmp.replace(video)
    return video
