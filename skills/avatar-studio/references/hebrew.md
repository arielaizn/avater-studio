# Hebrew (and RTL) notes

## Writing the script
- Spoken Hebrew, short sentences, no nikud unless a word is ambiguous. Prefer everyday words over formal ones.
- Write numbers as words when they are spoken oddly ("אלפיים עשרים ושש"), as digits when they are on screen only.
- Latin names and brands: write them in Latin letters; Cartesia and ElevenLabs handle common ones. If a name is mispronounced, spell it phonetically in the script ("קלוד") and keep the correct spelling in the headline.
- Run `avs say-test "<line>"` for any risky word before voicing the whole script.

## Captions and headlines
- The page is RTL (`dir=rtl`). Mixed Hebrew and Latin text is handled by the browser's bidi algorithm; keep Latin terms short.
- Captions use the script's spelling, aligned to the voice's word timing.
- Hebrew prefixes (ה, ו, ב, ל, מ, ש, כ) are attached to words. Time anchors accept the bare word: `word:קלוד` matches "הקלוד".
- Emphasis with `*word*` colors that word in the headline.

## Display faces bundled (all open licenses)
Heebo, Rubik, Secular One, Karantina, Suez One, Frank Ruhl Libre, Alef, Amatic SC, Bellefair, David Libre, Miriam Libre, Assistant, Varela Round. The concept engine picks a pairing; override only with a reason.

## Other languages
Set `language` and `direction` with `avs profile set language=en direction=ltr`. Everything else works the same; Cartesia supports many languages, and `avs voices --language <code>` lists matching voices.
