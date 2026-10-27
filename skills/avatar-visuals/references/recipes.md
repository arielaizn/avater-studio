# Recipes (copy, then change the words)

## Opening scene (t=0 is already the hook)
```json
{"id": "hook", "start": 0, "end": "w:5",
 "plate": {"prompt": "...hero object in the world, lower third calm...", "move": "push-in", "focus": [0.5, 0.35]},
 "avatar": {"show": true},
 "layers": [
  {"type": "headline", "text": "הכסף *נעלם*", "style": "slab", "pos": [0.5, 0.2], "size": 160, "at": 0.1, "anim": "slam", "settle": true},
  {"type": "lightsweep", "at": 0.5, "dur": 1.0}
 ]}
```

## The number scene (presenter hidden)
```json
{"id": "num", "start": "word:אלף", "end": "+2.6", "transition": "dip-flash", "avatar": {"show": false},
 "plate": {"prompt": "...macro of the object this number counts...", "move": "pull-out", "shade": 0.3},
 "layers": [{"type": "counter", "from": 0, "to": 4800, "prefix": "₪", "label": "בחודש", "pos": [0.5, 0.42], "size": 300, "at": "word:אלף", "dur": 1.1}]}
```

## Before / after
```json
{"type": "compare", "left": {"label": "לפני", "src": "assets/before.png"}, "right": {"label": "אחרי", "src": "assets/after.png"}, "h": 0.4, "pos": [0.5, 0.4], "at": "w:30"}
```

## Three steps
```json
{"type": "list", "pos": [0.5, 0.4], "items": [{"text": "מחליטים", "at": "w:40"}, {"text": "בונים", "at": "w:43"}, {"text": "משחררים", "at": "w:46"}]}
```

## Point at the thing
```json
{"type": "circle", "rect": [0.3, 0.3, 0.4, 0.2], "at": "word:כאן", "color": "accent2"},
{"type": "arrow", "from": [0.2, 0.5], "to": [0.45, 0.38], "at": "word:כאן"}
```

## Verdict
```json
{"type": "stamp", "text": "לא עובד", "pos": [0.5, 0.35], "size": 140, "rot": -8, "at": "word:עובד", "color": "accent"}
```

## Source line
```json
{"type": "lower", "title": "דוח מקצועי 2026", "sub": "עמוד 14", "pos": [0.5, 0.58], "at": "w:22"}
```

## A punch on a word
```json
"plate": {"prompt": "...", "move": "drift", "beats": [{"at": "word:בום", "kind": "punch", "amt": 0.07}]}
```

## Payoff + CTA scene
Presenter shown, one headline, `confetti` only if the tone is celebratory, then the profile CTA as a `label` headline in the last 2 seconds:
```json
{"type": "headline", "text": "עקבו להמשך", "style": "label", "pos": [0.5, 0.2], "at": "w:120"}
```
(Anchor it to the first word of the closing sentence.)
