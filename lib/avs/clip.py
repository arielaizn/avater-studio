"""avs clip: a quick designed clip from a short text (10 to 30 seconds), no storyboard writing needed.

Frames: studio (presenter in the bottom third over a photographed world), spotlight (bigger, centered),
side (presenter off to one side with big type opposite), image (no presenter), plain (solid brand color)."""
from __future__ import annotations

import re
from pathlib import Path

from . import align as A, concept as CO, voice as V
from .common import fail, load_profile, ok, read_json, say, warn, write_json

FRAMES = {
    "studio": {"avatar": {"show": True}, "hl_pos": [0.5, 0.2]},
    "spotlight": {"avatar": {"show": True, "x": 0.0}, "hl_pos": [0.5, 0.17], "height": 0.5},
    "side": {"avatar": {"show": True, "x": -0.2}, "hl_pos": [0.5, 0.2]},
    "image": {"avatar": {"show": False}, "hl_pos": [0.5, 0.42]},
    "plain": {"avatar": {"show": False}, "hl_pos": [0.5, 0.42], "plain": True},
}
STYLES = ["slab", "plain", "highlight", "outline", "sign"]


def add_args(s) -> None:
    s.add_argument("--text", help="the spoken text")
    s.add_argument("--text-file")
    s.add_argument("--headlines", help="headline per scene, separated by |  (max 4 words each)")
    s.add_argument("--frame", default="studio", choices=list(FRAMES))
    s.add_argument("--name", default="")
    s.add_argument("--topic", default="")
    s.add_argument("--prompt", help="what the world looks like (English, photographic)")
    s.add_argument("--presenter-file", help="presenter clip to use (transparent webm is best)")
    s.add_argument("--provider", choices=["auto", "cartesia", "elevenlabs", "mock"])
    s.add_argument("--placeholders", action="store_true")
    s.add_argument("--no-render", action="store_true")


def _groups(words: list[dict], target: float = 3.0) -> list[tuple[int, int]]:
    out, i = [], 0
    while i < len(words):
        j = i
        while j + 1 < len(words) and (words[j + 1]["end"] - words[i]["start"] < target or not re.search(r"[.!?,،]$", words[j]["w"])) and words[j + 1]["end"] - words[i]["start"] < 4.4:
            j += 1
        out.append((i, j))
        i = j + 1
    return out


def cmd_clip(a) -> None:
    from . import avatar as AV, compose, mix, render as R, cover, qa, imagegen
    text = a.text or (Path(a.text_file).read_text(encoding="utf-8") if a.text_file else "")
    if not text.strip():
        fail("Give --text or --text-file")
    prof = load_profile()
    root = Path(prof["projects_root"]).expanduser()
    slug = re.sub(r"[^a-z0-9-]+", "-", (a.name or "clip").lower()).strip("-") or "clip"
    pr = root / slug
    n = 2
    while pr.exists():
        pr = root / f"{slug}-{n}"
        n += 1
    for sub in ("audio", "twin", "plates", "assets", "comp", "out"):
        (pr / sub).mkdir(parents=True)
    v = prof["video"]
    write_json(pr / "project.json", {"name": pr.name, "width": v["width"], "height": v["height"], "fps": v["fps"]})
    (pr / "script.txt").write_text(text, encoding="utf-8")
    V.make_narration(text, pr / "audio", prof, a.provider)
    words = read_json(pr / "audio" / "words.json")
    cands = CO.propose(a.topic or text[:80], 1)
    if not cands:
        fail("No world available right now")
    con = CO.finalize(cands[0], a.name or pr.name, a.topic or "", "", a.prompt or "")
    write_json(pr / "concept.json", con)
    fr = FRAMES[a.frame]
    pf = a.presenter_file or prof["avatar"].get("file")
    if fr["avatar"].get("show") and pf and Path(pf).exists():
        AV.prepare(pf, pr, v["fps"])
    elif fr["avatar"].get("show"):
        warn("No presenter clip: the clip will be made without one (pass --presenter-file, or use `avs twin`)")
    heads = [h.strip() for h in (a.headlines or "").split("|") if h.strip()]
    groups = _groups(words)
    scenes = []
    for k, (i, j) in enumerate(groups):
        chunk = words[i:j + 1]
        if k < len(heads):
            head = heads[k]
        else:
            top = sorted(range(len(chunk)), key=lambda q: -len(chunk[q]["w"]))[:2]
            head = " ".join(chunk[q]["w"].strip(".,!?،") for q in sorted(top))
        plate = {"prompt": f"{a.prompt or con.get('hero') or 'a quiet detail of the scene'}, scene {k + 1}, {con['setting']}", "move": ["push-in", "pan-left", "drift", "pull-out", "pan-right"][k % 5]}
        if fr.get("plain"):
            plate = {"bg": con["palette"]["bg"]}
        layer = {"type": "headline", "text": head, "style": STYLES[k % len(STYLES)], "pos": fr["hl_pos"], "size": 150 if len(head) < 18 else 120, "at": (0 if k == 0 else f"w:{i}.start"), "anim": ["pop-words", "slam", "rise"][k % 3]}
        sc = {"id": f"s{k + 1}", "start": f"w:{i}.start" if k else 0, "end": f"w:{groups[k + 1][0]}.start" if k + 1 < len(groups) else "end",
              "plate": plate, "avatar": dict(fr["avatar"]), "layers": [layer]}
        if k and not fr.get("plain"):
            sc["transition"] = con.get("transition", "soft-push")
        scenes.append(sc)
    sb = {"meta": {"title": a.name or pr.name}, "avatar": ({"height": fr["height"]} if fr.get("height") else {}),
          "cover": {"headline": heads[0] if heads else scenes[0]["layers"][0]["text"], "variant": "hero"}, "scenes": scenes}
    if not fr["avatar"].get("show"):
        sb["avatar"] = False
    write_json(pr / "storyboard.json", sb)
    ok(f"clip project: {pr}")
    if a.no_render:
        return
    if not fr.get("plain") and not imagegen.key("GEMINI_API_KEY"):
        a.placeholders = True
    if not fr.get("plain"):
        imagegen.run(pr, None, False, 3, a.placeholders, False)
    R.render_video(pr, False, None, False, None, None, a.placeholders)
    mix.run_mix(pr)
    if prof["covers"].get("enabled", True):
        cover.make_covers(pr)
        cover.embed(pr / "out" / "final.mp4", pr / "out" / "cover.jpg")
    qa.run_qa(pr)
    say(f"Done: {pr / 'out' / 'final.mp4'}")
