---
name: avatar-visuals
description: Design the storyboard and generate the photographic scene plates for an avatar video: scenes anchored to spoken words, kinetic type, camera moves, overlays, presenter windows. Use after the voice and world exist and before rendering.
---

# Storyboard and plates

You write `storyboard.json`; the build step resolves every time anchor against the real word timings. Full field reference: `references/storyboard-reference.md`. Copy-paste recipes: `references/recipes.md`. A complete working example: `examples/storyboard.example.json` in the plugin root.

## Process
1. Read `audio/words.json` (index, word, start, end) and `concept.json` (palette, type, setting, hero, plate_style, transition).
2. Cut the script into scenes of 1.2 to 4.5 s (average 2.7). Cut on beats of meaning. Give each scene an `id`, a `start` (`0`, `w:<i>`, `word:<text>`, or seconds) and let `end` default to the next scene's start.
3. For each scene write the **plate prompt**: one photograph, in English, describing real objects and light inside the concept's world. Mention the hero object where it helps. No text, no logos, no faces of real people, never the forbidden styles. The lower 38% must stay calm when the presenter is shown (the generator adds that instruction).
4. Add **layers** (headline first). Anchor each to the word that triggers it. 1 to 5 layers per scene; calm scenes have one.
5. Decide **presenter windows** per scene: `"avatar": {"show": true}` or `false`. Show at the open, hide for full-frame moments, return for the payoff. Keep the presenter on screen 55 to 70 percent of the time.
6. For hero scenes (opener, payoff, any place or reveal) consider a **depth stage**: pieces in 3D space with a moving camera. See the `avatar-stage` skill.
7. Choose **camera**: `plate.move` push-in, pull-out, pan-left/right/up/down, drift; `plate.focus [x,y]` sets the zoom center on the subject; `plate.beats` add a punch or shake on a word.
8. Choose **transitions** from the concept's language; vary them. First scene is always a cut. `transition: {"type": "whip-pan", "dur": 0.4}` overrides.
9. Fill `cover` (`headline` of 4 words or fewer, optional `sub`, `variant`, `avatar_time`).
10. `avs build` and read every warning. Then `avs imagegen --dry-run` to review the final prompts, then `avs imagegen`.
11. **Look at every plate** (open the PNGs). Regenerate weak ones with a better prompt: `avs imagegen --only s3 --force`. A plate that is flat, glossy-AI, text-filled or off-world is rejected.
12. `avs render --stills 0.3,2.5,...` and look at 6 to 8 frames. Fix overlaps, then continue with `avatar-render`.

## Rules of thumb
- One focal point per scene. If a headline and a card compete, drop one.
- Headlines: 4 words max, one emphasized word with `*word*`. Different headline `style` from the previous scene (plain, slab, sign, outline, highlight, neon, stamp, label).
- Captions are automatic (style from the concept). Keep headlines out of the caption band (y about 0.57 to 0.66 with presenter, 0.74 without).
- Numbers on screen: `counter`. Comparison: `compare`. Steps: `list`. Source or claim: `quote`/`lower`. A verdict: `stamp`.
- Motion principle: the viewer's eye should be led, so layers appear on the word and the camera always moves a little.
- Sound effects are added automatically from transitions and layers; add `sfx` entries only for a moment that needs one.
- If you need an object that must be consistent across scenes (a prop, a product), generate it once as an `assets` entry and reuse it as a `card` or `sticker` image.

## Plates without a Gemini key
Generate them with any image tool the user has, and save as `plates/<scene-id>.png` at 1080x1920 (9:16), photographic. For previews only: `avs imagegen --placeholders` or `avs build --placeholders` makes procedural stand-ins. Never publish a video made with placeholders.
