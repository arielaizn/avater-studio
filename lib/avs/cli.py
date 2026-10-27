"""avs: the Avatar Studio command line."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from . import common as C
from .common import (AvsError, HOME, PLUGIN_ROOT, deep_set, fail, have, key, load_profile, ok, project_path, read_json, run, save_profile,
                     say, warn, write_json)

VERSION = "1.0.0"


# ------------------------------------------------------------------ setup
def cmd_setup(a) -> None:
    say(f"Avatar Studio {VERSION}")
    C.ensure_env_file()
    prof = load_profile()
    if not C.PROFILE_PATH.exists():
        save_profile(prof)
    ok(f"config folder: {HOME}")
    py = [m for m in ("numpy", "PIL") if not _importable(m)]
    if py:
        say("Installing Python packages (numpy, Pillow) ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages", "numpy", "Pillow"], check=False)
    rd = PLUGIN_ROOT / "render"
    if have("npm"):
        if not (rd / "node_modules" / "playwright").exists():
            say("Installing the renderer (npm install) ...")
            subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=rd, check=False)
        if not a.skip_browser:
            say("Making sure Chromium is available ...")
            subprocess.run(["npx", "playwright", "install", "chromium"], cwd=rd, check=False)
    else:
        warn("npm is missing", "install Node.js 18+ from https://nodejs.org")
    _install_shim()
    cmd_doctor(a)


def _importable(m: str) -> bool:
    try:
        __import__(m)
        return True
    except ImportError:
        return False


def _install_shim() -> None:
    target = Path.home() / ".local" / "bin"
    try:
        target.mkdir(parents=True, exist_ok=True)
        sh = target / "avs"
        sh.write_text(f'#!/usr/bin/env bash\nexec "{PLUGIN_ROOT / "bin" / "avs"}" "$@"\n', encoding="utf-8")
        sh.chmod(0o755)
        ok(f"command installed: {sh}")
        if str(target) not in os.environ.get("PATH", ""):
            warn(f"{target} is not on your PATH", f'add: export PATH="$HOME/.local/bin:$PATH"')
    except OSError as e:
        warn(f"could not install the avs shim ({e})")


def cmd_doctor(a) -> None:
    bad = 0
    for name, need in (("ffmpeg", True), ("ffprobe", True), ("node", True)):
        if have(name):
            ok(name)
        else:
            warn(f"{name} is missing", {"ffmpeg": "install ffmpeg 5+ (brew install ffmpeg / apt install ffmpeg)", "node": "install Node.js 18+"}.get(name, ""))
            bad += 1
    if have("ffmpeg"):
        enc = run(["ffmpeg", "-hide_banner", "-encoders"], check=False).stdout
        dec = run(["ffmpeg", "-hide_banner", "-decoders"], check=False).stdout
        for e in ("libx264", "libwebp"):
            if e in enc:
                ok(f"ffmpeg has {e}")
            else:
                warn(f"ffmpeg lacks {e}", "install a full ffmpeg build")
                bad += 1
        if "libvpx-vp9" in dec or "libvpx" in dec:
            ok("ffmpeg can decode transparent webm")
        else:
            warn("ffmpeg cannot decode VP9 with alpha (libvpx-vp9)", "install a full ffmpeg build; needed for the HeyGen presenter")
    for m in ("numpy", "PIL"):
        if _importable(m):
            ok(f"python: {m}")
        else:
            warn(f"python package {m} is missing", "run `avs setup`")
            bad += 1
    pw = (PLUGIN_ROOT / "render" / "node_modules" / "playwright").exists() or (have("node") and run(
        ["node", "-e", "require('playwright')"], check=False, cwd=str(PLUGIN_ROOT / "render")).returncode == 0)
    if pw:
        ok("renderer installed")
    else:
        warn("renderer not installed", "run `avs setup`")
        bad += 1
    p = load_profile()
    say("")
    from . import voice as V
    for r in V.readiness(p):
        (ok if r["ready"] else warn)(f"narration {r['provider']}: " + ("ready" if r["ready"] else r["why"]))
    for k, why in C.KEY_NAMES:
        say(f"  {k:<18} {'set' if key(k) else 'not set'}")
    say(f"\nprofile: {C.PROFILE_PATH}\nkeys file: {C.ENV_PATH}")
    if bad:
        raise SystemExit(1)


def cmd_keys(a) -> None:
    C.ensure_env_file()
    if a.action == "set":
        name = a.name.upper()
        if name not in [k for k, _ in C.KEY_NAMES]:
            fail(f"Unknown key {name}", "one of: " + ", ".join(k for k, _ in C.KEY_NAMES))
        val = a.value or getpass.getpass(f"{name} (input hidden): ").strip()
        if not val:
            fail("Empty value")
        C.set_env_key(name, val)
        ok(f"{name} saved to {C.ENV_PATH}")
        return
    C.load_env()
    for k, why in C.KEY_NAMES:
        say(f"{k:<18} {'set' if key(k) else 'NOT SET'}   {why}")
    say(f"\nKeys live in {C.ENV_PATH}. Open that file and paste the values, or run `avs keys set NAME` (hidden prompt).\nNever paste keys into a chat.")


def cmd_check(a) -> None:
    """Live check of every key that is set (cheap read-only calls)."""
    from . import voice as V, avatar as AV, imagegen as IG
    p = load_profile()
    tests = [("CARTESIA_API_KEY", lambda: len(V.cartesia_voices("", False))),
             ("ELEVEN_API_KEY", lambda: len(V.eleven_voices())),
             ("HEYGEN_API_KEY", lambda: len(AV.looks())),
             ("GEMINI_API_KEY", lambda: IG.pick_gemini_model(p))]
    for k, fn in tests:
        if not key(k):
            warn(f"{k} not set")
            continue
        try:
            r = fn()
            ok(f"{k} works ({r})")
        except (AvsError, Exception) as e:  # noqa: BLE001
            warn(f"{k} failed: {str(getattr(e, 'msg', e))[:140]}")


def cmd_profile(a) -> None:
    p = load_profile()
    if a.action == "set":
        for kv in a.pairs:
            if "=" not in kv:
                fail(f"Use key=value, got '{kv}'")
            k, v = kv.split("=", 1)
            deep_set(p, k, C.coerce(v))
        save_profile(p)
        ok("saved")
    elif a.action == "reset":
        save_profile(C.DEFAULT_PROFILE)
        ok("profile reset to defaults")
    say(json.dumps(p, ensure_ascii=False, indent=2))


# -------------------------------------------------------------- projects
def cmd_new(a) -> None:
    prof = load_profile()
    root = Path(prof["projects_root"]).expanduser()
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in a.name.strip()).strip("-").lower() or "video"
    d = Path(a.dir).expanduser() / slug if a.dir else root / slug
    if (d / "project.json").exists():
        fail(f"{d} already exists", "pick another name, or work in it directly")
    for sub in ("audio", "twin", "plates", "assets", "comp", "out"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    v = prof["video"]
    write_json(d / "project.json", {"name": a.name, "created": datetime.now().isoformat(timespec="seconds"), "width": v["width"], "height": v["height"], "fps": v["fps"]})
    (d / "PLAN.md").write_text(f"# {a.name}\n\nTopic:\nAudience / what a stranger must understand:\nMetaphor and world:\nScenes (one line each):\nCost to approve before spending (presenter seconds x $0.12):\n", encoding="utf-8")
    ok(f"project created: {d}")
    say(f"Next: write {d / 'script.txt'}, then `avs concept propose --topic \"...\" --project {d}`")


def _proj(a) -> Path:
    return project_path(getattr(a, "project", None))


def cmd_tts(a) -> None:
    from . import voice as V
    pr = _proj(a)
    tf = Path(a.text_file) if a.text_file else pr / "script.txt"
    text = a.text or (tf.read_text(encoding="utf-8") if tf.exists() else "")
    if not text.strip():
        fail("No script", f"write {pr / 'script.txt'} (paragraphs separated by blank lines)")
    info = V.make_narration(text, pr / "audio", load_profile(), a.provider, a.dry_run, a.language)
    if a.dry_run:
        say(json.dumps(info, ensure_ascii=False, indent=2))
    elif not (pr / "script.txt").exists():
        (pr / "script.txt").write_text(text, encoding="utf-8")


def cmd_twin(a) -> None:
    from . import avatar as AV
    pr = _proj(a)
    out = pr / "twin"
    if a.resume:
        AV.wait_twin(a.resume, out, "twin")
    else:
        audio = a.audio or str(pr / "audio" / "narration.wav")
        if not Path(audio).exists() and not audio.startswith("http"):
            fail("No narration to animate", "run `avs tts` first")
        if not a.dry_run and not a.yes:
            fail("This spends HeyGen credits", "check the cost with --dry-run, get the user's approval, then run again with --yes")
        AV.render_twin(audio, out, "twin", a.aspect, a.res, a.engine, a.dry_run, True)
    if a.dry_run:
        return
    for ext in ("webm", "mp4"):
        f = out / f"twin.{ext}"
        if f.exists():
            AV.prepare(str(f), pr, load_profile()["video"]["fps"], force=True)
            break


def cmd_avatar(a) -> None:
    from . import avatar as AV
    pr = _proj(a)
    if a.never:
        sb = read_json(pr / "storyboard.json", {})
        sb["avatar"] = False
        write_json(pr / "storyboard.json", sb)
        ok("this video will have no presenter")
        return
    src = a.file or load_profile()["avatar"].get("file")
    if not src or not Path(src).exists():
        fail("No presenter clip", "pass --file clip.webm (transparent) or any clip on a plain background, or use `avs twin` with HeyGen")
    AV.prepare(src, pr, load_profile()["video"]["fps"], force=a.force)


def cmd_imagegen(a) -> None:
    from . import imagegen as IG
    IG.run(_proj(a), a.only, a.force, a.parallel, a.placeholders, a.dry_run)


def cmd_build(a) -> None:
    from . import compose
    compose.build(_proj(a), a.placeholders)


def cmd_render(a) -> None:
    from . import render as R
    pr = _proj(a)
    if a.stills:
        for f in R.stills(pr, [float(x) for x in a.stills.split(",")], a.full):
            say(str(f))
        return
    R.render_video(pr, a.draft, a.workers, False, a.start, a.end, a.placeholders)


def cmd_mix(a) -> None:
    from . import mix
    mix.run_mix(_proj(a), not a.no_music, not a.no_sfx)


def cmd_cover(a) -> None:
    from . import cover
    pr = _proj(a)
    made = cover.make_covers(pr, a.formats.split(",") if a.formats else None, a.variants.split(",") if a.variants else None)
    fin = pr / "out" / "final.mp4"
    if fin.exists() and (pr / "out" / "cover.jpg").exists() and not a.no_embed:
        cover.embed(fin, pr / "out" / "cover.jpg")
        ok("cover embedded in final.mp4")
    say(f"{len(made)} covers in {pr / 'out' / 'covers'}")


def cmd_qa(a) -> None:
    from . import qa
    if not qa.run_qa(_proj(a), layout_check=not a.no_layout):
        raise SystemExit(3)


def cmd_finish(a) -> None:
    """render -> mix -> covers -> qa in one go."""
    from . import render as R, mix, cover, qa
    pr = _proj(a)
    R.render_video(pr, False, a.workers, False, None, None, a.placeholders)
    mix.run_mix(pr)
    if load_profile()["covers"].get("enabled", True):
        cover.make_covers(pr)
        cover.embed(pr / "out" / "final.mp4", pr / "out" / "cover.jpg")
    if not qa.run_qa(pr):
        raise SystemExit(3)


def cmd_selftest(a) -> None:
    from . import selftest
    selftest.run(a.keep, a.seconds)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="avs", description="Avatar Studio: unique, studio-grade vertical videos with a digital presenter.")
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def P(name, fn, help_, project=True):
        s = sub.add_parser(name, help=help_)
        if project:
            s.add_argument("--project", "-p", help="project folder or name (default: current folder)")
        s.set_defaults(fn=fn)
        return s

    s = P("setup", cmd_setup, "install dependencies, create config, add the avs command", False); s.add_argument("--skip-browser", action="store_true")
    P("doctor", cmd_doctor, "check the machine and the keys", False)
    s = P("keys", cmd_keys, "show or set API keys", False); s.add_argument("action", nargs="?", default="show", choices=["show", "set"]); s.add_argument("name", nargs="?"); s.add_argument("value", nargs="?")
    P("check", cmd_check, "live-test every key that is set", False)
    s = P("profile", cmd_profile, "show or change defaults", False); s.add_argument("action", nargs="?", default="show", choices=["show", "set", "reset"]); s.add_argument("pairs", nargs="*")

    s = P("voices", None, "list narrator voices", False); s.add_argument("--provider"); s.add_argument("--language"); s.add_argument("--mine", action="store_true")
    from . import voice as V, avatar as AV, concept as CO
    s.set_defaults(fn=V.cmd_voices)
    s = P("voice-clone", V.cmd_clone, "clone your own voice on Cartesia", False); s.add_argument("--clip", required=True); s.add_argument("--name", required=True); s.add_argument("--language", default="he"); s.add_argument("--confirm-own-voice", action="store_true")
    s = P("say-test", V.cmd_say_test, "voice one line to check pronunciation", False); s.add_argument("text"); s.add_argument("--provider"); s.add_argument("--language"); s.add_argument("--out")
    s = P("looks", AV.cmd_looks, "list your HeyGen avatars", False)

    s = P("new", cmd_new, "create a project folder", False); s.add_argument("name"); s.add_argument("--dir")
    s = P("tts", cmd_tts, "voice the script (Cartesia, ElevenLabs only as fallback)"); s.add_argument("--text"); s.add_argument("--text-file"); s.add_argument("--provider", choices=["auto", "cartesia", "elevenlabs", "mock"]); s.add_argument("--language"); s.add_argument("--dry-run", action="store_true")
    s = P("twin", cmd_twin, "render the presenter with HeyGen (spends credits)"); s.add_argument("--audio"); s.add_argument("--aspect", default="9:16"); s.add_argument("--res", default="1080p"); s.add_argument("--engine"); s.add_argument("--dry-run", action="store_true"); s.add_argument("--yes", action="store_true"); s.add_argument("--resume")
    s = P("avatar", cmd_avatar, "prepare a presenter clip you already have"); s.add_argument("--file"); s.add_argument("--force", action="store_true"); s.add_argument("--never", action="store_true", help="make this video without a presenter")
    s = P("concept", CO.cmd_concept, "choose a world that is different from your recent videos")
    s.add_argument("action", choices=["propose", "pick", "check", "commit", "history", "worlds"]); s.add_argument("--topic"); s.add_argument("-n", type=int, default=6); s.add_argument("--seed", type=int); s.add_argument("--avoid")
    s.add_argument("--index", type=int, default=1); s.add_argument("--title", default=""); s.add_argument("--metaphor"); s.add_argument("--hero"); s.add_argument("--extra"); s.add_argument("--force", action="store_true")
    s = P("imagegen", cmd_imagegen, "generate the scene plates"); s.add_argument("--only"); s.add_argument("--force", action="store_true"); s.add_argument("--parallel", type=int, default=3); s.add_argument("--placeholders", action="store_true"); s.add_argument("--dry-run", action="store_true")
    s = P("build", cmd_build, "compile storyboard + audio into the composition"); s.add_argument("--placeholders", action="store_true")
    s = P("render", cmd_render, "render the picture"); s.add_argument("--draft", action="store_true"); s.add_argument("--workers", type=int); s.add_argument("--start", type=float); s.add_argument("--end", type=float); s.add_argument("--stills"); s.add_argument("--full", action="store_true"); s.add_argument("--placeholders", action="store_true")
    s = P("mix", cmd_mix, "voice + music + effects, loudness -14 LUFS, mux"); s.add_argument("--no-music", action="store_true"); s.add_argument("--no-sfx", action="store_true")
    s = P("cover", cmd_cover, "cover photos (default for every video)"); s.add_argument("--formats"); s.add_argument("--variants"); s.add_argument("--no-embed", action="store_true")
    s = P("qa", cmd_qa, "quality gate"); s.add_argument("--no-layout", action="store_true")
    s = P("finish", cmd_finish, "render + mix + covers + qa"); s.add_argument("--workers", type=int); s.add_argument("--placeholders", action="store_true")
    s = P("selftest", cmd_selftest, "render a short test video with stand-ins", False); s.add_argument("--keep", action="store_true"); s.add_argument("--seconds", type=float, default=0)
    try:
        from . import clip
        s = P("clip", clip.cmd_clip, "quick designed clip from a short text"); clip.add_args(s)
    except ImportError:
        pass
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except AvsError as e:
        print(f"[!!] {e.msg}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
