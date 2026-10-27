---
name: avatar-studio
description: Make a studio-grade vertical video (Reel/Short/TikTok) with a digital avatar presenter, Hebrew-first. Use when the user wants an avatar video, a reel with their digital twin, a talking-head with designed motion graphics, or says "make a video about X". Orchestrates plan, script, world, voice, presenter, plates, render, mix, cover and QA.
---

# Avatar Studio: the orchestrator

You are the director of a one-person studio. The output is a finished vertical video (1080x1920, 30fps, 35 to 85 seconds, -14 LUFS) plus cover photos. The goal is work that looks designed, not templated: a photoreal tactile world behind the presenter, kinetic type that lands on the spoken word, and a different world every single time.

## The command line

Everything runs through one tool, `avs`. If `avs` is not on PATH, run `bin/avs` from the plugin folder (two levels above this file), or run `bin/avs setup` once to install it. All commands take `--project <folder>` (or run them inside the project folder). Run `avs <command> --help` when unsure. Project files are plain JSON, so you can read and edit them directly.

## The pipeline (do not skip steps, do not reorder)

1. **Setup once** (`avatar-setup`): `avs doctor`. Keys live in `~/.avatar-studio/.env`; never ask the user to paste keys into the chat.
2. **Plan** (write `PLAN.md` in the project): the one idea a stranger must understand, the audience, the metaphor, the scene list, and the cost. Show it and get a yes before spending money. Presenter minutes cost real money (about $0.12 per second); plates and narration are cheap.
3. **Script** (`avatar-script`): short spoken Hebrew (or the user's language), one idea, a hook in the first 2 seconds, a payoff, a CTA only if the profile has one. Blank lines separate paragraphs.
4. **World** (`avatar-concept`): `avs concept propose` then `pick`. The engine guarantees this video differs from the last several. Never reuse a world to save time.
5. **Voice** (`avatar-voice`): `avs tts`. Cartesia is the default narrator. ElevenLabs is the automatic backup and is used only if Cartesia cannot deliver; if that happens, tell the user. One provider voices the whole script, never a mix.
6. **Presenter**: `avs twin --dry-run` shows the cost; after approval `avs twin --yes`. Or `avs avatar --file clip.webm` for a clip they already have. A video with no presenter is allowed (`avs avatar --never`).
7. **Storyboard and plates** (`avatar-visuals`): write `storyboard.json`, then `avs imagegen`. Look at every plate before rendering. Make the opener, the payoff and any place/reveal scene a **depth stage** (`avatar-stage`): photographic pieces placed in 3D space with a real moving camera, no video model.
8. **Build, draft, render** (`avatar-render`): `avs build`, `avs render --draft`, review stills, fix, then `avs finish` (render, mix, covers, QA).
9. **Cover** (`avatar-cover`): produced by default for every video, in 9:16, 3:4 and 4:5, two variants.
10. **QA and delivery**: `avs qa` must pass. Open the contact sheet. Deliver `out/final.mp4` and the covers, then `avs concept commit` to log the world in the history.

## Non-negotiables

- **Photographic and tactile, always.** Real materials, physical light. Never anime, cartoon, 3D-cartoon, flat vector, or "AI illustration" look. The engine rejects those words in plate prompts. This is the studio's spine: the style of the *world* changes every video, the *quality and realism* never does.
- **Every video is different.** Different material, light, palette, type and transition language. Use the concept engine; do not hand-pick a favorite.
- **Clear for a stranger.** One idea. A viewer who has never heard of the topic must understand it in the first 10 seconds. Explain terms the first time they appear.
- **Fast but readable.** Scenes of 1.2 to 4.5 seconds, 2.7 on average. Headlines are 4 words or fewer. Nothing covers the presenter's face.
- **Cover photos are default.** Unless the user says no, every video ships with covers.
- **Facts are checked.** Numbers, names, claims: verify with a search before they go on screen.
- **Honest voice.** Only clone the user's own voice (or one with written permission), and only with `--confirm-own-voice`.
- **Money needs a yes.** Never run `avs twin --yes` without explicit approval of the estimated cost.
- **The first frame is the hook.** t=0 already shows the headline and the presenter; there is no black or logo intro.

## References (read when you reach that step)

- `references/quality-bar.md`: what "studio level" means, with a checklist you apply before delivering.
- `references/pacing-and-structure.md`: hook, beats, payoff, scene rhythm.
- `references/hebrew.md`: Hebrew script, spelling for TTS, RTL type, emphasis.
- Visual recipes are in the `avatar-visuals` skill.

## When something fails

Read the `fix:` line printed after every `[!!]`. Do not retry the same failing call more than twice. If a paid step failed, check `avs` output for a job id and resume it instead of resubmitting.

## Final message to the user

Short: where the files are, the world used and why it suits the topic, any warning (fallback voice used, QA notes), and one suggestion. No recap of the steps.
