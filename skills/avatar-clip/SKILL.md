---
name: avatar-clip
description: Quick designed clip from a short text (10 to 30 seconds) with no storyboard writing: pick a frame style, get a voiced, designed vertical video with cover. Use for quick posts, announcements, stories, or when the user wants a fast avatar clip rather than a full production.
---

# Quick clips

`avs clip` does the whole pipeline with automatic design: voice, a fresh world, scene splitting, headlines, plates, render, mix, cover and QA.

```
avs clip --text "..." --frame studio --name launch-note --topic "product launch" \
         --headlines "יוצאים לדרך|שלושה דברים חדשים|בואו לראות" --presenter-file me.webm
```

## Frames
| `--frame` | Look |
|---|---|
| `studio` | presenter in the bottom third over a photographed world, headline above |
| `spotlight` | presenter larger and centered, headline above |
| `side` | presenter off to one side |
| `image` | no presenter, plate and type only |
| `plain` | solid world color with big type, no plates (fast, no image key needed) |

## Tips
- `--headlines` (4 words or fewer each, separated by `|`) gives much better results than auto-picked words. Provide them whenever you can.
- `--prompt "a cluttered potter's desk"` steers the world's photograph (English, concrete).
- No Gemini key: the clip uses procedural placeholder plates and says so. Provide plates for anything you publish.
- A quick clip still goes through the concept engine, so it differs from recent videos.
- For anything longer than 30 seconds, or when the story matters, use the full pipeline in `avatar-studio` instead.
- It creates a normal project, so you can open `storyboard.json`, adjust it, and run `avs finish` again.
