"""storyboard.json  ->  comp/resolved.json + comp/index.html

The storyboard is the creative contract (scenes, plates, layers, anchors to spoken words). This step resolves every
anchor to seconds using the real word timings, checks the result, and writes the page the renderer opens.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import align as A
from .common import PLUGIN_ROOT, fail, load_profile, ok, read_json, say, warn, write_json

TRANSITION_DUR = {"cut": 0.0, "soft-push": 0.45, "whip-pan": 0.4, "iris": 0.55, "slide-wipe": 0.5, "dip-flash": 0.4,
                  "zoom-through": 0.5, "paper-turn": 0.55, "blur-dissolve": 0.5, "shutter": 0.5, "glitch-cut": 0.3}
LAYER_TYPES = {"headline", "stamp", "badge", "circle", "underline", "strike", "arrow", "counter", "card", "sticker", "list", "quote",
               "lower", "bars", "ticker", "compare", "shape", "flash", "particles", "lightsweep", "html"}
SETTLE_TYPES = {"headline", "stamp", "badge", "card", "sticker", "counter", "quote", "compare", "circle", "underline", "arrow"}
TR_SFX = {"whip-pan": "whoosh", "soft-push": "swish", "iris": "riser", "slide-wipe": "whoosh", "dip-flash": "impact",
          "zoom-through": "whoosh-deep", "paper-turn": "paper", "shutter": "shutter", "glitch-cut": "glitch"}
LAYER_SFX = {"stamp": "stamp", "badge": "pop", "circle": "scribble", "underline": "scribble", "arrow": "scribble", "strike": "scribble",
             "counter": "tick-roll", "flash": "impact", "card": "swish", "sticker": "pop", "compare": "swish", "lower": "swish"}
FONTS_BUNDLED = {"Heebo", "Rubik", "Secular One", "Karantina", "Suez One", "Frank Ruhl Libre", "Alef", "Amatic SC", "Bellefair",
                 "David Libre", "Miriam Libre", "Assistant", "Varela Round"}


class Resolver:
    def __init__(self, words: list[dict], timing: dict, total: float):
        self.words, self.timing, self.total = words, timing or {}, total
        self.norms = [A.norm(w["w"]) for w in words]
        self.scenes: dict[str, dict] = {}

    def _word_index(self, text: str, nth: int) -> int:
        n = A.norm(text)
        hits = [i for i, x in enumerate(self.norms) if x == n]
        if not hits:   # Hebrew prefixes: the script says הקלוד, the anchor says קלוד
            hits = [i for i, x in enumerate(self.norms) if n and x.endswith(n) and len(x) - len(n) <= 2]
        if len(hits) < nth:
            near = ", ".join(w["w"] for w in self.words[:0]) or ""
            fail(f"Anchor word '{text}' (#{nth}) is not in the narration",
                 f"use w:<index> instead, or check the spelling against audio/words.json {near}")
        return hits[nth - 1]

    def at(self, spec, scene_start: float | None = None, default=None):
        if spec is None:
            return default
        if isinstance(spec, (int, float)):
            return float(spec)
        s = str(spec).strip()
        if re.fullmatch(r"\+\d+(\.\d+)?", s):
            return (scene_start or 0.0) + float(s[1:])
        if s == "end":
            return self.total
        off = 0.0
        m = re.search(r"([+-]\d+(?:\.\d+)?)$", s)
        if m and not re.fullmatch(r"[+-]?\d+(\.\d+)?", s):
            body = s[: m.start()]
            if re.match(r"^(w|word|p|scene):", body):
                off, s = float(m.group(1)), body
        edge = "start"
        m = re.search(r"\.(start|end)$", s)
        if m:
            edge, s = m.group(1), s[: m.start()]
        if s.startswith("w:"):
            i = int(s[2:])
            if i < 0 or i >= len(self.words):
                fail(f"Anchor w:{i} is out of range (the narration has {len(self.words)} words)", "see audio/words.json")
            return round(self.words[i][edge] + off, 3)
        if s.startswith("word:"):
            body, nth = s[5:], 1
            m2 = re.match(r"^(.*)#(\d+)$", body)
            if m2:
                body, nth = m2.group(1), int(m2.group(2))
            return round(self.words[self._word_index(body, nth)][edge] + off, 3)
        if s.startswith("p:"):
            paras = self.timing.get("paragraphs") or []
            i = int(s[2:])
            if i >= len(paras):
                fail(f"Anchor p:{i} is out of range", "paragraphs are separated by blank lines in script.txt")
            return round(paras[i][edge] + off, 3)
        if s.startswith("scene:"):
            sid = s[6:]
            if sid not in self.scenes:
                fail(f"Anchor refers to scene '{sid}' which is not defined before it", "scenes can only refer to earlier scenes")
            return round(self.scenes[sid][edge] + off, 3)
        try:
            return float(s)
        except ValueError:
            fail(f"Cannot read time anchor '{spec}'", "use seconds, w:<index>, word:<text>, p:<index>, scene:<id>.end, +<secs>, or end")


def _abs(path: str | None) -> str | None:
    if not path:
        return path
    if path.startswith(("http", "/", "data:")):
        return path
    return "/" + path.replace("\\", "/")


def build(proj: Path, placeholders: bool = False, quiet: bool = False) -> dict:
    prof = load_profile()
    sb = read_json(proj / "storyboard.json")
    if not sb:
        fail("No storyboard.json in the project", "write it (see the avatar-visuals skill), then run `avs build`")
    concept = read_json(proj / "concept.json")
    if not concept:
        fail("No concept.json in the project", "run `avs concept propose` and `avs concept pick` first")
    words = read_json(proj / "audio" / "words.json")
    timing = read_json(proj / "audio" / "timing.json", {})
    if not words:
        fail("No audio/words.json", "voice the script first: `avs tts`")
    for i, w in enumerate(words):
        w["i"] = i
    total = float(sb.get("meta", {}).get("duration") or timing.get("total") or words[-1]["end"] + 1.0)
    pr = read_json(proj / "project.json", {})
    meta = {"width": pr.get("width", 1080), "height": pr.get("height", 1920), "fps": pr.get("fps", 30), "duration": round(total, 3),
            "dir": sb.get("meta", {}).get("dir") or prof.get("direction", "rtl"), "lang": prof.get("language", "he"),
            "title": sb.get("meta", {}).get("title") or concept.get("title", "")}
    R = Resolver(words, timing, total)
    problems: list[str] = []

    # --- avatar
    fit = read_json(proj / "twin" / "fit.json")
    sbav = sb.get("avatar", {}) if isinstance(sb.get("avatar"), dict) else {}
    avatar_mode = "never" if sb.get("avatar") is False or sbav.get("mode") == "never" else "always"
    if not fit and avatar_mode != "never":
        problems.append("no twin/fit.json: the presenter is not prepared (run `avs avatar`); building without a presenter")
    avatar = None
    if fit and avatar_mode != "never":
        avatar = {"dir": "/twin/frames", "fps": fit["fps"], "frames": fit["frames"], "width": fit["width"], "height": fit["height"],
                  "opaque": not fit.get("alpha", True), "face": fit.get("face"), "heightFrac": sbav.get("height", 0.40),
                  "maxWidthFrac": sbav.get("max_width", 1.08), "offset": sbav.get("offset", 0.0), "windows": []}

    # --- world
    world = {"palette": concept["palette"], "type": concept["type"], "captions": concept.get("captions", "word-pop"),
             "grain": concept.get("grain", 0.1), "vignette": concept.get("vignette", 0.3), "transition": concept.get("transition", "soft-push")}
    for f in {world["type"]["display"], world["type"]["body"]}:
        if f not in FONTS_BUNDLED:
            problems.append(f"font '{f}' is not bundled; the page falls back to Heebo")

    # --- scenes
    scenes_in = sb.get("scenes") or []
    if not scenes_in:
        fail("storyboard.json has no scenes", "add at least one scene")
    scenes: list[dict] = []
    sfx: list[dict] = []
    for idx, sc in enumerate(scenes_in):
        sid = sc.get("id") or f"s{idx + 1}"
        start = 0.0 if idx == 0 and sc.get("start") is None else R.at(sc.get("start"), None, None)
        if start is None:
            fail(f"Scene {sid} has no start", "give each scene a start (seconds or w:<index>)")
        scenes.append({"id": sid, "start": start, "_raw": sc})
        R.scenes[sid] = {"start": start, "end": start}
    for idx, S in enumerate(scenes):
        nxt = scenes[idx + 1]["start"] if idx + 1 < len(scenes) else total
        end = R.at(S["_raw"].get("end"), S["start"], nxt)
        S["end"] = round(min(end, total) if idx + 1 == len(scenes) else end, 3)
        R.scenes[S["id"]] = {"start": S["start"], "end": S["end"]}
        if S["end"] <= S["start"]:
            fail(f"Scene {S['id']} ends before it starts ({S['start']} -> {S['end']})", "check the anchors")
    # now full scene objects
    out_scenes = []
    for idx, S in enumerate(scenes):
        sc = S["_raw"]
        tr = sc.get("transition", world["transition"] if idx else "cut")
        tr = {"type": tr, "dur": None} if isinstance(tr, str) else dict(tr)
        if idx == 0:
            tr = {"type": "cut", "dur": 0.0}
        if tr["type"] not in TRANSITION_DUR:
            problems.append(f"scene {S['id']}: unknown transition '{tr['type']}', using cut")
            tr["type"] = "cut"
        tr["dur"] = TRANSITION_DUR[tr["type"]] if tr.get("dur") is None else float(tr["dur"])
        plate = dict(sc.get("plate") or {})
        if plate.get("stage"):
            st = json.loads(json.dumps(plate["stage"]))
            if not st.get("layers"):
                problems.append(f"scene {S['id']}: stage has no layers")
            for li, Ly in enumerate(st.get("layers", [])):
                src = Ly.get("src") or f"plates/{S['id']}_L{li}.png"
                if not (proj / src).exists() and not src.startswith("http"):
                    problems.append(f"scene {S['id']}: stage layer {li} image {src} does not exist" + (" (prompt present: run `avs imagegen`)" if Ly.get("prompt") else ""))
                    plate["_missing"] = True
                Ly["src"] = _abs(src)
                Ly.pop("prompt", None)
            if len(st.get("layers", [])) < 3:
                problems.append(f"scene {S['id']}: a depth stage needs 3 or more layers (background, middle, foreground) to feel 3D")
            plate["stage"] = st
        if plate.get("src") is None and not plate.get("bg") and not plate.get("stage"):
            for ext in ("png", "jpg", "jpeg", "webp"):
                if (proj / "plates" / f"{S['id']}.{ext}").exists():
                    plate["src"] = f"plates/{S['id']}.{ext}"
                    break
        if plate.get("src") and not (proj / plate["src"]).exists() and not plate["src"].startswith("http"):
            problems.append(f"scene {S['id']}: plate {plate['src']} does not exist" + (" (prompt present: run `avs imagegen`)" if plate.get("prompt") else ""))
            plate["_missing"] = True
        if not plate.get("src") and not plate.get("bg") and not plate.get("stage"):
            problems.append(f"scene {S['id']}: no plate")
            plate["_missing"] = True
        plate["src"] = _abs(plate.get("src"))
        plate.pop("prompt", None)
        dur = S["end"] - S["start"]
        if dur > 4.6 and not sc.get("allow_long"):
            problems.append(f"scene {S['id']} is {dur:.1f}s: long scenes lose retention; split it or add motion (spine: 1.2-4.5s)")
        if dur < 0.9 and idx + 1 < len(scenes):
            problems.append(f"scene {S['id']} is only {dur:.1f}s")
        layers = []
        first = idx == 0
        for L0 in sc.get("layers", []):
            L = dict(L0)
            t = L.get("type")
            if t not in LAYER_TYPES:
                problems.append(f"scene {S['id']}: unknown layer type '{t}'")
                continue
            default_at = S["start"] + (0.15 if first else max(0.1, tr["dur"] * 0.6))
            L["at"] = R.at(L.get("at"), S["start"], default_at)
            if L.get("until") is not None:
                L["until"] = R.at(L["until"], S["start"], S["end"])
            if t == "list":
                for k, it in enumerate(L.get("items", [])):
                    if it.get("at") is not None:
                        it["at"] = R.at(it["at"], S["start"])
            if first and L["at"] <= 0.06 and t in SETTLE_TYPES and L.get("settle") is None:
                L["settle"] = True
            if t == "headline" and len(re.sub(r"\*", "", L.get("text", "")).split()) > 5:
                problems.append(f"scene {S['id']}: headline '{L.get('text', '')[:30]}...' has more than 5 words; one idea, max 4 words")
            for key in ("src",):
                if L.get(key):
                    L[key] = _abs(L[key])
                    if L[key].startswith("/") and not (proj / L[key].lstrip("/")).exists():
                        problems.append(f"scene {S['id']}: {t} image {L[key]} does not exist")
            for side in ("left", "right"):
                if isinstance(L.get(side), dict) and L[side].get("src"):
                    L[side]["src"] = _abs(L[side]["src"])
            layers.append(L)
            if t in LAYER_SFX and sb.get("sfx") is not False and not L.get("silent"):
                sfx.append({"t": round(L["at"], 3), "name": LAYER_SFX[t], "gain": -16.0})
            if t == "headline" and L.get("anim") == "slam" and sb.get("sfx") is not False:
                sfx.append({"t": round(L["at"], 3), "name": "hit", "gain": -12.0})
        if len(layers) > 9:
            problems.append(f"scene {S['id']} has {len(layers)} layers: too busy for 1-4 seconds")
        for e in sc.get("sfx", []) or []:
            sfx.append({"t": R.at(e.get("at"), S["start"], S["start"]), "name": e["name"], "gain": e.get("gain", -14.0)})
        if idx > 0 and tr["type"] in TR_SFX and sb.get("sfx") is not False:
            sfx.append({"t": round(S["start"], 3), "name": TR_SFX[tr["type"]], "gain": -17.0})
        av = sc.get("avatar", True)
        av_cfg = av if isinstance(av, dict) else {}
        show = bool(av) if not isinstance(av, dict) else av.get("show", True)
        if avatar is None:
            show = False
        if plate.get("beats"):
            for b in plate["beats"]:
                b["at"] = R.at(b.get("at"), S["start"], S["start"])
        out_scenes.append({"id": S["id"], "start": S["start"], "end": S["end"], "transition": tr, "plate": plate, "layers": layers,
                           "avatar": {"show": show, **{k: v for k, v in av_cfg.items() if k != "show"}}})

    # --- avatar windows (merge consecutive scenes that show the presenter)
    if avatar is not None:
        cur = None
        for i, S in enumerate(out_scenes):
            if S["avatar"]["show"]:
                if cur is None:
                    cur = {"t0": S["start"], "t1": S["end"], "enter": S["avatar"].get("enter") or ("cut" if S["start"] <= 0.01 else "rise"),
                           "exit": "fall", "x": S["avatar"].get("x", 0.0)}
                else:
                    cur["t1"] = S["end"]
                cur["exit"] = S["avatar"].get("exit", cur["exit"])
            elif cur is not None:
                avatar["windows"].append(cur)
                cur = None
        if cur is not None:
            avatar["windows"].append(cur)
        if not avatar["windows"]:
            problems.append("the presenter is never shown (every scene has avatar:false)")
        if avatar["windows"] and avatar["windows"][0]["t0"] > 4.0:
            problems.append("the presenter first appears after 4s: viewers want a human in the first seconds")
        if fit and fit["seconds"] + 0.15 < total:
            problems.append(f"the twin clip is {fit['seconds']:.1f}s but the narration is {total:.1f}s: the presenter freezes at the end")

    # --- captions
    cap = dict(sb.get("captions") or {})
    cap.setdefault("style", world["captions"])
    cap.setdefault("size", 60)
    y_av, y_free = cap.pop("y_avatar", 0.575), cap.pop("y_free", 0.74)
    zones = []
    for S in out_scenes:
        zones.append({"t0": S["start"], "y": y_av if S["avatar"]["show"] else y_free})
    cap["zones"] = zones

    # --- cover
    cov = dict(sb.get("cover") or {})
    if cov.get("plate"):
        cov["plate"] = _abs(cov["plate"])
    cov.setdefault("headline", meta["title"])
    if not cov.get("headline"):
        problems.append("no cover headline (storyboard.cover.headline)")

    resolved = {"meta": meta, "world": world, "avatar": avatar, "words": words, "scenes": out_scenes, "captions": cap, "cover": cov}
    comp = proj / "comp"
    comp.mkdir(exist_ok=True)
    write_json(comp / "resolved.json", resolved)
    sfx.sort(key=lambda e: e["t"])
    write_json(comp / "sfx_cues.json", sfx)
    html = _html(resolved)
    (comp / "index.html").write_text(html, encoding="utf-8")

    missing = [p for p in problems if "does not exist" in p or "no plate" in p]
    if placeholders and missing:
        from . import imagegen
        n = imagegen.fill_placeholders(proj, out_scenes, concept)
        say(f"  placeholder plates generated: {n}")
        return build(proj, False, quiet)
    if not quiet:
        ok(f"built comp/index.html: {len(out_scenes)} scenes, {total:.1f}s, avg scene {total / len(out_scenes):.1f}s")
        for p in problems:
            warn(p)
    return {"resolved": resolved, "problems": problems}


def _html(res: dict) -> str:
    data = json.dumps(res, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="{res['meta']['lang']}" dir="{res['meta']['dir']}"><head><meta charset="utf-8"><title>{res['meta'].get('title') or 'video'}</title>
<meta name="viewport" content="width={res['meta']['width']}">
<link rel="stylesheet" href="/__fonts/fonts.css"><link rel="stylesheet" href="/__kit/kit.css">
</head><body><div id="stage"></div>
<script>window.SB = {data};</script>
<script src="/__kit/engine.js"></script><script src="/__kit/kit.js"></script>
</body></html>
"""
