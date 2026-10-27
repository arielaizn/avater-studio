---
name: avatar-voice
description: Voice the script with Cartesia (default) or ElevenLabs (backup), with exact word timing for captions. Use when the script is final and the user wants the narration, or to fix pronunciation, speed or provider.
---

# Narration

`avs tts --project <p>` reads `script.txt` and writes `audio/narration.wav`, `audio/words.json` (every word with start/end), `audio/timing.json` (paragraph times) and `audio/tts_log.json` (which provider voiced it).

## Policy
- **Cartesia is the default narrator.** ElevenLabs runs only if Cartesia cannot voice the script (missing key, no voice chosen, repeated errors). Then the whole script is re-voiced by ElevenLabs, never mixed, and the command prints `Fallback used`. Tell the user in your final message.
- Check readiness with `avs doctor` (it lists both providers). A fallback with no key configured is a silent trap, so recommend adding the ElevenLabs key.
- `--provider elevenlabs` forces the backup only when the user asks. `--provider mock` makes a placeholder voice for tests.

## Before voicing the whole thing
1. `avs tts --dry-run` shows words, paragraphs and estimated seconds.
2. Test risky words with `avs say-test "<line>"` (names, English terms, numbers). Respell phonetically in the script if needed; keep the real spelling in headlines.
3. Speed: `avs profile set voice.cartesia.speed=1.05`. Do not go above 1.15.

## Timing
Word times come from the provider's timestamps when available, otherwise from forced alignment or an estimate. Captions always use the script's spelling. Time anchors in the storyboard refer to these words: `w:12` is word index 12 in `audio/words.json`. Open that file when you write the storyboard.

## After voicing
- Listen is not possible for you; trust the log. If the duration is far from the plan, edit the script and re-run; do not stretch audio.
- The presenter is rendered *from* this audio, so lock the script before `avs twin`.
