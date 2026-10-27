"""The presenter: render with HeyGen (transparent WebM), or bring any avatar clip, then prepare frames for the compositor.

Prepared frames are cropped to the figure, scaled and stored as WebP (with alpha) so the compositor can place the
presenter anywhere, in front of or behind graphics, and fade or slide it in and out.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from .common import (AvsError, duration, fail, ffmpeg, http, key, load_profile, multipart, ok, probe_stream, run, say,
                     warn, write_json, read_json)

API = "https://api.heygen.com"


def _h():
    return {"x-api-key": key("HEYGEN_API_KEY")}


def _items(j):
    d = j.get("data", j) if isinstance(j, dict) else j
    if isinstance(d, list):
        return d
    for k in ("looks", "avatars", "voices", "items", "list"):
        if isinstance(d, dict) and isinstance(d.get(k), list):
            return d[k]
    return []


def looks() -> list[dict]:
    if not key("HEYGEN_API_KEY"):
        fail("HEYGEN_API_KEY is not set", "run `avs keys`")
    j = http("GET", f"{API}/v3/avatars/looks?ownership=private&limit=50", _h())
    out = []
    for v in _items(j):
        out.append({"id": v.get("id") or v.get("look_id") or v.get("avatar_id"),
                    "name": v.get("name") or v.get("avatar_name") or "",
                    "type": v.get("avatar_type") or v.get("type") or "",
                    "preview": v.get("preview_image_url") or v.get("image_url") or ""})
    return out


def heygen_voices() -> list[dict]:
    j = http("GET", f"{API}/v3/voices?type=private&limit=50", _h())
    return [{"id": v.get("voice_id") or v.get("id"), "name": v.get("name"), "language": v.get("language")} for v in _items(j)]


def upload_audio(path: str) -> str:
    body, ctype = multipart({}, {"file": path})
    h = _h()
    h["Content-Type"] = ctype
    j = http("POST", f"{API}/v3/assets", h, raw=body, timeout=300)
    return j["data"]["asset_id"]


def render_twin(audio: str, out_dir: Path, name: str = "twin", aspect: str = "9:16", res: str = "1080p",
                engine: str | None = None, dry_run: bool = False, wait: bool = True) -> dict:
    p = load_profile()
    look = p["avatar"].get("look_id")
    if not look:
        fail("No avatar chosen", "run `avs looks`, then `avs profile set avatar.look_id=<id>`")
    body = {"type": "avatar", "avatar_id": look, "aspect_ratio": aspect, "resolution": res,
            "engine": {"type": engine or p["avatar"].get("engine") or "avatar_v"},
            "output_format": "webm",                       # alpha channel; do not send `background` with webm
            "title": f"Avatar Studio {datetime.now():%Y-%m-%d %H:%M}"}
    if audio.startswith("http"):
        body["audio_url"] = audio
    else:
        body["audio_asset_id"] = f"<upload of {audio}>" if dry_run else None
    secs = duration(audio) if not audio.startswith("http") else 0
    est = round(secs * 0.12, 2)
    if dry_run:
        print(json.dumps({"request": body, "audio_seconds": round(secs, 1), "estimated_cost_usd": est,
                          "note": "HeyGen API credits, about $0.12 per second at the time of writing"}, indent=2, ensure_ascii=False))
        return {"dry_run": True, "estimated_cost_usd": est}
    if not key("HEYGEN_API_KEY"):
        fail("HEYGEN_API_KEY is not set", "run `avs keys`")
    if body.get("audio_asset_id") is None:
        say("  uploading narration to HeyGen ...")
        body["audio_asset_id"] = upload_audio(audio)
    j = http("POST", f"{API}/v3/videos", _h(), body)
    vid = j["data"]["video_id"]
    say(f"  submitted video_id={vid} (estimated ${est})")
    state = {"video_id": vid, "submitted": datetime.now().isoformat(timespec="seconds"), "estimated_cost_usd": est}
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "twin_job.json", state)
    if not wait:
        return state
    return wait_twin(vid, out_dir, name)


def wait_twin(vid: str, out_dir: Path, name: str = "twin") -> dict:
    t0 = time.time()
    while True:
        d = http("GET", f"{API}/v3/videos/{vid}", _h())["data"]
        st = d.get("status")
        if st == "completed":
            break
        if st == "failed":
            fail(f"HeyGen could not render the video: {d.get('failure_code')} {d.get('failure_message')}",
                 "if it says the avatar is not ready or lacks matting, fix it in HeyGen and retry. Failed renders are usually not charged.")
        if time.time() - t0 > 45 * 60:
            fail(f"Still rendering after 45 minutes (video_id={vid})", f"it may still finish: `avs twin --resume {vid}`. Never resubmit, you would pay twice.")
        say(f"  {st} ({int(time.time() - t0)}s)")
        time.sleep(15)
    fmt = (d.get("output_format") or "webm").lower()
    if fmt != "webm":
        warn("HeyGen returned an MP4 (no transparency). The avatar probably lacks matting.",
             "use a newer avatar trained with matting, or bring a clip on a plain background and use `avs avatar --file`")
    out = out_dir / f"{name}.{'webm' if fmt == 'webm' else 'mp4'}"
    urllib.request.urlretrieve(d["video_url"], out)
    ok(f"{out} ({d.get('duration')}s)")
    return {"video_id": vid, "file": str(out), "duration": d.get("duration")}


# ------------------------------------------------------------- preparation
def has_alpha(path: str) -> bool:
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=pix_fmt:stream_tags=alpha_mode", "-of", "json", str(path)], check=False)
    try:
        st = json.loads(r.stdout)["streams"][0]
    except (ValueError, KeyError, IndexError):
        return False
    pf = st.get("pix_fmt") or ""
    return "yuva" in pf or "rgba" in pf or "bgra" in pf or "argb" in pf or (st.get("tags") or {}).get("alpha_mode") == "1"


def detect_bbox(path: str, secs: float = 12.0) -> dict | None:
    """Union bounding box of the figure over the first seconds, using the alpha channel."""
    r = run(["ffmpeg", "-hide_banner", "-c:v", "libvpx-vp9", "-i", path, "-t", str(secs),
             "-vf", "alphaextract,cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"], check=False)
    m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr or "")
    if not m:
        return None
    w, h, x, y = map(int, m[-1])
    return {"w": w, "h": h, "x": x, "y": y}


def prepare(src: str, proj: Path, fps: int = 30, target_w: int = 1000, force: bool = False) -> dict:
    """Crop to the figure, scale, and write twin/frames/a_00001.webp ... plus twin/fit.json."""
    tw = proj / "twin"
    frames = tw / "frames"
    fit_path = tw / "fit.json"
    if fit_path.exists() and not force and any(frames.glob("a_*.webp")):
        return read_json(fit_path)
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True, exist_ok=True)
    st = probe_stream(src)
    sw, sh = int(st.get("width") or 0), int(st.get("height") or 0)
    if not sw:
        fail(f"Cannot read the video {src}", "check the file plays")
    alpha = has_alpha(src)
    dec = ["-c:v", "libvpx-vp9"] if str(src).lower().endswith(".webm") and alpha else []
    if alpha:
        bb = detect_bbox(src) or {"w": sw, "h": sh, "x": 0, "y": 0}
        pad = 6
        x0, y0 = max(0, bb["x"] - pad), max(0, bb["y"] - pad)
        cw, ch = min(sw - x0, bb["w"] + 2 * pad), min(sh - y0, bb["h"] + 2 * pad)
        cw -= cw % 2
        ch -= ch % 2
        vf = f"fps={fps},crop={cw}:{ch}:{x0}:{y0},scale={target_w}:-2:flags=lanczos,format=yuva420p"
        ffmpeg(*dec, "-i", src, "-vf", vf, "-c:v", "libwebp", "-quality", "86", "-compression_level", "2", "-an",
               str(frames / "a_%05d.webp"))
        crop = {"w": cw, "h": ch, "x": x0, "y": y0}
    else:
        vf = f"fps={fps},scale={target_w}:-2:flags=lanczos"
        ffmpeg("-i", src, "-vf", vf, "-c:v", "libwebp", "-quality", "86", "-compression_level", "2", "-an",
               str(frames / "a_%05d.webp"))
        crop = {"w": sw, "h": sh, "x": 0, "y": 0}
    n = len(list(frames.glob("a_*.webp")))
    if not n:
        fail("No avatar frames were produced", "check that ffmpeg has libwebp and libvpx-vp9 (`avs doctor`)")
    out_w = target_w
    out_h = int(round(crop["h"] * target_w / crop["w"] / 2) * 2)
    fit = {"source": str(src), "alpha": alpha, "fps": fps, "frames": n, "seconds": round(n / fps, 3),
           "crop": crop, "width": out_w, "height": out_h,
           # face box inside the prepared frame, as fractions (top 38% of a waist-up figure)
           "face": [0.22, 0.02, 0.78, 0.40]}
    write_json(fit_path, fit)
    ok(f"avatar prepared: {n} frames, {out_w}x{out_h}, alpha={alpha}")
    return fit


def cmd_looks(args) -> None:
    rows = looks()
    for r in rows:
        say(f"{r['id']} | {r['name']} | {r['type']}")
    if not rows:
        say("No avatars found. Create your digital twin in HeyGen first (Avatars -> Create avatar).")
    else:
        say("\nSave one with: avs profile set avatar.look_id=<id>")


def cmd_twin(args) -> None:
    out = Path(args.out)
    if args.resume:
        res = wait_twin(args.resume, out, args.name)
        return
    if not args.audio:
        fail("Give --audio narration.wav", "make it first with `avs tts`")
    render_twin(args.audio, out, args.name, args.aspect, args.res, args.engine, args.dry_run, not args.no_wait)
