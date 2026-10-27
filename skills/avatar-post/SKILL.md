---
name: avatar-post
description: After a video is rendered: write the caption, hashtags and posting notes, review the contact sheet, and log the world so the next video differs. Use when the user asks for a caption, wants to publish, or when finishing a project.
---

# After the render

1. Open `out/contact_sheet.jpg` and `out/qa.json`. Mention any unresolved QA note.
2. **Caption** (in the video's language): line 1 is the hook, restated differently; 2 to 3 short lines of value; the profile CTA only if set (`avs profile`). No hashtag wall: 3 to 5 specific tags.
3. **Cover choice**: recommend one of `out/covers/` for the grid and one for the feed.
4. **Log the world**: `avs concept commit --project <p>` (once the user is happy with the video).
5. Tell the user, in two lines: where `final.mp4` and the covers are, and which voice provider narrated (and a warning if the backup was used).

Publishing itself is the user's decision; do not post anywhere on your own.
