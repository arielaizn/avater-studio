---
name: avatar-concept
description: Choose the visual world for a video so it differs from recent ones: material, light, palette, type, captions, transition, sound. Use after the script is written and before plates are generated; also when the user asks for a different look or says videos feel repetitive.
---

# Concept: a different world every time

The studio has a constant spine (photographic realism, presenter in the bottom third, pacing, loudness) and a variable world. The engine keeps a history of the last videos and refuses worlds that are too close to them (different family and material from the last 5, a different light and a 40 degree hue gap from the last 3, and an overall distance above a threshold).

## Steps
1. `avs concept propose --topic "<one line>" --project <p>`: prints up to 6 candidates, ranked by how well they suit the topic and how far they are from the history. Each shows material, light, accent hue, type pairing, caption style, transition language, sound bed, setting and recurring motif.
2. Choose by meaning, not taste: which world makes the *idea* visible? A video about hidden cost suits a ledger-and-brass world; about speed, a wet-asphalt night. Say why in one sentence.
3. `avs concept pick --index N --title "<title>" --topic "<topic>" --metaphor "<the one metaphor>" --hero "<the one object that recurs>" --project <p>`. This writes `concept.json`.
4. Optional: remix a single axis with `--extra file.json` (for example a different transition) when the user asks for it; the check still applies.
5. `avs concept check --project <p>` must pass.
6. Only after the video is delivered: `avs concept commit --project <p>`, which logs it so the next video avoids it.

`avs concept worlds` lists every world; `avs concept history` shows what was used. To add a new world, append an entry to `data/worlds.json` (keep fields complete: family, material, light, hue, palette, type, captions, transition, sound, setting, props, motif, plate_style).

## What the concept controls
Palette (bg, ink, paper, accent, accent2), fonts, caption style, default transition, the sound bed, grain and vignette, and the plate style text that is appended to every image prompt so all scenes share one world. It never changes the realism or the pacing.

## Forbidden
Anime, cartoon, Pixar-like 3D, flat vector, "illustration" looks. The constraint is on the *rendering*: a video can be warm, cold, dusty, neon, clinical or lush, but always photographic.
