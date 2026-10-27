"""End-to-end smoke test with stand-ins: mock narration, a drawn presenter with alpha, procedural plates. No keys, no spend."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from . import avatar as AV, compose, concept as CO, cover, mix, qa, render as R, voice as V
from .common import PLUGIN_ROOT, fail, load_profile, ok, read_json, run, say, write_json, ffmpeg


def stand_in_presenter(dest: Path, seconds: float, fps: int = 30) -> None:
    """A simple drawn half-figure with a moving mouth, on a transparent background (VP9 with alpha)."""
    d = dest.parent / "_frames"
    d.mkdir(parents=True, exist_ok=True)
    W, H = 640, 960
    n = int(seconds * fps) + 2
    for i in range(n):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g = ImageDraw.Draw(im)
        bob = int(6 * __import__("math").sin(i / 9))
        g.rounded_rectangle([60, 520 + bob, 580, 960], 120, fill=(38, 52, 74, 255))
        g.rectangle([270, 440 + bob, 370, 540 + bob], fill=(224, 176, 142, 255))
        g.ellipse([190, 130 + bob, 450, 470 + bob], fill=(232, 186, 152, 255))
        g.ellipse([190, 110 + bob, 450, 260 + bob], fill=(52, 34, 26, 255))
        for ex in (265, 375):
            g.ellipse([ex - 14, 290 + bob, ex + 14, 318 + bob], fill=(30, 24, 22, 255))
        m = 6 + int(14 * abs(__import__("math").sin(i / 2.6)))
        g.ellipse([290, 380 + bob, 350, 380 + m + bob], fill=(120, 40, 44, 255))
        im.save(d / f"p_{i:05d}.png")
    ffmpeg("-framerate", str(fps), "-i", str(d / "p_%05d.png"), "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "1M", str(dest))
    shutil.rmtree(d, ignore_errors=True)


def run(keep: bool = False, seconds: float = 0.0) -> None:  # noqa: A001
    base = Path(tempfile.mkdtemp(prefix="avs-selftest-"))
    pr = base / "selftest"
    for sub in ("audio", "twin", "plates", "assets", "comp", "out"):
        (pr / sub).mkdir(parents=True)
    write_json(pr / "project.json", {"name": "selftest", "width": 1080, "height": 1920, "fps": 30})
    ex = PLUGIN_ROOT / "examples"
    script = (ex / "script.example.txt").read_text(encoding="utf-8")
    say("1/7 narration (mock voice)")
    V.make_narration(script, pr / "audio", load_profile(), "mock")
    total = read_json(pr / "audio" / "timing.json")["total"]
    say("2/7 world")
    cands = CO.propose("why most AI avatars look fake", 3, 7)
    if not cands:
        fail("no world available")
    write_json(pr / "concept_candidates.json", cands)
    con = CO.finalize(cands[0], "למה אווטאר נראה מזויף", "avatars", "a workshop where a head sculpture comes alive", "a head sculpture")
    write_json(pr / "concept.json", con)
    say("3/7 stand-in presenter")
    stand_in_presenter(pr / "twin" / "twin.webm", total)
    AV.prepare(str(pr / "twin" / "twin.webm"), pr, 30, force=True)
    shutil.copy(ex / "storyboard.example.json", pr / "storyboard.json")
    say("4/7 build + placeholder plates")
    res = compose.build(pr, placeholders=True)
    say("5/7 render")
    R.render_video(pr, False, None, False, None, seconds or None, False)
    say("6/7 mix + covers")
    if seconds:
        write_json(pr / "out" / "note.json", {"partial": seconds})
    mix.run_mix(pr)
    cover.make_covers(pr, ["9x16", "4x5"], ["hero", "type"])
    cover.embed(pr / "out" / "final.mp4", pr / "out" / "cover.jpg")
    say("7/7 qa")
    passed = qa.run_qa(pr)
    ok(f"self-test finished: {pr / 'out'}")
    say(f"project: {pr}")
    if not keep and passed and False:
        shutil.rmtree(base, ignore_errors=True)
