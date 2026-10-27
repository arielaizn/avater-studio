"""The uniqueness engine.

Every video gets a *world* (a place, a material, a light, a typographic voice, a sound) that differs from the recent
videos on purpose, while the spine (data/spine.json) keeps the quality and the studio feel constant.

  propose  -> several candidate worlds that fit the topic and pass the distance rules
  pick     -> turn one candidate into <project>/concept.json (add the topic-specific metaphor)
  check    -> verify a concept.json against the history
  commit   -> log it in ~/.avatar-studio/history.json (do this when the video ships)
  history  -> what the recent videos looked like
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import random
import re
from datetime import date
from pathlib import Path

from .common import HISTORY_PATH, PLUGIN_ROOT, fail, load_profile, ok, read_json, say, warn, write_json

WORLDS = read_json(PLUGIN_ROOT / "data" / "worlds.json")
SPINE = read_json(PLUGIN_ROOT / "data" / "spine.json")
AXES = WORLDS["axes"]

LIGHT_TEXT = {
    "golden-window": "warm golden window light with soft moving shadows",
    "noir-spot": "a single hard noir spotlight with deep black shadow",
    "flat-fluorescent": "flat even fluorescent light with soft reflections",
    "neon-rim": "coloured neon rim light with haze and wet reflections",
    "overcast-soft": "soft overcast daylight, gentle and shadowless",
    "candle-warm": "warm flickering candle-gold light with volumetric haze",
    "softbox-clean": "clean bright softbox light with crisp highlights",
    "dawn-blue": "cool blue dawn light mixed with a warm lamp",
    "sodium-street": "orange sodium street-lamp light with cool fill",
    "lamp-pool": "a single warm lamp pool and deep surrounding shadow",
    "safelight-red": "deep red darkroom safelight",
    "projector-beam": "a volumetric projector beam cutting a dark smoky room",
}

WEIGHTS = {"family": 3.0, "material": 2.0, "light": 1.5, "type": 1.5, "hue": 2.0, "transition": 1.0, "captions": 1.0, "sound": 1.0}
MIN_DIST = 0.55          # against each of the last 8 videos
WINDOW_DIST = 8
WINDOW_FAMILY = 5        # family and material must not repeat inside this window
WINDOW_HUE = 3           # accent hue must differ by >= 40 degrees inside this window
MIN_HUE_GAP = 40
# these words in a plate prompt are refused, see spine.forbidden_styles


def _world(wid: str) -> dict:
    for w in WORLDS["worlds"]:
        if w["id"] == wid:
            return w
    fail(f"Unknown world '{wid}'", "run `avs concept worlds` to list them")


def fingerprint_of_world(w: dict, over: dict | None = None) -> dict:
    over = over or {}
    return {
        "family": w["family"], "material": w["material"],
        "light": over.get("light", w["light"]), "type": over.get("type", w["type"]["id"]),
        "hue": int(round(over.get("hue", w["hue"]))) % 360,
        "transition": over.get("transition", w["transition"]),
        "captions": over.get("captions", w["captions"]), "sound": over.get("sound", w["sound"]),
    }


def hue_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def distance(a: dict, b: dict) -> float:
    tot = sum(WEIGHTS.values())
    s = 0.0
    for k, wt in WEIGHTS.items():
        if k == "hue":
            s += wt * min(1.0, hue_gap(a["hue"], b["hue"]) / 90.0)
        else:
            s += wt * (0.0 if a.get(k) == b.get(k) else 1.0)
    return round(s / tot, 3)


def violations(fp: dict, hist: list[dict]) -> list[str]:
    out = []
    recent = hist[-WINDOW_DIST:]
    for i, h in enumerate(reversed(recent)):
        d = distance(fp, h["fingerprint"])
        if d < MIN_DIST:
            out.append(f"too close to '{h.get('title') or h.get('id')}' ({i + 1} video(s) ago): distance {d} < {MIN_DIST}")
    for h in hist[-WINDOW_FAMILY:]:
        f = h["fingerprint"]
        if f["family"] == fp["family"]:
            out.append(f"family '{fp['family']}' was used in '{h.get('title') or h.get('id')}'")
        if f["material"] == fp["material"]:
            out.append(f"material '{fp['material']}' was used in '{h.get('title') or h.get('id')}'")
    for h in hist[-WINDOW_HUE:]:
        f = h["fingerprint"]
        if hue_gap(f["hue"], fp["hue"]) < MIN_HUE_GAP:
            out.append(f"accent hue {fp['hue']} is within {MIN_HUE_GAP} degrees of '{h.get('title') or h.get('id')}'")
        if f["light"] == fp["light"]:
            out.append(f"light '{fp['light']}' repeats '{h.get('title') or h.get('id')}'")
    return out


# --------------------------------------------------------------- colour
def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c * 255)))) for c in (r, g, b))


def shift_hex(h: str, deg: float) -> str:
    r, g, b = _hex_to_rgb(h)
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.08:                      # greys stay grey
        return h
    return _rgb_to_hex(*colorsys.hls_to_rgb((hh + deg / 360.0) % 1.0, l, s))


def shift_palette(pal: dict, deg: float) -> dict:
    return {k: (shift_hex(v, deg) if k in ("bg", "accent", "accent2") else v) for k, v in pal.items()}


# -------------------------------------------------------------- history
def history() -> list[dict]:
    return read_json(HISTORY_PATH, {"videos": []})["videos"]


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^\w֐-׿]+", s.lower()) if len(t) > 1}


def affinity_score(w: dict, topic_tokens: set[str]) -> float:
    sc = 0.0
    for a in w["affinity"]:
        a = a.lower()
        for t in topic_tokens:
            if a == t:
                sc += 1.0
            elif len(a) > 2 and (a in t or t in a) and min(len(a), len(t)) >= 3:
                sc += 0.6
    return sc


def build_candidate(w: dict, over: dict, hist: list[dict], topic: str) -> dict:
    shift = over.get("hue_shift", 0)
    pal = shift_palette(w["palette"], shift) if shift else dict(w["palette"])
    hue = (w["hue"] + shift) % 360
    over = dict(over, hue=hue)
    fp = fingerprint_of_world(w, over)
    typ = dict(w["type"])
    if over.get("type") and over["type"] != w["type"]["id"]:
        t = AXES["type"][over["type"]]
        typ = {"id": over["type"], "display": t["display"], "weight": t["weight"], "body": t["body"], "case": "none", "tracking": "0em"}
    style = w["plate_style"]
    if fp["light"] != w["light"]:
        style += f". Lighting override (replaces any other lighting above): {LIGHT_TEXT[fp['light']]}"
    if shift:
        style += f". Colour override: dominant background tone {pal['bg']}, accent {pal['accent']}, secondary accent {pal['accent2']}"
    return {
        "base": w["id"], "name": w["name"], "remixed": sorted(k for k in ("light", "type", "transition", "captions", "sound") if fp[k] != fingerprint_of_world(w)[k]) + (["hue"] if shift else []),
        "fingerprint": fp,
        "setting": w["setting"], "props": w["props"], "motif": w["motif"],
        "palette": pal, "type": typ, "captions": fp["captions"], "transition": fp["transition"], "sound": fp["sound"],
        "light": fp["light"], "grain": w["grain"], "vignette": w["vignette"], "plate_style": style,
        "min_distance": min([distance(fp, h["fingerprint"]) for h in hist[-WINDOW_DIST:]] or [1.0]),
    }


def propose(topic: str, k: int = 6, seed: int | None = None, avoid: list[str] | None = None) -> list[dict]:
    rng = random.Random(seed if seed is not None else random.SystemRandom().randrange(1 << 30))
    hist = history()
    toks = _tokens(topic)
    scored = []
    for w in WORLDS["worlds"]:
        if avoid and w["id"] in avoid:
            continue
        scored.append((affinity_score(w, toks) + rng.uniform(0, 1.1), w))
    scored.sort(key=lambda x: -x[0])
    out, fams = [], set()
    recent_axes = {a: {h["fingerprint"][a] for h in hist[-3:]} for a in ("light", "type", "transition", "captions", "sound")}
    for sc, w in scored:
        if w["family"] in fams and len(out) < k - 1:
            continue
        # hard window constraints that remixing cannot repair
        if any(h["fingerprint"]["family"] == w["family"] or h["fingerprint"]["material"] == w["material"] for h in hist[-WINDOW_FAMILY:]):
            continue
        cand = None
        for attempt in range(60):
            over = {}
            if attempt > 0:
                axes = rng.sample(["light", "type", "transition", "captions", "sound"], rng.randint(1, 4))
                for a in axes:
                    pool = [v for v in (AXES["type"].keys() if a == "type" else AXES[a]) if v not in recent_axes[a]]
                    over[a] = rng.choice(pool or list(AXES[a]))
                if attempt > 6 and rng.random() < 0.6:
                    over["hue_shift"] = rng.choice([-1, 1]) * rng.randint(40, 120)
            fp = fingerprint_of_world(w, dict(over, hue=(w["hue"] + over.get("hue_shift", 0)) % 360))
            if not violations(fp, hist):
                cand = build_candidate(w, over, hist, topic)
                break
        if cand:
            cand["fit"] = round(sc, 2)
            cand["why"] = [a for a in w["affinity"] if a.lower() in toks or any(len(a) > 2 and (a.lower() in t or t in a.lower()) and min(len(a), len(t)) >= 3 for t in toks)][:4]
            out.append(cand)
            fams.add(w["family"])
        if len(out) >= k:
            break
    return out


def finalize(cand: dict, title: str, topic: str, metaphor: str, hero: str, extra: dict | None = None) -> dict:
    cid = f"{date.today():%Y%m%d}-{cand['base']}-{hashlib.sha1((title + topic).encode()).hexdigest()[:4]}"
    c = {"version": 1, "id": cid, "title": title, "topic": topic, **cand, "metaphor": metaphor, "hero_object": hero}
    c.update(extra or {})
    return c


def check(concept: dict, hist: list[dict] | None = None) -> list[str]:
    hist = history() if hist is None else hist
    fp = concept.get("fingerprint")
    if not fp:
        return ["concept.json has no fingerprint (use `avs concept pick`)"]
    miss = [k for k in WEIGHTS if k not in fp]
    if miss:
        return [f"fingerprint is missing: {', '.join(miss)}"]
    hist = [h for h in hist if h.get("id") != concept.get("id")]
    return violations(fp, hist)


def commit(concept: dict, project: str = "") -> None:
    data = read_json(HISTORY_PATH, {"videos": []})
    data["videos"] = [v for v in data["videos"] if v.get("id") != concept["id"]]
    data["videos"].append({"id": concept["id"], "date": f"{date.today():%Y-%m-%d}", "title": concept.get("title", ""),
                           "topic": concept.get("topic", ""), "base": concept.get("base"), "fingerprint": concept["fingerprint"],
                           "metaphor": concept.get("metaphor", ""), "project": project})
    write_json(HISTORY_PATH, data)


def lint_prompt(prompt: str) -> list[str]:
    low = prompt.lower()
    return [w for w in SPINE["forbidden_styles"] if re.search(r"\b" + re.escape(w) + r"\b", low)]


# --------------------------------------------------------------------- cli
def _fmt(i: int, c: dict) -> str:
    fp = c["fingerprint"]
    return (f"[{i}] {c['name']}  (base {c['base']}, fit {c['fit']}, min distance {c['min_distance']})\n"
            f"    material: {fp['material']} | light: {fp['light']} | accent hue: {fp['hue']} | type: {fp['type']}\n"
            f"    captions: {fp['captions']} | transition: {fp['transition']} | sound: {fp['sound']}\n"
            f"    setting: {c['setting']}\n    motif: {c['motif']}" + (f"\n    remixed: {', '.join(c['remixed'])}" if c["remixed"] else ""))


def cmd_concept(args) -> None:
    a = args.action
    if a == "worlds":
        for w in WORLDS["worlds"]:
            say(f"{w['id']:<22} {w['family']:<13} {w['material']:<28} {w['light']}")
        return
    if a == "history":
        h = history()
        if not h:
            say("No videos yet: every world is available.")
        for v in h[-15:]:
            fp = v["fingerprint"]
            say(f"{v['date']}  {v['title'] or v['id']:<40} {v['base']:<20} {fp['material']} / {fp['light']} / hue {fp['hue']}")
        return
    if a == "propose":
        if not args.topic:
            fail("Give --topic", "e.g. --topic \"why most AI avatars look fake\"")
        cands = propose(args.topic, args.n, args.seed, args.avoid.split(",") if args.avoid else None)
        if not cands:
            fail("No world passes the distance rules right now", "run `avs concept history`; use --avoid to relax nothing, or add a new world to data/worlds.json")
        for i, c in enumerate(cands, 1):
            say(_fmt(i, c))
        if args.project:
            from .common import project_path
            write_json(project_path(args.project) / "concept_candidates.json", cands)
            say(f"\nSaved {len(cands)} candidates to concept_candidates.json")
        else:
            say("\n" + json.dumps(cands, ensure_ascii=False))
        return
    if a == "pick":
        from .common import project_path
        pr = project_path(args.project)
        cands = read_json(pr / "concept_candidates.json")
        if not cands:
            fail("No concept_candidates.json", "run `avs concept propose --topic ... --project ...` first")
        c = cands[args.index - 1]
        extra = read_json(args.extra, {}) if args.extra else {}
        con = finalize(c, args.title, args.topic or "", args.metaphor or "", args.hero or "", extra)
        write_json(pr / "concept.json", con)
        ok(f"concept.json written: {con['id']}")
        problems = check(con)
        for p in problems:
            warn(p)
        return
    if a in ("check", "commit"):
        from .common import project_path
        pr = project_path(args.project)
        con = read_json(pr / "concept.json")
        if not con:
            fail("No concept.json in the project", "run `avs concept pick` first")
        problems = check(con)
        if problems:
            for p in problems:
                warn(p)
            if a == "check" or not args.force:
                fail("This concept is too close to a recent video", "pick another candidate or remix more axes, then check again", 2)
        ok("distinct enough from the last videos")
        if a == "commit":
            commit(con, str(pr))
            ok(f"logged in history: {con['id']}")
        return
    fail(f"Unknown action {a}")
