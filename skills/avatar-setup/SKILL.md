---
name: avatar-setup
description: First-run and troubleshooting for Avatar Studio: install dependencies, add API keys safely, choose the narrator voice and the digital presenter, test the keys. Use when the user installs the plugin, when `avs doctor` reports problems, or when a key, voice or avatar is missing.
---

# Setup

`avs` is the command line. If it is not on PATH, use `bin/avs` in the plugin folder.

## 1. Install and check
1. `avs setup` installs Python packages, the renderer (npm + Chromium), creates `~/.avatar-studio/`, and adds `avs` to `~/.local/bin`.
2. `avs doctor` must end without `[!!]` lines for ffmpeg, node, python packages and the renderer. Fix each with the printed `fix:` line. ffmpeg must include libx264 and libwebp and be able to decode VP9 with alpha.

## 2. Keys (never in chat)
Keys live in `~/.avatar-studio/.env`. Tell the user to open that file, or run `avs keys set CARTESIA_API_KEY` in their own terminal (hidden prompt). Do not ask them to paste a key into the conversation; if they do, tell them to rotate it.

| Key | Used for | Needed |
|---|---|---|
| `CARTESIA_API_KEY` | narration, **default** | yes |
| `ELEVEN_API_KEY` | narration backup | recommended |
| `HEYGEN_API_KEY` | the digital presenter | only if rendering a twin |
| `GEMINI_API_KEY` | scene plates | recommended (without it the user supplies images, or placeholders are used for previews) |

`avs check` makes one cheap read-only call per key and reports which work.

## 3. Voice
- `avs voices --language he` lists Cartesia voices (add `--mine` for the user's own, clones included). Save one: `avs profile set voice.cartesia.voice_id=<id>`.
- Do the same for the backup: `avs voices --provider elevenlabs`, then `avs profile set voice.elevenlabs.voice_id=<id>`.
- Pronunciation test, free of project: `avs say-test "משפט לבדיקה"`.
- To use the user's own voice: `avs voice-clone --clip sample.wav --name "my voice" --confirm-own-voice`. First ask the user to confirm it is their own voice (or that the owner gave permission). Never clone anyone else.
- Speed and tone: `avs profile set voice.cartesia.speed=1.05`.

## 4. Presenter
- HeyGen: `avs looks` lists avatars; choose with `avs profile set avatar.look_id=<id>`. The avatar should have matting (transparent output); otherwise `avs twin` warns and falls back to an opaque clip.
- Already have a clip? `avs profile set avatar.file=/path/clip.webm`.
- Cost: about $0.12 per second of presenter video, charged by HeyGen. Always run `avs twin --dry-run` first.

## 5. Personal defaults
`avs profile set handle=@name cta="..." name="..."`. Rules the user states ("never use red", "always end with the logo line") go in `rules` and you apply them to every video: `avs profile set rules='["..."]'`.

## Providers: the policy
Cartesia first, always. ElevenLabs is used only if Cartesia cannot deliver the whole script; the whole script is then re-voiced with ElevenLabs (voices are never mixed inside one video) and the tool prints a warning you must pass on to the user. Force a provider with `avs tts --provider elevenlabs` only when the user asks.
