"""Word timing: map the script's own words onto times heard in the audio.

Sources, best first: provider timestamps (Cartesia / ElevenLabs) -> faster-whisper (optional) -> estimate.
The captions always use the SCRIPT's spelling, only the times come from the audio.
"""
from __future__ import annotations

import difflib
import re

_NIKUD = re.compile(r"[֑-ׇ]")
_PUNCT = re.compile(r"[^\w֐-׿]+", re.UNICODE)
_PAUSE_CHARS = {",": 0.35, ";": 0.45, ":": 0.45, ".": 0.7, "!": 0.7, "?": 0.7, "…": 0.7, "—": 0.3, "-": 0.0}


def norm(tok: str) -> str:
    t = _NIKUD.sub("", tok).lower()
    t = t.replace("׳", "").replace("'", "").replace("״", "").replace('"', "")
    return _PUNCT.sub("", t)


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def _weight(tok: str) -> float:
    base = max(1, len(norm(tok)))
    return base + 0.0


def estimate(tokens: list[str], t0: float, t1: float) -> list[dict]:
    """Spread tokens across [t0, t1] by character weight, with extra pause after punctuation."""
    if not tokens:
        return []
    weights, pauses = [], []
    for tok in tokens:
        weights.append(_weight(tok))
        pauses.append(next((v for ch, v in _PAUSE_CHARS.items() if tok.endswith(ch)), 0.0))
    # one char of speech ~ 0.065 s; pauses are real silence inside the span
    span = max(0.01, t1 - t0)
    speech = sum(weights)
    pause_total = sum(pauses)
    # shrink pauses if they would eat more than 30% of the span
    k = min(1.0, 0.30 * span / pause_total) if pause_total else 1.0
    unit = (span - pause_total * k) / speech
    out, t = [], t0
    for tok, w, p in zip(tokens, weights, pauses):
        d = w * unit
        out.append({"w": tok, "start": round(t, 3), "end": round(t + d, 3)})
        t += d + p * k
    return out


def align(script_tokens: list[str], heard: list[dict] | None, t0: float, t1: float) -> list[dict]:
    """heard: [{w, start, end}] from a provider or from whisper. Returns one entry per script token."""
    if not script_tokens:
        return []
    if not heard:
        return estimate(script_tokens, t0, t1)
    a = [norm(t) for t in script_tokens]
    b = [norm(h["w"]) for h in heard]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times: list[tuple[float, float] | None] = [None] * len(script_tokens)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
        elif tag == "replace":
            # different counts: spread script tokens over the heard span
            hs, he = heard[j1]["start"], heard[j2 - 1]["end"]
            seg = estimate(script_tokens[i1:i2], hs, he)
            for k, s in enumerate(seg):
                times[i1 + k] = (s["start"], s["end"])
    # fill the gaps (script tokens nobody heard) between known neighbours
    i = 0
    n = len(times)
    while i < n:
        if times[i] is None:
            j = i
            while j < n and times[j] is None:
                j += 1
            left = times[i - 1][1] if i > 0 else t0
            right = times[j][0] if j < n else t1
            right = max(right, left + 0.05 * (j - i))
            seg = estimate(script_tokens[i:j], left, right)
            for k, s in enumerate(seg):
                times[i + k] = (s["start"], s["end"])
            i = j
        else:
            i += 1
    out = []
    prev_end = t0
    for tok, (s, e) in zip(script_tokens, times):
        s = max(s, prev_end - 0.02)           # keep monotonic
        e = max(e, s + 0.04)
        out.append({"w": tok, "start": round(s, 3), "end": round(e, 3)})
        prev_end = e
    return out


def whisper_words(wav_path: str, lang: str = "he") -> list[dict] | None:
    """Optional: word times from faster-whisper if installed. Returns None when unavailable."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return None
    try:
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segs, _ = model.transcribe(wav_path, language=lang, word_timestamps=True, vad_filter=False)
        words = []
        for s in segs:
            for w in s.words or []:
                words.append({"w": w.word.strip(), "start": float(w.start), "end": float(w.end)})
        return words or None
    except Exception:
        return None


def chars_to_words(chars: list[str], starts: list[float], ends: list[float]) -> list[dict]:
    """ElevenLabs character alignment -> word list."""
    words, cur, s0, e0 = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "start": s0, "end": e0})
            cur, s0, e0 = "", None, None
            continue
        if s0 is None:
            s0 = s
        cur += ch
        e0 = e
    if cur:
        words.append({"w": cur, "start": s0, "end": e0})
    return words
