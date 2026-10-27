# Avatar Studio (agent instructions)

This repository is a plugin of skills for making studio-grade vertical videos with a digital avatar. It works in Claude Code and in Codex.

- Start with the skill `avatar-studio` (the orchestrator). The other skills are steps: `avatar-setup`, `avatar-script`, `avatar-concept`, `avatar-voice`, `avatar-visuals`, `avatar-stage` (2.5D depth scenes), `avatar-render`, `avatar-cover`, `avatar-clip`, `avatar-post`.
- All work runs through the `avs` command line (`bin/avs`; `avs setup` installs it on PATH). `avs --help` lists every command.
- Narration: Cartesia is the default provider, ElevenLabs is the automatic backup. Never mix providers inside one video.
- Every video gets a different photographic world from the concept engine; cover photos are produced by default.
- Never ask for API keys in chat; they live in `~/.avatar-studio/.env`.
- Never spend presenter credits (HeyGen) without the user's explicit approval of the estimate.
- Python 3.9+, Node 18+, ffmpeg with libx264/libwebp/libvpx are required (`avs doctor` checks).
