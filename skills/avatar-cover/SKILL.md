---
name: avatar-cover
description: Cover photos for avatar videos: produced by default for every video in 9:16, 3:4 and 4:5, hero and type variants, from the video's own world. Use to regenerate, restyle or customize covers, or when the user asks for a thumbnail or cover.
---

# Covers

Covers are on by default (`avs profile set covers.enabled=false` turns them off). `avs finish` makes them; `avs cover` makes them alone.

## What you get
`out/covers/cover_<variant>_<format>.png`:
- **hero**: the world's plate, the presenter (a frame where the expression reads), a big headline of 4 words or fewer.
- **type**: the palette's background with the headline huge and a short sub-line; for feeds where a face is not the draw.
- Formats: `9x16` (1080x1920, Reels/Shorts/Stories), `3x4` (1080x1440, profile grid), `4x5` (1080x1350, feed). The 9:16 hero is also saved as `out/cover.jpg` and embedded in `final.mp4`.

## Controlling them
In `storyboard.json`:
```json
"cover": {"headline": "אווטאר *אמיתי*", "sub": "זה לא הטכנולוגיה", "variant": "hero", "avatar_time": 0.8, "plate": "plates/s3.png", "style": "slab"}
```
- `headline`: 4 words or fewer, one emphasized word. It is the promise, not the title.
- `avatar_time`: the second of the presenter clip to use. Pick a moment with the mouth closed or smiling; check the still.
- `plate`: any plate; the strongest image of the video usually works best.
Options: `avs cover --variants hero,type --formats 9x16,4x5`.

## Check
Open the covers. Readable at 150 px wide? Face visible and not covered? Headline inside the safe area (profile grids crop the edges)? If not, shorten the headline or change `avatar_time`.
