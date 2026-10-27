"""Audio: voice + a music bed (ducked under the voice) + sound effects, loudness-normalised, muxed onto the picture."""
from __future__ import annotations

import json
import re
import wave
import zlib
from pathlib import Path

import numpy as np

from . import sfx as S
from .common import AvsError, duration, fail, ffmpeg, load_profile, ok, read_json, run, say, warn, write_json

SR = S.SR


def _write(path: Path, x: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def build_tracks(proj: Path, total: float, concept: dict, music: bool, effects: bool, extra_cues: list | None = None) -> dict:
    a = proj / "audio"
    seed = zlib.crc32(concept.get("id", "x").encode())
    paths = {}
    if music:
        sound = concept.get("sound") or "warm-pad"
        x = S.bed(sound, total, seed)
        fade = int(1.5 * SR)
        x[-fade:] *= np.linspace(1, 0, fade)
        x[: int(0.4 * SR)] *= np.linspace(0, 1, int(0.4 * SR))
        _write(a / "bed.wav", x)
        paths["bed"] = a / "bed.wav"
    if effects:
        cues = (read_json(proj / "comp" / "sfx_cues.json", []) or []) + (extra_cues or [])
        buf = np.zeros(int((total + 2) * SR), dtype=np.float32)
        cache: dict[str, np.ndarray] = {}
        last_by_name: dict[str, float] = {}
        for c in sorted(cues, key=lambda c: c["t"]):
            name = c["name"]
            if name in ("tick-roll",) and c["t"] - last_by_name.get(name, -9) < 1.3:
                continue
            if c["t"] - last_by_name.get(name, -9) < 0.12:     # never stack the same sound
                continue
            last_by_name[name] = c["t"]
            try:
                snd = cache.setdefault(name, S.make(name))
            except KeyError:
                warn(f"unknown sound effect '{name}' skipped")
                continue
            g = 10 ** (c.get("gain", -15.0) / 20.0)
            i = int(max(0, c["t"]) * SR)
            seg = snd[: max(0, len(buf) - i)]
            buf[i:i + len(seg)] += seg * g
        _write(a / "sfx.wav", np.tanh(buf))
        paths["sfx"] = a / "sfx.wav"
    return paths


def mix_audio(proj: Path, total: float, tracks: dict, lufs: float, bed_db: float) -> Path:
    a = proj / "audio"
    voice = a / "narration.wav"
    ins = ["-i", str(voice)]
    graph = ["[0:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=70,acompressor=threshold=-21dB:ratio=2.5:attack=8:release=140:makeup=3,asplit=2[v1][v2]"]
    labels = ["[v2]"]
    n = 1
    if "bed" in tracks:
        ins += ["-i", str(tracks["bed"])]
        graph.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={bed_db}dB[b0]")
        graph.append("[b0][v1]sidechaincompress=threshold=0.035:ratio=9:attack=15:release=420:makeup=1[bd]")
        labels.append("[bd]")
        n += 1
    if "sfx" in tracks:
        ins += ["-i", str(tracks["sfx"])]
        graph.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo[sf]")
        labels.append("[sf]")
        n += 1
    graph.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,atrim=0:{total + 0.3}[m]")
    base = ";".join(graph)
    # pass 1: measure
    r = run(["ffmpeg", "-hide_banner", "-nostats", *ins, "-filter_complex", f"{base};[m]loudnorm=I={lufs}:TP=-1.0:LRA=9:print_format=json[o]",
             "-map", "[o]", "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr or "", re.S)
    if m:
        j = json.loads(m.group(0))
        ln = (f"loudnorm=I={lufs}:TP=-1.0:LRA=9:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
              f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    else:
        ln = f"loudnorm=I={lufs}:TP=-1.0:LRA=9"
    out = a / "mix.wav"
    ffmpeg(*ins, "-filter_complex", f"{base};[m]{ln}[o]", "-map", "[o]", "-ar", "48000", "-c:a", "pcm_s16le", str(out))
    return out


def run_mix(proj: Path, music: bool = True, effects: bool = True, silent_video: Path | None = None, out_name: str = "final.mp4") -> Path:
    prof = load_profile()
    res = read_json(proj / "comp" / "resolved.json")
    concept = read_json(proj / "concept.json", {})
    if not res:
        fail("Nothing built yet", "run `avs build` and `avs render` first")
    total = res["meta"]["duration"]
    if not (proj / "audio" / "narration.wav").exists():
        fail("No narration.wav", "run `avs tts` first")
    sb = read_json(proj / "storyboard.json", {})
    mus = sb.get("music", {}) if isinstance(sb.get("music"), dict) else {}
    if sb.get("music") is False:
        music = False
    if sb.get("sfx") is False:
        effects = False
    tracks = build_tracks(proj, total, concept, music, effects)
    mixw = mix_audio(proj, total, tracks, prof["video"].get("lufs", -14.0), mus.get("level_db", -21.0))
    vid = silent_video or (proj / "out" / "video_silent.mp4")
    if not vid.exists():
        fail(f"{vid} is missing", "run `avs render` first")
    dest = proj / "out" / out_name
    ffmpeg("-i", str(vid), "-i", str(mixw), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total}",
           "-movflags", "+faststart", str(dest))
    ok(f"{dest} ({duration(dest):.1f}s)")
    return dest
