"""Synthesised sound effects and music beds. Nothing is sampled, so there is nothing to license and every bed is
different per video (the seed picks key, mode and pattern)."""
from __future__ import annotations

import numpy as np

SR = 44100


def _t(d):
    return np.arange(int(d * SR)) / SR


def _env(n, a=0.005, d=0.1, s=0.0, r=0.05):
    e = np.ones(n, dtype=np.float32)
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nd and s < 1:
        seg = e[na:na + nd]
        e[na:na + len(seg)] = np.linspace(1, s, len(seg)) if s else np.exp(-np.linspace(0, 6, len(seg)))
        e[na + len(seg):] = s
    if nr:
        e[-nr:] *= np.linspace(1, 0, min(nr, n))
    return e


def _noise(d, seed=1):
    return np.random.default_rng(seed).standard_normal(int(d * SR)).astype(np.float32)


def _bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / max(hi, 1)) ** 4)
    return np.fft.irfft(X * m, len(x)).astype(np.float32)


def _sweep(d, f0, f1, width=0.5, seed=1):
    """Noise whose band centre glides f0 -> f1."""
    n = int(d * SR)
    x = _noise(d, seed)
    out = np.zeros(n, dtype=np.float32)
    frame, hop = 2048, 1024
    win = np.hanning(frame).astype(np.float32)
    for s in range(0, n - frame, hop):
        u = s / max(n, 1)
        c = f0 * (f1 / f0) ** u
        seg = x[s:s + frame] * win
        out[s:s + frame] += _bandpass(seg, c * (1 - width), c * (1 + width))
    return out / (np.abs(out).max() + 1e-6)


def _norm(x, peak=0.9):
    return (x / (np.abs(x).max() + 1e-9) * peak).astype(np.float32)


def make(name: str) -> np.ndarray:
    if name == "whoosh":
        d = 0.55
        x = _sweep(d, 500, 4200, 0.7, 3) * np.sin(np.pi * np.clip(_t(d) / d, 0, 1)) ** 1.5
        return _norm(x, 0.8)
    if name == "swish":
        d = 0.28
        x = _sweep(d, 1800, 5200, 0.6, 4) * np.sin(np.pi * np.clip(_t(d) / d, 0, 1))
        return _norm(x, 0.55)
    if name == "whoosh-deep":
        d = 0.6
        t = _t(d)
        x = _sweep(d, 120, 1400, 0.8, 5) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.3 + 0.4 * np.sin(2 * np.pi * (90 - 50 * t / d) * t) * _env(len(t), 0.02, 0.5, 0.0, 0.1)
        return _norm(x, 0.85)
    if name == "riser":
        d = 0.8
        t = _t(d)
        x = _sweep(d, 300, 6000, 0.7, 6) * (t / d) ** 2 + 0.25 * np.sin(2 * np.pi * (180 + 700 * (t / d) ** 2) * t) * (t / d)
        return _norm(x * _env(len(t), 0.01, 0, 1, 0.04), 0.7)
    if name in ("impact", "hit"):
        d = 0.9 if name == "impact" else 0.3
        t = _t(d)
        body = np.sin(2 * np.pi * (46 + 70 * np.exp(-t * 22)) * t) * np.exp(-t * (5 if name == "impact" else 14))
        click = _bandpass(_noise(0.06, 9), 1200, 7000) * np.exp(-_t(0.06) * 90)
        x = body.copy()
        x[:len(click)] += click * 0.8
        if name == "impact":
            x += _bandpass(_noise(d, 8), 80, 600) * np.exp(-t * 6) * 0.5
        return _norm(x, 0.9)
    if name == "stamp":
        d = 0.35
        t = _t(d)
        x = np.sin(2 * np.pi * (95 - 40 * np.minimum(t * 8, 1)) * t) * np.exp(-t * 22)
        c = _bandpass(_noise(0.04, 2), 800, 5000) * np.exp(-_t(0.04) * 120)
        x[:len(c)] += c * 0.9
        return _norm(x, 0.85)
    if name == "pop":
        d = 0.14
        t = _t(d)
        x = np.sin(2 * np.pi * (900 * np.exp(-t * 18) + 220) * t) * np.exp(-t * 32)
        return _norm(x, 0.7)
    if name == "paper":
        d = 0.4
        x = _bandpass(_noise(d, 11), 2500, 9000) * (np.abs(_noise(d, 12)) ** 0.5) * np.sin(np.pi * np.clip(_t(d) / d, 0, 1))
        return _norm(x, 0.55)
    if name == "shutter":
        out = np.zeros(int(0.22 * SR), dtype=np.float32)
        for off, s in ((0.0, 3), (0.07, 4)):
            c = _bandpass(_noise(0.05, s), 1500, 9000) * np.exp(-_t(0.05) * 70)
            i = int(off * SR)
            out[i:i + len(c)] += c
        return _norm(out, 0.7)
    if name == "glitch":
        d = 0.28
        n = int(d * SR)
        r = np.random.default_rng(5)
        x = np.zeros(n, dtype=np.float32)
        i = 0
        while i < n:
            L = int(r.uniform(0.01, 0.04) * SR)
            f = r.uniform(300, 6000)
            seg = np.sign(np.sin(2 * np.pi * f * np.arange(L) / SR)) * r.uniform(0.3, 1.0)
            x[i:i + L] = seg[: n - i]
            i += L + int(r.uniform(0, 0.02) * SR)
        return _norm(_bandpass(x, 200, 9000) * _env(n, 0.001, 0, 1, 0.05), 0.5)
    if name == "scribble":
        d = 0.4
        n = int(d * SR)
        r = np.random.default_rng(7)
        am = np.repeat(r.uniform(0.2, 1, int(d * 38)), n // int(d * 38) + 1)[:n]
        x = _bandpass(_noise(d, 13), 2500, 8000) * am * _env(n, 0.01, 0, 1, 0.08)
        return _norm(x, 0.45)
    if name in ("tick", "tick-roll"):
        click = lambda: _bandpass(_noise(0.02, 21), 1800, 9000) * np.exp(-_t(0.02) * 160)
        if name == "tick":
            return _norm(click(), 0.6)
        out = np.zeros(int(1.15 * SR), dtype=np.float32)
        t = 0.0
        gap = 0.11
        while t < 1.05:
            c = click()
            i = int(t * SR)
            out[i:i + len(c)] += c
            t += gap
            gap = max(0.035, gap * 0.9)
        return _norm(out, 0.5)
    raise KeyError(name)


NAMES = ["whoosh", "swish", "whoosh-deep", "riser", "impact", "hit", "stamp", "pop", "paper", "shutter", "glitch", "scribble", "tick", "tick-roll"]


# ---------------------------------------------------------------- music beds
def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def _note(buf, t0, dur, f, amp, kind="sine", harm=6, decay=None):
    i = int(t0 * SR)
    if i >= len(buf):
        return
    n = min(int(dur * SR), len(buf) - i)
    if n <= 0:
        return
    t = np.arange(n) / SR
    if kind == "pad":
        x = sum((1 / k) * np.sin(2 * np.pi * f * k * (1 + 0.0012 * (j - 1)) * t + j) for k in range(1, harm) for j in range(3)) / 3
        e = _env(n, 0.8, 0, 1, 1.2)
    elif kind == "pluck":
        x = sum((1 / k ** 1.3) * np.sin(2 * np.pi * f * k * t) for k in range(1, harm))
        e = np.exp(-t * (decay or 5.0)) * np.minimum(t * 300, 1)
    elif kind == "bell":
        x = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) + 0.25 * np.sin(2 * np.pi * f * 5.4 * t)
        e = np.exp(-t * (decay or 3.0)) * np.minimum(t * 500, 1)
    elif kind == "sub":
        x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t)
        e = _env(n, 0.05, 0, 1, 0.4)
    else:
        x = np.sin(2 * np.pi * f * t)
        e = _env(n, 0.02, 0, 1, 0.1)
    buf[i:i + n] += (x * e * amp).astype(np.float32)


MODES = {"minor": [0, 2, 3, 5, 7, 8, 10], "major": [0, 2, 4, 5, 7, 9, 11], "dorian": [0, 2, 3, 5, 7, 9, 10], "lydian": [0, 2, 4, 6, 7, 9, 11], "phrygian": [0, 1, 3, 5, 7, 8, 10]}


def bed(kind: str, seconds: float, seed: int = 1) -> np.ndarray:
    r = np.random.default_rng(seed)
    n = int((seconds + 2) * SR)
    buf = np.zeros(n, dtype=np.float32)
    root = int(r.integers(43, 55))
    mode = {"warm-pad": "dorian", "tense-pulse": "phrygian", "airy-drone": "lydian", "soft-lofi": "minor", "minimal-clicks": "minor",
            "bright-arp": "major", "deep-sub": "phrygian", "music-box": "major"}.get(kind, "minor")
    sc = MODES[mode]
    prog = [0, 5, 3, 4] if r.random() < 0.5 else [0, 3, 5, 4]

    def deg(d, octave=0):
        return root + 12 * octave + sc[d % 7] + 12 * (d // 7)

    if kind == "warm-pad":
        bar = 8.0
        for b in range(int(seconds / bar) + 2):
            d = prog[b % 4]
            for k, off in enumerate((0, 2, 4)):
                _note(buf, b * bar, bar + 1.6, midi(deg(d + off, 1)), 0.11, "pad")
            _note(buf, b * bar, bar + 0.5, midi(deg(d, 0) - 12 + 12), 0.14, "sub")
    elif kind == "airy-drone":
        for k, (off, amp) in enumerate(((0, 0.16), (7, 0.1), (12, 0.1), (16, 0.05))):
            _note(buf, 0, seconds + 2, midi(root + 12 + off), amp, "pad", 4)
        buf += (_bandpass(_noise(seconds + 2, seed), 300, 2400) * 0.03 * (0.6 + 0.4 * np.sin(np.arange(n) / SR * 0.2))).astype(np.float32)[:n]
    elif kind == "tense-pulse":
        step = 60 / 92 / 2
        for i in range(int(seconds / step) + 2):
            _note(buf, i * step, step * 0.9, midi(root - 12 + (1 if (i // 16) % 2 else 0)), 0.2 if i % 4 == 0 else 0.1, "pluck", 5, 12)
        _note(buf, 0, seconds + 2, midi(root + 12), 0.05, "pad", 3)
        _note(buf, 0, seconds + 2, midi(root + 13), 0.04, "pad", 3)
    elif kind == "deep-sub":
        _note(buf, 0, seconds + 2, midi(root - 12), 0.28, "sub")
        for i in range(int(seconds / 1.0) + 2):
            _note(buf, i * 1.0, 0.4, 52 - 8 * (i % 2), 0.4 if i % 2 == 0 else 0.25, "pluck", 2, 9)
        _note(buf, 0, seconds + 2, midi(root + 12), 0.05, "pad", 4)
    elif kind == "soft-lofi":
        beat = 60 / 78
        for b in range(int(seconds / (beat * 4)) + 2):
            d = prog[b % 4]
            for off in (0, 2, 4, 6):
                _note(buf, b * beat * 4 + (0.0 if off != 6 else beat * 1.5), beat * 3, midi(deg(d + off, 1)), 0.07, "pluck", 4, 2.2)
            _note(buf, b * beat * 4, beat * 2, midi(deg(d, -1) + 12 - 12), 0.18, "sub")
        for i in range(int(seconds / beat) + 2):
            _note(buf, i * beat, 0.12, 60, 0.30 if i % 2 == 0 else 0.0, "pluck", 2, 28)
            if i % 2 == 1:
                c = _bandpass(_noise(0.05, i), 5000, 12000) * np.exp(-_t(0.05) * 60) * 0.1
                j = int((i * beat) * SR)
                buf[j:j + len(c)] += c[: max(0, min(len(c), n - j))]
        buf += (_noise(seconds + 2, 99)[:n] * 0.004).astype(np.float32)
    elif kind == "minimal-clicks":
        beat = 60 / 100
        for i in range(int(seconds / (beat / 2)) + 2):
            if r.random() < 0.55:
                c = _bandpass(_noise(0.02, i), 2500, 9000) * np.exp(-_t(0.02) * 140) * r.uniform(0.05, 0.14)
                j = int(i * beat / 2 * SR)
                buf[j:j + len(c)] += c[: max(0, min(len(c), n - j))]
        for b in range(int(seconds / (beat * 4)) + 2):
            _note(buf, b * beat * 4, beat * 3.5, midi(deg(prog[b % 4], 0)), 0.2, "sub")
    elif kind == "bright-arp":
        step = 60 / 112 / 2
        pat = [0, 2, 4, 2, 5, 4, 2, 4]
        for i in range(int(seconds / step) + 2):
            d = prog[(i // 16) % 4]
            _note(buf, i * step, step * 1.6, midi(deg(d + pat[i % 8], 2)), 0.07, "pluck", 4, 7)
        for b in range(int(seconds / (step * 16)) + 2):
            _note(buf, b * step * 16, step * 16, midi(deg(prog[b % 4], 0)), 0.2, "sub")
    elif kind == "music-box":
        beat = 60 / 84
        pat = [0, 2, 4, 7, 4, 2]
        for i in range(int(seconds / beat) + 2):
            d = prog[(i // 12) % 4]
            _note(buf, i * beat, 1.6, midi(deg(d + pat[i % 6], 2)), 0.09, "bell", 3, 2.8)
        _note(buf, 0, seconds + 2, midi(root), 0.1, "pad", 3)
    else:
        raise KeyError(kind)
    buf = np.tanh(buf * 1.4) * 0.8
    return buf[: int((seconds + 2) * SR)]
