"""Render: comp/index.html -> frames (headless Chromium) -> silent MP4."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .common import PLUGIN_ROOT, AvsError, duration, fail, ffmpeg, ok, read_json, say, warn
from . import compose

RENDER = PLUGIN_ROOT / "render"


def node_cmd() -> list[str]:
    exe = shutil.which("node")
    if not exe:
        fail("Node.js is not installed", "install Node 18+ (https://nodejs.org) or run `avs setup`")
    return [exe, str(RENDER / "render.mjs")]


def run_node(args: list[str], capture: bool = False):
    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(filter(None, [str(RENDER / "node_modules"), env.get("NODE_PATH", "")]))
    if capture:
        r = subprocess.run(node_cmd() + args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if r.returncode != 0:
            raise AvsError(f"renderer failed:\n{(r.stderr or r.stdout)[-1500:]}")
        return r.stdout
    p = subprocess.Popen(node_cmd() + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
    last = ""
    for line in p.stdout:
        line = line.rstrip()
        if line.startswith("frames "):
            last = line
            if line.split()[1].split("/")[0].isdigit() and int(line.split()[1].split("/")[0]) % 120 == 0:
                say("  " + line)
        elif line:
            say("  " + line)
    p.wait()
    if p.returncode != 0:
        raise AvsError("renderer failed (see output above)")
    return last


def render_video(proj: Path, draft: bool = False, workers: int | None = None, keep_frames: bool = False,
                 t_from: float | None = None, t_to: float | None = None, placeholders: bool = False) -> Path:
    res = compose.build(proj, placeholders=placeholders, quiet=True)
    bad = [p for p in res["problems"] if "does not exist" in p or "no plate" in p]
    if bad:
        for b in bad:
            warn(b)
        fail("Some plates are missing", "run `avs imagegen`, add the images to plates/, or pass --placeholders for stand-ins")
    meta = res["resolved"]["meta"]
    out = proj / "out"
    frames = out / ("frames_draft" if draft else "frames")
    if frames.exists():
        shutil.rmtree(frames)
    fps = 15 if draft else meta["fps"]
    scale = 0.5 if draft else 1
    args = ["--project", str(proj), "--frames", str(frames), "--fps", str(fps), "--scale", str(scale)]
    if workers:
        args += ["--workers", str(workers)]
    if t_from is not None:
        args += ["--from", str(t_from)]
    if t_to is not None:
        args += ["--to", str(t_to)]
    say(f"Rendering {meta['duration']:.1f}s at {meta['width']}x{meta['height']}{' (draft, half size, 15fps)' if draft else ''} ...")
    run_node(args)
    dest = out / ("video_draft.mp4" if draft else "video_silent.mp4")
    crf = "24" if draft else "20"
    ffmpeg("-framerate", str(fps), "-i", str(frames / "f_%06d.jpg"), "-c:v", "libx264", "-preset", "veryfast" if draft else "medium",
           "-crf", crf, "-maxrate", "6M" if draft else "10M", "-bufsize", "12M" if draft else "20M", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest))
    if not keep_frames:
        shutil.rmtree(frames, ignore_errors=True)
    ok(f"{dest} ({duration(dest):.1f}s)")
    return dest


def stills(proj: Path, times: list[float], full: bool = False) -> list[Path]:
    compose.build(proj, quiet=True)
    d = proj / "out" / "stills"
    d.mkdir(parents=True, exist_ok=True)
    out = run_node(["--project", str(proj), "--frames", str(d), "--still", ",".join(str(t) for t in times), "--scale", "1" if full else "0.5"], capture=True)
    return [Path(x.strip()) for x in out.splitlines() if x.strip().endswith(".png")]
