---
name: avatar-stage
description: 2.5D depth scenes for avatar videos. Flat image pieces (background, midground, foreground cut-outs) are placed in 3D space and a real perspective camera moves through them, with no video model. Use for hero shots, reveals, openers, dioramas, "camera flies through the world" moments, or whenever a flat plate would feel like a slide.
---

# Depth stage (2.5D)

A scene's `plate` can be a **stage**: several images placed at different depths, with a camera that dollies, trucks, cranes or orbits through them. Because the pieces sit at real distances, near layers move more than far ones (true parallax), which reads as a 3D set without any video generation. It is deterministic, cheap (a few images), and keeps the studio's photographic look because every piece is a photograph.

## When to use it
- The opening shot and the payoff shot (the two scenes that must feel big).
- Any scene about a place, a room, a object-with-surroundings, a journey, a reveal.
- 3 to 6 stage scenes per 60 s video is plenty; the rest stay on normal plates. Do not stage every scene.
- Not for scenes dominated by a diagram, a counter or a quote: use a normal plate.

## Storyboard
```json
{"id": "reveal", "start": "w:8", "end": "w:13", "avatar": {"show": false},
 "plate": {"stage": {
   "camera": {"move": "dolly-in", "amount": 1.1},
   "perspective": 1400, "origin": [0.5, 0.42], "center": -300,
   "layers": [
     {"prompt": "the far wall of a clay workshop, shelves of pots, warm window light", "z": -900, "w": 1.5, "cutout": false, "blur": 3},
     {"prompt": "a potter's wheel with a half-formed vase", "z": -450, "x": -0.2, "y": 0.1, "w": 0.55, "anchor": "bottom", "top": 0.72},
     {"prompt": "a glowing oil lamp on a small stool", "z": -150, "x": 0.26, "y": -0.04, "w": 0.4, "anchor": "bottom", "top": 0.72, "float": 6},
     {"prompt": "out-of-focus leaves of a plant, close to the lens", "z": 260, "x": -0.32, "y": 0.2, "w": 0.7, "anchor": "bottom", "top": 1.0, "blur": 3}
   ]}}}
```

### Layer fields
| Field | Meaning |
|---|---|
| `prompt` | English description of ONE isolated object (or the background). The generator renders cut-outs on chroma green and keys them to transparency. |
| `src` | Use your own PNG instead (transparent for cut-outs). Default `plates/<scene>_L<i>.png`. |
| `cutout` | `true` for objects (default for every layer after the first), `false` for a full background. |
| `z` | Depth in px. Negative = farther (background -900 to -600), 0 = the plane of the frame, positive = closer than the frame (foreground 150 to 400). |
| `w` | Apparent width as a fraction of the frame width at rest (perspective compensated). Background 1.4 to 1.6 so edges never show during the move. |
| `x`, `y` | Offset as a fraction of the frame width/height. |
| `anchor` / `top` | `bottom`: the object stands on a line `top` (fraction of frame height, 0.7 = 70% down). Use it so objects sit on the floor instead of floating. |
| `blur`, `brightness` | Depth of field and atmosphere: far and very near layers slightly blurred, far layers slightly darker. |
| `float` | A gentle bob in px for lights, dust, hanging things. |

### Camera
`move`: `dolly-in` (push through), `dolly-out`, `truck-left`, `truck-right`, `crane-up`, `crane-down`, `orbit-left`, `orbit-right`, `drift` (slow combination). `amount` 0.5 to 1.5 (default 1). Move lasts the whole scene. Vary the moves between stage scenes; dolly-in for reveals, orbit for objects, truck for panoramas.

## Method
1. Decide the scene's three planes before prompting: **far** (the place), **mid** (the subject, 1 or 2 objects), **near** (something close to the lens, blurred). Fewer than 3 layers will not read as 3D (the build warns).
2. Use the concept's world in every prompt (materials, light, palette). All pieces must look like they were photographed in the same room, same light direction. The generator adds the world's style and uses the first image as a style reference.
3. Keep the lower 38% calm when the presenter is shown (the background prompt gets that instruction). With the presenter visible, put objects at the sides and keep `top` of mid objects above 0.7.
4. `avs imagegen --dry-run` to read the prompts, then `avs imagegen`. Open every piece. A cut-out with a ragged edge, green fringe, a baked shadow or a cropped subject gets regenerated (`avs imagegen --only reveal_L2 --force`) or replaced with your own transparent PNG.
5. `avs render --stills <times in the scene>`: look at three frames (start, middle, end). The parallax must be visible and no background edge may appear. If an edge shows, increase the background `w` or reduce the camera `amount`.
6. Combine with normal layers: headlines, counters and captions work on top of a stage exactly as on a plate. Keep type out of the presenter's face zone.

## Rules
- Photographic pieces only. No flat vector, no cartoon cut-outs.
- Do not put more than 5 layers in a stage; more makes a collage, not a set.
- A layer that is too close (`z` above 450) will fill the frame; use it only as a blurred foreground accent.
- Previews: `avs build --placeholders` makes stand-in shapes so you can check the camera move before spending on images. Never publish placeholders.
- Needs `GEMINI_API_KEY` (or your own PNGs). Cost: one image per layer.

## Technical note
The stage uses a real perspective projection (the same math as a three.js perspective camera) in the renderer's browser page, so it is frame-exact and needs nothing else installed. If the user specifically wants a Blender or three.js scene instead, build it from the same layer list (images as planes at the same z, a camera with the same dolly path) and import the rendered frames as the scene's plate video; ask before going that route, it is slower.
