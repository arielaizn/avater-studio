"""Plates: the world's photographs. Gemini image models by default, procedural placeholders when there is no key.

Every prompt is wrapped with the concept's plate style so all scenes of a video live in the same world, and the first
accepted plate becomes the style reference for the rest.
"""
from __future__ import annotations

import base64
import concurrent.futures as cf
import io
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import concept as C
from .common import AvsError, fail, http, key, load_profile, ok, read_json, save_profile, say, warn

GEMINI = "https://generativelanguage.googleapis.com/v1beta"

GUARD = ("Photographic realism with real materials and physically plausible light. Never illustration, never cartoon, never anime, "
         "never 3D-cartoon, never flat vector. No text, letters, logos or watermarks in the image unless the prompt asks for a specific word.")


def pick_gemini_model(p: dict) -> str:
    m = (p.get("imagegen") or {}).get("gemini_model")
    if m:
        return m
    try:
        j = http("GET", f"{GEMINI}/models?pageSize=200", {"x-goog-api-key": key("GEMINI_API_KEY")})
        names = []
        for mod in j.get("models", []):
            n = mod.get("name", "").split("/")[-1]
            if "image" in n and "imagen" not in n and "generateContent" in (mod.get("supportedGenerationMethods") or []):
                names.append(n)

        def rank(n):
            v = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", n)[:1] or [0]]
            return (v[0], "pro" in n, "preview" not in n, n)
        if names:
            best = sorted(names, key=rank)[-1]
            p.setdefault("imagegen", {})["gemini_model"] = best
            save_profile(p)
            return best
    except AvsError:
        pass
    return "gemini-2.5-flash-image"


def _compose(prompt: str, concept: dict, avatar_below: bool, ref: bool) -> str:
    bad = C.lint_prompt(prompt)
    if bad:
        raise AvsError(f"prompt uses a forbidden style word: {', '.join(bad)}. The studio's spine is tactile photographic realism.")
    parts = [prompt.strip(), f"World: {concept.get('setting', '')}", f"Style: {concept.get('plate_style', '')}", GUARD,
             "Vertical 9:16 composition, shot as a single coherent photograph with shallow depth of field."]
    if avatar_below:
        parts.append("Composition: keep the lower 38% of the frame calm and simple (a surface or soft shadow), because a presenter will stand there.")
    if ref:
        parts.append("The attached image shows this video's world: keep the same materials, lighting, colour palette and level of detail, but make a NEW composition for this prompt.")
    return "\n".join(x for x in parts if x)


def gemini_image(prompt: str, p: dict, aspect: str = "9:16", ref_path: str | None = None) -> bytes:
    model = pick_gemini_model(p)
    parts = [{"text": prompt}]
    if ref_path and Path(ref_path).exists():
        parts.append({"inline_data": {"mime_type": "image/png" if str(ref_path).endswith("png") else "image/jpeg",
                                      "data": base64.b64encode(Path(ref_path).read_bytes()).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}
    j = http("POST", f"{GEMINI}/models/{model}:generateContent", {"x-goog-api-key": key("GEMINI_API_KEY")}, body, timeout=240)
    for c in j.get("candidates", []):
        for part in (c.get("content") or {}).get("parts", []):
            d = part.get("inlineData") or part.get("inline_data")
            if d and d.get("data"):
                return base64.b64decode(d["data"])
    reason = (j.get("promptFeedback") or {}).get("blockReason") or "no image in the response"
    raise AvsError(f"Gemini returned no image ({reason})", retryable=False)


def _to_png(data: bytes, path: Path, size=(1080, 1920)) -> None:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    # cover-fit to the canvas, keep the full resolution when it is already larger
    tw, th = size
    if im.width < tw or im.height < th:
        k = max(tw / im.width, th / im.height)
        im = im.resize((int(im.width * k) + 1, int(im.height * k) + 1), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG", optimize=False)


# --------------------------------------------------------- procedural plates
def _hex(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def procedural(path: Path, concept: dict, seed: int, size=(1080, 1920)) -> None:
    """A moody, lit backdrop in the world's palette. A stand-in for real plates (previews, tests, no-key use)."""
    w, h = size
    rng = np.random.default_rng(seed + 17)
    pal = concept["palette"]
    bg, acc, acc2, paper = (np.array(_hex(pal[k]), dtype=np.float32) for k in ("bg", "accent", "accent2", "paper"))
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top = bg * 0.55 + paper * 0.12
    bot = bg * 0.25
    base = top * (1 - yy) + bot * yy
    base = np.repeat(base, w, axis=1)
    im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    # soft light pools
    for k in range(3):
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        cx, cy, r = rng.uniform(0.1, 0.9) * w, rng.uniform(0.1, 0.6) * h, rng.uniform(0.25, 0.5) * w
        col = tuple(int(v) for v in (acc2 if k % 2 == 0 else acc)) + (110,)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        im = Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(120)))
    # bokeh
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(26):
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, 0.75 * h), rng.uniform(18, 90)
        c = tuple(int(v) for v in [acc, acc2, paper][int(rng.integers(0, 3))]) + (int(rng.integers(26, 70)),)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    im = Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(7)))
    # a light beam
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0 = rng.uniform(0.1, 0.8) * w
    d.polygon([(x0, 0), (x0 + 220, 0), (x0 + 220 + 520, h * 0.8), (x0 + 520, h * 0.8)], fill=tuple(int(v) for v in paper) + (34,))
    im = Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(40)))
    arr = np.array(im.convert("RGB"), dtype=np.float32)
    arr += rng.normal(0, 4.0, arr.shape[:2])[:, :, None]
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path, "PNG")


# ------------------------------------------------------- cut-outs (2.5D stage)
def _compose_cutout(prompt: str, concept: dict, ref: bool) -> str:
    bad = C.lint_prompt(prompt)
    if bad:
        raise AvsError(f"prompt uses a forbidden style word: {', '.join(bad)}. The studio's spine is tactile photographic realism.")
    parts = [prompt.strip(), "ONE isolated object or group, centered, fully inside the frame with a margin on every side, "
             "photographed on a perfectly flat, uniform, pure chroma-key green background (#00FF00). "
             "No shadow, reflection, floor or horizon on the green. No green anywhere on the subject. Even soft light with a clear light direction.",
             f"World it belongs to: {concept.get('setting', '')}", f"Style: {concept.get('plate_style', '')}", GUARD]
    if ref:
        parts.append("The attached image shows this video's world: match its materials, light and palette.")
    return "\n".join(parts)


def key_green(im: Image.Image, pad: int = 8) -> Image.Image:
    """Chroma-key a green backdrop to alpha (soft edge + despill) and crop to the subject."""
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dom = g - np.maximum(r, b)
    alpha = 1.0 - np.clip((dom - 28.0) / 52.0, 0.0, 1.0)
    # despill: keep green from exceeding the other channels on edge pixels
    g2 = np.minimum(g, np.maximum(r, b) + 6.0)
    out = np.dstack([r, g2, b, alpha * 255.0]).astype(np.uint8)
    res = Image.fromarray(out, "RGBA")
    ys, xs = np.where(alpha > 0.06)
    if len(xs) < 50:
        raise AvsError("the cut-out came back without a clear subject on green; regenerate it", retryable=True)
    box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad))
    return res.crop(box)


def procedural_cutout(path: Path, concept: dict, seed: int) -> None:
    """Placeholder cut-out: a soft-lit organic shape in the palette, with alpha."""
    rng = np.random.default_rng(seed + 5)
    w = h = 700
    pal = concept["palette"]
    col = np.array(_hex(pal[["accent", "accent2", "paper"][seed % 3]]), dtype=np.float32)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for _ in range(5):
        cx, cy, r = rng.uniform(0.3, 0.7) * w, rng.uniform(0.35, 0.7) * h, rng.uniform(0.14, 0.3) * w
        k = rng.uniform(0.55, 1.0)
        d.ellipse([cx - r, cy - r * 1.2, cx + r, cy + r * 1.2], fill=tuple(int(v * k) for v in col) + (255,))
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shade).ellipse([w * 0.28, h * 0.5, w * 0.72, h * 0.8], fill=(0, 0, 0, 70))
    im = Image.alpha_composite(im, shade.filter(ImageFilter.GaussianBlur(24)))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.filter(ImageFilter.GaussianBlur(1.2)).save(path, "PNG")


def fill_placeholders(proj: Path, scenes: list[dict], concept: dict) -> int:
    n = 0
    for i, S in enumerate(scenes):
        for li, Ly in enumerate(((S.get("plate") or {}).get("stage") or {}).get("layers", [])):
            sp = (Ly.get("src") or "").lstrip("/")
            if sp and not (proj / sp).exists() and not sp.startswith("http"):
                (procedural(proj / sp, concept, i * 101 + li * 7 + 3) if li == 0 and not Ly.get("cutout") else procedural_cutout(proj / sp, concept, i * 13 + li))
                n += 1
        src = (S.get("plate") or {}).get("src")
        if not src:
            dest = proj / "plates" / f"{S['id']}.png"
        elif (proj / src.lstrip("/")).exists() or src.startswith("http"):
            continue
        else:
            dest = proj / src.lstrip("/")
        procedural(dest, concept, i * 101 + 3)
        n += 1
    return n


# ------------------------------------------------------------------- batch
def jobs_from_storyboard(proj: Path, only: set[str] | None, force: bool) -> list[dict]:
    sb = read_json(proj / "storyboard.json") or fail("No storyboard.json", "write the storyboard first")
    jobs = []
    for i, sc in enumerate(sb.get("scenes", [])):
        sid = sc.get("id") or f"s{i + 1}"
        pl = sc.get("plate") or {}
        for li, Ly in enumerate((pl.get("stage") or {}).get("layers", [])):
            if not Ly.get("prompt"):
                continue
            dest = proj / (Ly.get("src") or f"plates/{sid}_L{li}.png")
            if (only and sid not in only and f"{sid}_L{li}" not in only) or (dest.exists() and not force):
                continue
            cut = Ly.get("cutout", li > 0)
            jobs.append({"id": f"{sid}_L{li}", "prompt": Ly["prompt"], "dest": dest, "aspect": Ly.get("aspect", "9:16" if not cut else "1:1"),
                         "avatar_below": bool(not cut and (sc.get("avatar", True) is not False)), "cutout": cut, "kind": Ly.get("kind", "")})
        if not pl.get("prompt"):
            continue
        dest = proj / (pl.get("src") or f"plates/{sid}.png")
        if only and sid not in only:
            continue
        if dest.exists() and not force:
            continue
        av = sc.get("avatar", True)
        show = bool(av) if not isinstance(av, dict) else av.get("show", True)
        jobs.append({"id": sid, "prompt": pl["prompt"], "dest": dest, "aspect": pl.get("aspect", "9:16"), "avatar_below": show})
    for a in sb.get("assets", []) or []:
        dest = proj / (a.get("file") or f"plates/{a['id']}.png")
        if only and a["id"] not in only:
            continue
        if dest.exists() and not force:
            continue
        jobs.append({"id": a["id"], "prompt": a["prompt"], "dest": dest, "aspect": a.get("aspect", "1:1"), "avatar_below": False, "asset": True})
    return jobs


def run(proj: Path, only: str | None = None, force: bool = False, parallel: int = 3, placeholders: bool = False, dry_run: bool = False) -> None:
    p = load_profile()
    concept = read_json(proj / "concept.json") or fail("No concept.json", "pick a world first (`avs concept pick`)")
    jobs = jobs_from_storyboard(proj, set(only.split(",")) if only else None, force)
    if not jobs:
        ok("every plate with a prompt already exists")
        return
    if dry_run:
        for j in jobs:
            say(f"[{j['id']}] {j['aspect']} -> {j['dest'].relative_to(proj)}\n{_compose(j['prompt'], concept, j['avatar_below'], False)}\n")
        return
    if not key("GEMINI_API_KEY"):
        if placeholders:
            for i, j in enumerate(jobs):
                (procedural_cutout(j["dest"], concept, i) if j.get("cutout") else procedural(j["dest"], concept, i * 101 + 3))
            warn("GEMINI_API_KEY is not set: wrote procedural placeholder plates (good for previews, not for publishing)")
            return
        fail("GEMINI_API_KEY is not set", "run `avs keys`, or generate the plates with any image tool the user has and save them to plates/<scene-id>.png; `--placeholders` makes stand-ins")
    ref = None
    scene_jobs = [j for j in jobs if not j.get("asset")]
    asset_jobs = [j for j in jobs if j.get("asset")]
    existing = sorted((proj / "plates").glob("*.png")) if (proj / "plates").exists() else []
    if existing:
        ref = str(existing[0])

    def one(j, ref_path):
        last = None
        for attempt in range(3):
            try:
                if j.get("cutout"):
                    data = gemini_image(_compose_cutout(j["prompt"], concept, bool(ref_path)), p, j["aspect"], ref_path)
                    j["dest"].parent.mkdir(parents=True, exist_ok=True)
                    key_green(Image.open(io.BytesIO(data))).save(j["dest"], "PNG")
                    return None
                data = gemini_image(_compose(j["prompt"], concept, j["avatar_below"], bool(ref_path)), p, j["aspect"], ref_path)
                _to_png(data, j["dest"], (1080, 1920) if j["aspect"] == "9:16" else (1080, 1080))
                return None
            except AvsError as e:
                last = e
                if not e.retryable and attempt:
                    break
        return last
    # first plate alone (it becomes the style anchor), the rest in parallel
    if scene_jobs and not ref:
        say(f"  [{scene_jobs[0]['id']}] style anchor ...")
        err = one(scene_jobs[0], None)
        if err:
            fail(f"Image generation failed: {err.msg}", "check GEMINI_API_KEY, billing for images, and the prompt")
        ref = str(scene_jobs[0]["dest"])
        scene_jobs = scene_jobs[1:]
    rest = scene_jobs + asset_jobs
    with cf.ThreadPoolExecutor(max_workers=parallel) as ex:
        futs = {ex.submit(one, j, ref): j for j in rest}
        for f in cf.as_completed(futs):
            j = futs[f]
            err = f.result()
            if err:
                warn(f"plate {j['id']} failed: {err.msg[:160]}", "re-run `avs imagegen --only " + j["id"] + "`")
            else:
                ok(f"plate {j['id']}")
