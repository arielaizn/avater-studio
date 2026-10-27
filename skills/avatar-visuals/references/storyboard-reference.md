# storyboard.json reference

```json
{
  "meta": {"title": "..."},
  "avatar": {"height": 0.40},                // optional; false = no presenter in the whole video
  "captions": {"style": "word-pop", "size": 62},  // style defaults to the concept's
  "music": {"level_db": -21},                // or false for no music bed
  "sfx": true,                               // false for no effects
  "assets": [{"id": "prop1", "prompt": "...", "aspect": "1:1"}],   // generated images to reuse as card/sticker src
  "cover": {"headline": "4 words *max*", "sub": "optional", "variant": "hero", "avatar_time": 0.8},
  "scenes": [ ... ]
}
```

## Time anchors
Anywhere a time is expected (`start`, `end`, `at`, `until`, `items[].at`, `plate.beats[].at`, `sfx[].at`):
| Form | Meaning |
|---|---|
| `3.5` | seconds from the start |
| `"w:12"`, `"w:12.start"`, `"w:12.end"` | word index 12 of `audio/words.json` (start by default) |
| `"w:12+0.2"` | plus an offset |
| `"word:קלוד"`, `"word:קלוד#2"` | the first / second occurrence of the word (prefixes ה ו ב ל מ ש כ are tolerated) |
| `"p:2"` | start of paragraph 2 (`.end` for its end) |
| `"scene:hook.end"` | an earlier scene's edge |
| `"+0.4"` | seconds after the scene's start |
| `"end"` | end of the video |

## Scene
```json
{"id": "s3", "start": "w:8", "end": "w:13",
 "plate": {"prompt": "...", "src": "plates/s3.png", "move": "push-in", "amount": 1, "focus": [0.5, 0.4],
           "beats": [{"at": "word:בום", "kind": "punch", "amt": 0.06}], "tint": "#201010", "tintOpacity": 0.3, "shade": 0.25, "bg": "#101820"},
 "transition": "whip-pan",                    // or {"type": "...", "dur": 0.4}
 "avatar": {"show": true, "x": 0, "enter": "rise", "exit": "fall"},
 "layers": [ ... ],
 "sfx": [{"at": "w:9", "name": "hit", "gain": -12}],
 "allow_long": false}
```
- `plate.src` defaults to `plates/<id>.png`. `plate.bg` makes a solid color scene (no image).
- `plate.stage`: a 2.5D depth stage (layers at different z, camera dolly/truck/crane/orbit). Full reference in the `avatar-stage` skill.
- `plate.move`: `push-in`, `pull-out`, `pan-left`, `pan-right`, `pan-up`, `pan-down`, `drift`, `none`.
- Transitions: `cut`, `soft-push`, `whip-pan`, `iris`, `slide-wipe`, `dip-flash`, `zoom-through`, `paper-turn`, `blur-dissolve`, `shutter`, `glitch-cut`.
- Presenter `x` shifts it horizontally (-0.3 to 0.3 of the width). Consecutive shown scenes form one continuous window (the presenter does not re-enter).
- Effects names: whoosh, swish, whoosh-deep, riser, impact, hit, stamp, pop, paper, shutter, glitch, scribble, tick, tick-roll.

## Common layer fields
`type`, `at`, `until` (default scene end), `pos` (`"upper"`, `"mid"`, `"center"`, or `[x, y]` as fractions of the frame), `w` (width fraction), `rot` (degrees), `behind` (draw under the presenter), `color` (`accent`, `accent2`, `paper`, `ink`, or any CSS color), `settle` (true: already fully visible at `at`, for the first frame).

## Layer types
| type | fields |
|---|---|
| `headline` | `text` (use `*word*` for emphasis, `\n` for a line break), `style` plain/slab/sign/outline/highlight/neon/stamp/label, `size` (px at 1080 wide), `anim` pop-words/rise/type/slam/wipe/fade, `emphasis` (indexes or words), `maxh`, `align`, `mock` (3D tilt: `{rotateX, rotateY, rotateZ, blend}`) |
| `stamp` | `text`, `size`, `rot`, `pos` (a verdict stamped on the scene) |
| `badge` | `text`, `pos` (small round sticker) |
| `circle` | `rect: [x, y, w, h]` fractions around the thing to circle, `color`, `width`, `dur` |
| `underline` / `strike` | `rect`, `color`, `width` (hand-drawn line under or through) |
| `arrow` | `from: [x, y]`, `to: [x, y]`, `curve`, `color` |
| `counter` | `from`, `to`, `prefix`, `suffix`, `decimals`, `label`, `size`, `dur` |
| `card` | `src` (image) or `text`/`html`, `enter` pop/rise/drop/slide-left/slide-right/tilt-in/flip/cut, `rot`, `bg`, `textColor`, `radius`, `idle` |
| `sticker` | `src` (transparent PNG), `enter`, `rot`, `w` |
| `list` | `items: [{text, at}]`, `numbered` |
| `quote` | `text`, `who`, `size` |
| `lower` | `title`, `sub` (name/source bar) |
| `bars` | `values: [{label, value, hot}]`, `h`, `prefix`, `suffix` |
| `ticker` | `text`, `speed` |
| `compare` | `left`/`right: {label, src, bg}`, `h` |
| `shape` | `rect`, `kind` rect/circle, `color`, `radius`, `opacity`, `anim` grow-x/grow-y/fade |
| `flash` | `color`, `strength`, `dur` |
| `particles` | `kind` dust/confetti/sparks, `count`, `seed` |
| `lightsweep` | `color`, `dur`, `angle`, `strength` |
| `html` | `html`, `css`, `js` (escape hatch; `js` receives `(el, api)` with the animation API) |

## Captions
`captions.style`: word-pop, karaoke-fill, typewriter, underline-sweep, box-highlight, bounce. `size` (px), `y_avatar`/`y_free` to move the caption band. Captions follow the spoken words and never need to be written.

## Warnings the build prints
Headline over 5 words, scene over 4.6 s or under 0.9 s, over 9 layers, missing plate, presenter first shown after 4 s, twin clip shorter than the narration, unknown fonts. Fix them; they are the quality bar speaking.
