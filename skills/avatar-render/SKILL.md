---
name: avatar-render
description: Compile, preview, render and finish an avatar video: presenter (HeyGen or your own clip), build, draft, stills, full render, audio mix to -14 LUFS, covers and QA. Use once the storyboard and plates exist.
---

# Presenter, build, render, finish

## Presenter
- **HeyGen twin:** `avs twin --dry-run` prints the request and the estimated cost (about $0.12 per second of narration). Show the user the number. Only after an explicit yes: `avs twin --yes`. It uploads the narration, renders a transparent webm, downloads it, crops to the figure and extracts frames (`twin/frames`, `twin/fit.json`). If it times out it prints a resume command (`avs twin --resume <video_id>`); never resubmit, you would pay twice.
- **Own clip:** `avs avatar --file clip.webm` (transparent webm is best; any clip on a plain background also works, shown as an opaque panel). The clip must be as long as the narration or the presenter freezes at the end; the build warns about it.
- **No presenter:** `avs avatar --never`.
- The presenter renders from the final narration. If you change the script afterwards, re-voice and re-render the twin (that costs again), so lock the script first.

## Build and look
1. `avs build` writes `comp/index.html`. Read every warning; fix them.
2. `avs render --stills 0.3,2.4,5,8 --project <p>` writes PNG stills in `out/stills/` (add `--full` for full size). Look at them. Check: presenter's face clear, captions readable, headlines inside the frame, nothing overlapping.
3. `avs render --draft` makes a half-size 15 fps preview quickly; `avs render --start 10 --end 20` renders only a range.
4. `avs qa --no-layout` before the final render is optional; `avs qa` after it is mandatory.

## Finish
`avs finish` runs: full render (1080x1920, 30 fps), audio mix (voice + ducked music bed + effects, two-pass loudness to -14 LUFS, true peak under -1 dBTP), covers (9:16, 3:4, 4:5; hero and type variants; the 9:16 hero is also embedded as the file's thumbnail), and QA.

Outputs in `<project>/out/`: `final.mp4`, `cover.jpg`, `covers/*.png`, `contact_sheet.jpg`, `qa.json`.

## QA failures
`avs qa` exits with code 3 and lists problems. Typical fixes: slow pacing (split scenes, add beats), frozen picture (add camera movement), a layer covering the face (move it or hide the presenter), loudness off (re-run `avs mix`). Re-render only what changed (`--start/--end`), then `avs mix` and `avs qa` again.

## Time and size
A 60 s video renders in a few minutes on a laptop (parallel Chromium workers). Output is H.264, about 10 to 25 MB. Do not re-encode it afterwards.
