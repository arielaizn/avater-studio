"""Shared helpers: paths, profile, keys, HTTP, ffmpeg.

Standard library only (plus optional numpy/Pillow in the modules that need them).
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ.get("AVS_HOME") or Path.home() / ".avatar-studio")
PROFILE_PATH = HOME / "profile.json"
ENV_PATH = HOME / ".env"
HISTORY_PATH = HOME / "history.json"
CACHE = HOME / "cache"

DEFAULT_PROFILE = {
    "name": "",
    "language": "he",
    "direction": "rtl",
    "avatar": {"provider": "heygen", "look_id": "", "engine": "avatar_v", "file": ""},
    "voice": {
        "provider": "cartesia",          # default narrator
        "fallback": "elevenlabs",        # used only if the default cannot deliver
        "cartesia": {"voice_id": "", "model": "sonic-3.5", "speed": 1.0, "emotion": ""},
        "elevenlabs": {"voice_id": "", "model": "eleven_v3", "speed": 1.0, "stability": 0.5, "similarity": 0.8, "style": 0.3},
        "heygen": {"voice_id": ""},
    },
    "handle": "",
    "cta": "",
    "rules": [],
    "projects_root": str(Path.home() / "avatar-videos"),
    "imagegen": {"provider": "auto", "gemini_model": ""},
    "covers": {"enabled": True, "formats": ["9x16", "3x4", "4x5"], "variants": ["hero", "type"]},
    "video": {"width": 1080, "height": 1920, "fps": 30, "lufs": -14.0},
}


# ----------------------------------------------------------------- messages
def say(msg: str = "") -> None:
    print(msg, flush=True)


def ok(msg: str) -> None:
    print(f"[ok] {msg}", flush=True)


def warn(msg: str, fix: str = "") -> None:
    print(f"[!!] {msg}", flush=True)
    if fix:
        print(f"     fix: {fix}", flush=True)


def fail(msg: str, fix: str = "", code: int = 1):
    print(f"[!!] {msg}", file=sys.stderr, flush=True)
    if fix:
        print(f"     fix: {fix}", file=sys.stderr, flush=True)
    raise SystemExit(code)


class AvsError(Exception):
    """Recoverable error carrying a fix hint (used by provider fallbacks)."""

    def __init__(self, msg: str, fix: str = "", retryable: bool = False):
        super().__init__(msg)
        self.msg, self.fix, self.retryable = msg, fix, retryable


# ------------------------------------------------------------------- files
def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, data) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ------------------------------------------------------------ env and keys
KEY_NAMES = [
    ("CARTESIA_API_KEY", "Narration (default). cartesia.ai -> API keys"),
    ("ELEVEN_API_KEY", "Narration fallback. elevenlabs.io -> Developers -> API keys"),
    ("HEYGEN_API_KEY", "Avatar video. HeyGen -> Settings -> API (API wallet is separate from the plan)"),
    ("GEMINI_API_KEY", "Images for scenes. aistudio.google.com/apikey (billing on for images)"),
]

_env_loaded = False


def load_env() -> None:
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    for p in (ENV_PATH, Path.cwd() / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if v and not os.environ.get(k):
                    os.environ[k] = v


def key(name: str) -> str:
    load_env()
    if name == "ELEVEN_API_KEY":
        return os.environ.get("ELEVEN_API_KEY") or os.environ.get("ELEVENLABS_API_KEY", "")
    if name == "GEMINI_API_KEY":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    return os.environ.get(name, "")


def ensure_env_file() -> Path:
    HOME.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        lines = ["# Avatar Studio keys. This file stays on your computer. Never paste keys into a chat.\n"]
        for k, why in KEY_NAMES:
            lines.append(f"# {why}\n{k}=\n")
        ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
        try:
            os.chmod(ENV_PATH, 0o600)
        except OSError:
            pass
    return ENV_PATH


def set_env_key(name: str, value: str) -> None:
    ensure_env_file()
    lines, done = ENV_PATH.read_text(encoding="utf-8").splitlines(), False
    for i, ln in enumerate(lines):
        if ln.startswith(f"{name}="):
            lines[i], done = f"{name}={value}", True
    if not done:
        lines.append(f"{name}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[name] = value


# ----------------------------------------------------------------- profile
def _merge(base: dict, over: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_profile() -> dict:
    return _merge(DEFAULT_PROFILE, read_json(PROFILE_PATH, {}))


def save_profile(p: dict) -> None:
    write_json(PROFILE_PATH, p)


def coerce(v: str):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v and v[0] in "[{":
        try:
            return json.loads(v)
        except ValueError:
            return v
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def deep_set(d: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


# -------------------------------------------------------------------- http
def http(method: str, url: str, headers: dict | None = None, body=None, raw: bytes | None = None,
         timeout: int = 300, retries: int = 3, want: str = "json"):
    """Tiny HTTP client with retries. want: json | bytes | text | response."""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hdrs = {"User-Agent": "avatar-studio/1.0"}
    hdrs.update(headers or {})
    if body is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
            if want == "response":
                return r
            payload = r.read()
            if want == "bytes":
                return payload
            if want == "text":
                return payload.decode("utf-8", "replace")
            return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:600]
            retryable = e.code in (408, 409, 425, 429, 500, 502, 503, 504)
            last = AvsError(f"HTTP {e.code} from {url.split('?')[0]}: {text}", retryable=retryable)
            if not retryable:
                raise last
            wait = float(e.headers.get("Retry-After") or 2 ** attempt * 2)
            time.sleep(min(wait, 30))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = AvsError(f"No connection to {url.split('/')[2]} ({getattr(e, 'reason', e)})", retryable=True)
            time.sleep(2 ** attempt * 2)
    raise last or AvsError("request failed")


def multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """fields: name->str ; files: name->path. Returns (body, content_type)."""
    b = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, path in files.items():
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        out += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\n'
                f"Content-Type: {mime}\r\n\r\n").encode()
        out += Path(path).read_bytes() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return out, f"multipart/form-data; boundary={b}"


# ------------------------------------------------------------------ ffmpeg
def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: list, check: bool = True, capture: bool = True, **kw) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=capture, text=True, encoding="utf-8", errors="replace", **kw)
    if check and r.returncode != 0:
        tail = (r.stderr or r.stdout or "")[-1200:]
        raise AvsError(f"command failed: {' '.join(str(c) for c in cmd[:6])} ...\n{tail}")
    return r


def ffmpeg(*args, check: bool = True) -> subprocess.CompletedProcess:
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=check)


def duration(path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], check=False)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def probe_stream(path) -> dict:
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate,codec_name,pix_fmt", "-of", "json", str(path)], check=False)
    try:
        return json.loads(r.stdout)["streams"][0]
    except (ValueError, KeyError, IndexError):
        return {}


def project_path(arg: str | None) -> Path:
    """Resolve a project folder: explicit path, or a name under projects_root, or cwd."""
    if arg:
        p = Path(arg).expanduser()
        if (p / "project.json").exists():
            return p.resolve()
        q = Path(load_profile()["projects_root"]).expanduser() / arg
        if (q / "project.json").exists():
            return q.resolve()
        fail(f"No project at {arg}", "run `avs new <name>` first, or pass the project folder path")
    if (Path.cwd() / "project.json").exists():
        return Path.cwd()
    fail("No project selected", "pass the project folder or name, or cd into it")
