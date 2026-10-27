"""Quality gate: loudness, black/frozen frames, pacing, text overflow and collisions with the presenter's face."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import compose
from .common import duration, fail, ffmpeg, ok, probe_stream, read_json, run, say, warn, write_json
from .render import run_node


def _overlap(a: dict, b: dict) -> float:
    x = max(0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    y = max(0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    return (x * y) / max(1.0, min(a["w"] * a["h"], b["w"] * b["h"]))


def layout(proj: Path, res: dict) -> list[str]:
    times = []
    for s in res["scenes"]:
        d = s["end"] - s["start"]
        times += [s["start"] + d * 0.45, s["start"] + d * 0.85]
    times = [round(min(t, res["meta"]["duration"] - 0.05), 2) for t in times]
    out = run_node(["--project", str(proj), "--qa", ",".join(str(t) for t in times)], capture=True)
    try:
        frames = json.loads(out.strip().splitlines()[-1])
    except Exception:
        return ["layout check could not read the renderer output"]
    issues = []
    for fr in frames:
        t, W, H = fr["t"], fr["W"], fr["H"]
        items = fr["rects"] + [dict(c, kind="caption") for c in fr["caps"]]
        for it in items:
            if it["x"] < -4 or it["x"] + it["w"] > W + 4 or it["y"] < -4 or it["y"] + it["h"] > H + 4:
                issues.append(f"t={t}s {it['kind']} '{it.get('text', '')[:24]}' leaves the frame")
            if it["kind"] == "headline" and it.get("sw", 0) > it.get("cw", 0) + 2:
                issues.append(f"t={t}s headline '{it['text'][:24]}' overflows its box")
            f = fr.get("face")
            if f and it["kind"] in ("headline", "caption", "card", "sticker") and _overlap(it, f) > 0.12:
                issues.append(f"t={t}s {it['kind']} '{it.get('text', '')[:24]}' covers the presenter's face")
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a["kind"] == "counter" or b["kind"] == "counter":
                    continue
                if _overlap(a, b) > 0.35:
                    issues.append(f"t={t}s {a['kind']} '{a.get('text', '')[:18]}' overlaps {b['kind']} '{b.get('text', '')[:18]}'")
    return sorted(set(issues))


def loudness(path: Path) -> dict:
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=I=-14:TP=-1:LRA=9:print_format=json", "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr or "", re.S)
    if not m:
        return {}
    j = json.loads(m.group(0))
    return {"lufs": float(j["input_i"]), "true_peak": float(j["input_tp"]), "lra": float(j["input_lra"])}


def video_scan(path: Path) -> dict:
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", "blackdetect=d=0.25:pix_th=0.06,freezedetect=n=0.002:d=1.6", "-an", "-f", "null", "-"], check=False)
    err = r.stderr or ""
    return {"black": re.findall(r"black_start:([\d.]+).*?black_duration:([\d.]+)", err), "freeze": re.findall(r"freeze_start: ([\d.]+)", err)}


def contact_sheet(path: Path, dest: Path, cols: int = 6, rows: int = 3) -> Path:
    d = duration(path)
    n = cols * rows
    fps = n / max(1.0, d)
    ffmpeg("-i", str(path), "-vf", f"fps={fps:.5f},scale=240:-2,tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1", "-q:v", "3", str(dest))
    return dest


def run_qa(proj: Path, video: Path | None = None, layout_check: bool = True) -> bool:
    res = read_json(proj / "comp" / "resolved.json") or compose.build(proj, quiet=True)["resolved"]
    video = video or (proj / "out" / "final.mp4")
    if not video.exists():
        video = proj / "out" / "video_silent.mp4"
    if not video.exists():
        fail("No video to check", "run `avs render` first")
    prob, notes = [], []
    st = probe_stream(video)
    w, h = st.get("width"), st.get("height")
    if (w, h) != (res["meta"]["width"], res["meta"]["height"]):
        prob.append(f"size is {w}x{h}, expected {res['meta']['width']}x{res['meta']['height']}")
    scenes = res["scenes"]
    lens = [s["end"] - s["start"] for s in scenes]
    avg = sum(lens) / len(lens)
    notes.append(f"{len(scenes)} scenes, avg {avg:.1f}s, min {min(lens):.1f}s, max {max(lens):.1f}s, total {res['meta']['duration']:.1f}s")
    if avg > 3.6:
        prob.append(f"pacing is slow (average scene {avg:.1f}s, target 2.2 to 3.2s)")
    if max(lens) > 5.0:
        prob.append(f"one scene lasts {max(lens):.1f}s: split it or add a beat inside it")
    if res["meta"]["duration"] > 95:
        prob.append("longer than 95 seconds: short-form retention drops sharply")
    if video.name == "final.mp4":
        lo = loudness(video)
        if lo:
            notes.append(f"loudness {lo['lufs']:.1f} LUFS, true peak {lo['true_peak']:.1f} dBTP")
            if abs(lo["lufs"] + 14) > 1.2:
                prob.append(f"loudness is {lo['lufs']:.1f} LUFS, target -14")
            if lo["true_peak"] > -0.9:
                prob.append(f"true peak {lo['true_peak']:.1f} dBTP is too hot")
    sc = video_scan(video)
    for s, d in sc["black"]:
        if float(s) > 0.2 and float(s) < res["meta"]["duration"] - 0.6:
            prob.append(f"black frames at {s}s for {d}s")
    if sc["freeze"]:
        prob.append("frozen picture at " + ", ".join(sc["freeze"][:4]) + "s: add camera move or beats to that scene")
    if layout_check:
        prob += layout(proj, res)
    sheet = contact_sheet(video, proj / "out" / "contact_sheet.jpg")
    for n in notes:
        say("  " + n)
    write_json(proj / "out" / "qa.json", {"problems": prob, "notes": notes})
    if prob:
        for p in prob:
            warn(p)
        say(f"\nContact sheet: {sheet}")
        return False
    ok(f"QA passed. Contact sheet: {sheet}")
    return True
