# Avatar Studio

Studio-grade vertical videos with a digital presenter, made by your coding agent. A plugin for **Claude Code** and **Codex**.

- **Photoreal worlds, kinetic type.** Every scene is a photographed set with designed Hebrew/Latin typography that lands on the spoken word. The presenter stands in the bottom third and leaves the frame when a scene needs the whole picture.
- **A different world every video.** A constant studio spine (realism, pacing, loudness) with a variable world: material, light, palette, type, captions, transitions and sound. A history engine refuses worlds that are too close to the last ones. No "one anime video, one cartoon video".
- **Cartesia narration by default, ElevenLabs as backup.** One provider voices a whole video, with word-level timing for captions.
- **2.5D depth scenes.** Photographic pieces placed in 3D space and a real perspective camera flying through them. No video model needed.
- **Cover photos by default**: 9:16, 3:4, 4:5, hero and typographic variants, and the cover is embedded in the file.
- **Quality gate:** loudness -14 LUFS, pacing, frozen/black frames, text overflow and overlap with the presenter's face.
- **Fast clips:** `avs clip` turns a short text into a designed clip.

## Install

Requirements: Python 3.9+, Node 18+, ffmpeg (libx264, libwebp, libvpx).

**Claude Code**
```
/plugin marketplace add <owner>/avatar-studio
/plugin install avatar-studio@avatar-studio
```

**Codex**
```
codex plugin marketplace add <owner>/avatar-studio
```
or run `./install.sh codex` to link the skills.

**Either, from a clone**
```
git clone https://github.com/<owner>/avatar-studio && cd avatar-studio && ./install.sh
```
Then, in your agent: *"make me an avatar video about ..."*

## Keys

Put keys in `~/.avatar-studio/.env` (created by `avs setup`):

| Key | Purpose |
|---|---|
| `CARTESIA_API_KEY` | narration (default) |
| `ELEVEN_API_KEY` | narration backup |
| `HEYGEN_API_KEY` | digital presenter (about $0.12 per second, always shown before spending) |
| `GEMINI_API_KEY` | scene plates |

`avs doctor` checks the machine, `avs check` tests the keys.

## The pipeline

setup, plan, script, **concept** (world), **voice**, presenter, storyboard + plates, build, render, mix, **covers**, QA. The skills walk the agent through each step; `avs` does the work.

```
avs new my-video
avs concept propose --topic "..." -p my-video
avs tts -p my-video
avs twin --dry-run -p my-video      # cost first
avs build -p my-video
avs finish -p my-video
```

Try it without any key: `avs selftest` renders a short video with stand-ins.

## Layout
```
skills/        the agent skills (orchestrator + steps)
lib/avs/       the engine (voice, concept, compose, render, mix, cover, qa)
render/        deterministic HTML renderer (Chromium)
data/          worlds and the studio spine
assets/fonts   open-licensed Hebrew + Latin fonts
bin/avs        the command line
```

## License
MIT. Fonts are under the SIL Open Font License.
