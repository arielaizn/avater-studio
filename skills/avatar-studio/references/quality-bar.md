# The quality bar

A video leaves the studio only when every line below is true. Check them against stills (`avs render --stills 0.3,2,5,...`) and the contact sheet, not from memory.

## Frame
- The world looks photographed: a real surface, real depth of field, light with a direction. No smooth gradients posing as scenes, no clip-art, no stock-photo glossiness.
- The bottom third belongs to the presenter. The plate's lower area is calm so the figure reads. The presenter is sharp and grounded (soft shadow or surface), never floating on a flat color.
- The presenter's face is never covered by type, cards or stickers. Captions sit just above the shoulders, in the clear band.
- Type is part of the world: one display face and one body face per video, chosen by the concept. Maximum two accent colors, taken from the palette.
- Every scene has one focal point. If two things compete, remove one.

## Motion
- The camera always moves a little (push-in, pull-out, pan, drift). Static plates feel like slides.
- Elements arrive on the spoken word, not before it. Anchor layers to words (`word:` or `w:`), not to guessed seconds.
- Transitions come from the concept's transition language and are never used twice in a row unless it is the signature move. Hard cuts are fine for rhythm.
- Something changes every 1.5 to 2.5 seconds: a new layer, a camera beat, a cut.

## Sound
- Narration is the loudest thing. Music bed ducks under it. Effects are sparse, tuned to the transition, never constant.
- Final loudness -14 LUFS, true peak below -1 dBTP. `avs qa` measures this.
- No clicks at the cuts, no silence at the start (the voice begins within 0.15 s).

## Message
- One idea, said simply. The hook lands in 2 seconds. The last second pays it off.
- Every number on screen is true and sourced.
- A CTA appears only if it is in the profile, and only once.

## Cover
- Readable at thumbnail size: 4 words maximum, high contrast, face visible (hero variant) or typographic (type variant).
- Uses the video's world: same palette, same type.

## Reject on sight
Anime or cartoon look; text baked into the generated plate; a plate that does not match the video's world; headline over the face; five different fonts; a scene longer than 4.6 s with nothing changing; captions that lag the voice; a loud music bed; a mispronounced name.
