---
name: avatar-script
description: Write the spoken script and the plan for an avatar video: hook, one idea, short spoken lines, fact checks, and a PLAN.md with scenes and cost. Use before voicing anything, when the user gives a topic or rough idea for a reel/short.
---

# Script and plan

## Understand first
Ask at most two questions, only if the answer changes the video: who is it for, and what should they do or think afterwards. If the user gave a topic, start; do not interview them.

## Research
Anything factual (numbers, dates, product behavior, names) is looked up and confirmed before it is written. Keep a short list of sources for the final message. When the topic is current, search; do not rely on memory.

## The script
- Read `../avatar-studio/references/pacing-and-structure.md` and `../avatar-studio/references/hebrew.md`.
- 110 to 170 words for 45 to 70 seconds in Hebrew (about 2.6 words per second). Count before voicing: `avs tts --dry-run` prints the estimated duration.
- One idea. Hook in the first sentence: a claim, a contradiction, or a question the viewer wants answered. No greeting, no "hi everyone", no "in this video".
- Spoken, not written: short sentences, concrete nouns, one metaphor carried through the video.
- A viewer who does not know the topic must follow it. Define a term the first time, in plain words, in the sentence where it appears.
- End on the payoff. Add the profile's CTA only if there is one, in one sentence.
- Paragraph breaks (blank lines) mark breaths and scene groups; keep paragraphs to 1 to 3 sentences.
- Write it to `script.txt` in the project (`avs new <name>` creates the folder).

## PLAN.md
In the project, fill in `PLAN.md`:
1. The idea in one sentence a stranger understands.
2. The metaphor and what the world should feel like (the concept engine will propose real options next).
3. Scene list: one line per scene with the spoken words it covers, what is on screen, and where the presenter is shown or hidden.
4. Cost: presenter seconds x $0.12, plates count, narration provider. Present the plan and the cost, and wait for a yes before `avs twin --yes`.

Then continue with `avatar-concept`.
