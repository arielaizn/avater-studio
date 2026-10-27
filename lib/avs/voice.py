"""Narration. Cartesia is the default voice; ElevenLabs is the automatic fallback.

Policy (deliberate, so a video never mixes two voices):
  * The whole script is voiced by ONE provider.
  * Cartesia first. If its key or voice is missing, the language is unsupported, or any paragraph still fails after
    retries, the whole script is re-voiced with ElevenLabs.
  * The provider used is written to audio/tts_log.json and printed, so the agent can tell the user.
"""
from __future__ import annotations

import base64
import io
import json
import math
import re
import wave
import zlib
from pathlib import Path

import numpy as np

from . import align as A
from .common import (AvsError, fail, ffmpeg, http, key, load_profile, multipart, ok, say, warn, write_json,
                     HOME, ensure_env_file, save_profile, deep_set)

SR = 44100
CARTESIA = "https://api.cartesia.ai"
CARTESIA_VERSION = "2026-03-01"
ELEVEN = "https://api.elevenlabs.io"

# Words per second of natural speech, used for estimates before any audio exists.
WPS = {"he": 2.45, "en": 2.7, "default": 2.5}


# ------------------------------------------------------------------ helpers
def paragraphs(text: str) -> list[str]:
    parts = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", text.strip())]
    return [p for p in parts if p]


def estimate_seconds(text: str, lang: str = "he", speed: float = 1.0) -> float:
    n = len(A.tokenize(text))
    paras = len(paragraphs(text))
    return n / (WPS.get(lang, WPS["default"]) * speed) + max(0, paras - 1) * 0.35 + 1.0


def _pcm_to_np(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


def _np_to_pcm(x: np.ndarray) -> bytes:
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


def write_wav(path, x: np.ndarray, sr: int = SR) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(_np_to_pcm(x))


def trim_silence(x: np.ndarray, lead_keep: float = 0.05, tail_keep: float = 0.12, thresh_db: float = -46.0):
    """Trim leading/trailing silence. Returns (audio, seconds_removed_from_start)."""
    win = int(SR * 0.01)
    n = len(x) // win
    if n == 0:
        return x, 0.0
    rms = np.sqrt((x[: n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    loud = np.where(db > thresh_db)[0]
    if len(loud) == 0:
        return x, 0.0
    a = max(0, int((loud[0] * 0.01 - lead_keep) * SR))
    b = min(len(x), int(((loud[-1] + 1) * 0.01 + tail_keep) * SR))
    return x[a:b], a / SR


# ---------------------------------------------------------------- Cartesia
def cartesia_ready(p: dict) -> tuple[bool, str]:
    if not key("CARTESIA_API_KEY"):
        return False, "CARTESIA_API_KEY is not set"
    if not p["voice"]["cartesia"].get("voice_id"):
        return False, "no Cartesia voice chosen (avs voices --provider cartesia)"
    return True, ""


def _cartesia_headers() -> dict:
    k = key("CARTESIA_API_KEY")
    return {"Authorization": f"Bearer {k}", "X-API-Key": k, "Cartesia-Version": CARTESIA_VERSION}


def _cartesia_body(text: str, p: dict, lang: str) -> dict:
    c = p["voice"]["cartesia"]
    model = c.get("model") or "sonic-3.5"
    body = {
        "model_id": model,
        "transcript": text,
        "voice": {"mode": "id", "id": c["voice_id"]},
    }
    # Sonic 3.6+/latest take `locale`; earlier Sonic 3 takes `language`.
    if model.startswith("sonic-3.6") or model == "sonic-latest":
        body["locale"] = lang
    else:
        body["language"] = lang
    gc = {}
    if c.get("speed") and float(c["speed"]) != 1.0:
        gc["speed"] = max(0.6, min(1.5, float(c["speed"])))
    if c.get("emotion"):
        gc["emotion"] = c["emotion"]
    if gc:
        body["generation_config"] = gc
    return body


def cartesia_synth(text: str, p: dict, lang: str) -> tuple[np.ndarray, list[dict] | None]:
    body = _cartesia_body(text, p, lang)
    # 1) SSE: audio + word timestamps in one call
    try:
        sse = dict(body, add_timestamps=True,
                   output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": SR})
        r = http("POST", f"{CARTESIA}/tts/sse", _cartesia_headers(), sse, want="response", timeout=180)
        pcm, words = bytearray(), []
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:].strip() or "{}")
            t = ev.get("type")
            if t == "chunk" and ev.get("data"):
                pcm += base64.b64decode(ev["data"])
            elif t == "timestamps":
                wt = ev.get("word_timestamps") or {}
                for w, s, e in zip(wt.get("words", []), wt.get("start", []), wt.get("end", [])):
                    words.append({"w": w, "start": float(s), "end": float(e)})
            elif t == "error":
                raise AvsError(f"Cartesia: {ev.get('message') or ev.get('title')}", retryable=False)
        if len(pcm) > SR // 10:
            return _pcm_to_np(bytes(pcm)), (words or None)
    except AvsError as e:
        if "HTTP 4" in str(e) and "HTTP 429" not in str(e) and "HTTP 408" not in str(e):
            raise
    # 2) plain bytes endpoint (no timestamps)
    bb = dict(body, output_format={"container": "wav", "encoding": "pcm_s16le", "sample_rate": SR})
    data = http("POST", f"{CARTESIA}/tts/bytes", _cartesia_headers(), bb, want="bytes", timeout=180)
    with wave.open(io.BytesIO(data)) as w:
        return _pcm_to_np(w.readframes(w.getnframes())), None


def cartesia_voices(language: str = "", mine: bool = False) -> list[dict]:
    q = "limit=100" + (f"&language={language}" if language else "") + ("&is_owner=true" if mine else "")
    j = http("GET", f"{CARTESIA}/voices?{q}", _cartesia_headers(), want="json")
    items = j if isinstance(j, list) else (j.get("data") or j.get("voices") or [])
    return [{"id": v.get("id"), "name": v.get("name"), "language": v.get("language"),
             "description": (v.get("description") or "")[:80]} for v in items]


def cartesia_clone(clip: str, name: str, language: str) -> dict:
    body, ctype = multipart({"name": name, "language": language, "tagline": "Avatar Studio"}, {"clip": clip})
    h = _cartesia_headers()
    h["Content-Type"] = ctype
    return http("POST", f"{CARTESIA}/voices/clone", h, raw=body, timeout=300)


# -------------------------------------------------------------- ElevenLabs
def eleven_ready(p: dict) -> tuple[bool, str]:
    if not key("ELEVEN_API_KEY"):
        return False, "ELEVEN_API_KEY is not set"
    if not p["voice"]["elevenlabs"].get("voice_id"):
        return False, "no ElevenLabs voice chosen (avs voices --provider elevenlabs)"
    return True, ""


def eleven_synth(text: str, p: dict, lang: str) -> tuple[np.ndarray, list[dict] | None]:
    e = p["voice"]["elevenlabs"]
    vid = e["voice_id"]
    h = {"xi-api-key": key("ELEVEN_API_KEY")}
    settings = {"stability": e.get("stability", 0.5), "similarity_boost": e.get("similarity", 0.8),
                "style": e.get("style", 0.3), "use_speaker_boost": True}
    if e.get("speed") and float(e["speed"]) != 1.0:
        settings["speed"] = max(0.7, min(1.2, float(e["speed"])))
    body = {"text": text, "model_id": e.get("model") or "eleven_v3", "voice_settings": settings}
    words = None
    mp3 = None
    try:
        j = http("POST", f"{ELEVEN}/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128", h, body, timeout=240)
        mp3 = base64.b64decode(j["audio_base64"])
        al = j.get("alignment") or j.get("normalized_alignment")
        if al:
            words = A.chars_to_words(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])
    except (AvsError, KeyError) as ex:
        if isinstance(ex, AvsError) and ex.retryable:
            raise
    if mp3 is None:
        mp3 = http("POST", f"{ELEVEN}/v1/text-to-speech/{vid}?output_format=mp3_44100_128", h, body, want="bytes", timeout=240)
    tmp = HOME / "cache" / "el_tmp.mp3"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(mp3)
    out = tmp.with_suffix(".wav")
    ffmpeg("-i", str(tmp), "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(out))
    with wave.open(str(out)) as w:
        x = _pcm_to_np(w.readframes(w.getnframes()))
    return x, words


def eleven_voices() -> list[dict]:
    j = http("GET", f"{ELEVEN}/v1/voices", {"xi-api-key": key("ELEVEN_API_KEY")})
    return [{"id": v["voice_id"], "name": v.get("name"), "category": v.get("category"),
             "labels": ",".join(f"{k}={x}" for k, x in (v.get("labels") or {}).items())[:80]} for v in j.get("voices", [])]


# -------------------------------------------------------------------- mock
def mock_synth(text: str, p: dict, lang: str) -> tuple[np.ndarray, list[dict]]:
    """Offline stand-in: speech-shaped babble with exact word times. For tests and demos only."""
    rng = np.random.default_rng(zlib.crc32(text.encode('utf-8')))
    toks = A.tokenize(text)
    out, words, t = [np.zeros(int(0.1 * SR), dtype=np.float32)], [], 0.1
    for tok in toks:
        d = 0.09 + 0.055 * len(A.norm(tok))
        n = int(d * SR)
        tt = np.arange(n) / SR
        f0 = 110 + rng.uniform(-15, 25)
        env = np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 0.7
        sig = sum(np.sin(2 * np.pi * f0 * k * tt + k) / k for k in range(1, 9))
        form = 0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(3, 6) * tt)
        w = (sig * env * form * 0.18).astype(np.float32)
        out.append(w)
        words.append({"w": tok, "start": t, "end": t + d})
        t += d
        gap = 0.04 + (0.28 if tok[-1:] in ",.;:!?" else 0.0)
        out.append(np.zeros(int(gap * SR), dtype=np.float32))
        t += gap
    return np.concatenate(out), words


# ------------------------------------------------------------------- chain
PROVIDERS = {
    "cartesia": (cartesia_ready, cartesia_synth),
    "elevenlabs": (eleven_ready, eleven_synth),
    "mock": (lambda p: (True, ""), mock_synth),
}


def chain(p: dict, forced: str | None = None) -> list[str]:
    if forced and forced != "auto":
        return [forced]
    v = p["voice"]
    order = [v.get("provider") or "cartesia", v.get("fallback") or "elevenlabs"]
    seen, out = set(), []
    for x in order:
        if x in PROVIDERS and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def readiness(p: dict, forced: str | None = None) -> list[dict]:
    res = []
    for name in chain(p, forced):
        okk, why = PROVIDERS[name][0](p)
        res.append({"provider": name, "ready": okk, "why": why})
    return res


def synth_script(text: str, p: dict, provider: str, lang: str, gap: float = 0.38, lead: float = 0.12, tail: float = 0.9):
    """Voice every paragraph with ONE provider. Returns (audio, words, paragraphs_meta)."""
    synth = PROVIDERS[provider][1]
    chunks, words_all, meta = [np.zeros(int(lead * SR), dtype=np.float32)], [], []
    t = lead
    for i, para in enumerate(paragraphs(text)):
        x, heard = None, None
        for attempt in range(3):
            try:
                x, heard = synth(para, p, lang)
                break
            except AvsError as e:
                if attempt == 2 or not e.retryable:
                    raise
        x, cut = trim_silence(x)
        if heard:
            for h in heard:
                h["start"] = max(0.0, h["start"] - cut)
                h["end"] = max(h["start"] + 0.03, h["end"] - cut)
        dur = len(x) / SR
        toks = A.tokenize(para)
        if not heard and provider != "mock":
            tmp = HOME / "cache" / "para_tmp.wav"
            write_wav(tmp, x)
            heard = A.whisper_words(str(tmp), lang)   # optional; None when faster-whisper is not installed
        ws = A.align(toks, heard, 0.0, dur)
        for k, w in enumerate(ws):
            w["start"] = round(w["start"] + t, 3)
            w["end"] = round(w["end"] + t, 3)
            w["para"] = i
        words_all += ws
        meta.append({"i": i, "text": para, "start": round(t, 3), "end": round(t + dur, 3), "timing": "provider" if heard else "estimated"})
        chunks.append(x)
        t += dur
        chunks.append(np.zeros(int(gap * SR), dtype=np.float32))
        t += gap
    chunks.append(np.zeros(int(tail * SR), dtype=np.float32))
    audio = np.concatenate(chunks)
    return audio, words_all, meta


def make_narration(text: str, out_dir: Path, p: dict | None = None, forced: str | None = None,
                   dry_run: bool = False, lang: str | None = None) -> dict:
    p = p or load_profile()
    lang = lang or p.get("language", "he")
    rd = readiness(p, forced)
    est = estimate_seconds(text, lang, float(p["voice"].get("cartesia", {}).get("speed", 1.0) or 1.0))
    info = {"chain": rd, "estimated_seconds": round(est, 1), "words": len(A.tokenize(text)),
            "paragraphs": len(paragraphs(text)), "chars": len(text)}
    if dry_run:
        return info
    usable = [r["provider"] for r in rd if r["ready"]]
    if not usable:
        why = "; ".join(f"{r['provider']}: {r['why']}" for r in rd)
        fail(f"No narration provider is ready ({why})", "run `avs keys` to add a key, then `avs voices` to pick a voice")
    log, used = [], None
    for name in usable:
        try:
            say(f"  voicing with {name} ...")
            audio, words, meta = synth_script(text, p, name, lang)
            used = name
            break
        except AvsError as e:
            warn(f"{name} could not voice the script: {e.msg.splitlines()[0]}")
            log.append({"provider": name, "error": e.msg[:400]})
    if used is None:
        fail("Every narration provider failed", "see audio/tts_log.json; check keys, credits and voice ids with `avs check`")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_wav(out_dir / "narration.wav", audio)
    write_json(out_dir / "words.json", words)
    primary = chain(p, forced)[0]
    timing = {"total": round(len(audio) / SR, 3), "paragraphs": meta, "provider": used,
              "fallback_used": used != primary, "language": lang}
    write_json(out_dir / "timing.json", timing)
    write_json(out_dir / "tts_log.json", {"used": used, "primary": primary, "failures": log,
                                           "model": (p["voice"].get(used) or {}).get("model"),
                                           "voice_id": (p["voice"].get(used) or {}).get("voice_id")})
    if used != primary:
        warn(f"Fallback used: narrated with {used} because {primary} could not deliver. Tell the user.")
    ok(f"narration.wav {timing['total']}s via {used}, {len(words)} words")
    return timing


# --------------------------------------------------------------------- cli
def cmd_voices(args) -> None:
    p = load_profile()
    prov = args.provider or p["voice"]["provider"]
    if prov == "cartesia":
        if not key("CARTESIA_API_KEY"):
            fail("CARTESIA_API_KEY is not set", "run `avs keys`")
        rows = cartesia_voices(args.language or "", args.mine)
        if not rows and args.language:
            rows = cartesia_voices("", args.mine)
    elif prov == "elevenlabs":
        if not key("ELEVEN_API_KEY"):
            fail("ELEVEN_API_KEY is not set", "run `avs keys`")
        rows = eleven_voices()
    else:
        fail(f"Unknown provider {prov}")
    for r in rows:
        say(" | ".join(str(v) for v in r.values()))
    say(f"\n{len(rows)} voices. Save one with: avs profile set voice.{prov}.voice_id=<id>")


def cmd_clone(args) -> None:
    if not args.confirm_own_voice:
        fail("Voice cloning needs --confirm-own-voice",
             "only clone your own voice, or a voice whose owner gave you explicit permission. Ask the user to confirm first.")
    if not key("CARTESIA_API_KEY"):
        fail("CARTESIA_API_KEY is not set", "run `avs keys`")
    j = cartesia_clone(args.clip, args.name, args.language)
    vid = j.get("id")
    ok(f"Cloned voice '{args.name}' id={vid}")
    p = load_profile()
    deep_set(p, "voice.cartesia.voice_id", vid)
    save_profile(p)
    ok("Saved as your default Cartesia voice")


def cmd_tts(args) -> None:
    p = load_profile()
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    if not text:
        fail("No script given", "use --text-file script.txt")
    info = make_narration(text, Path(args.out), p, args.provider, args.dry_run, args.language)
    if args.dry_run:
        say(json.dumps(info, ensure_ascii=False, indent=2))


def cmd_say_test(args) -> None:
    """A short pronunciation test: one line, one provider, no project."""
    p = load_profile()
    out = Path(args.out or (HOME / "cache"))
    make_narration(args.text, out, p, args.provider, False, args.language)
    say(f"Listen to: {out / 'narration.wav'}")
