# Lane A — my games (Twitch VOD)

Own-game film: streamed to Twitch, 16:9, crisp HUD, commentary/mic audio. Neutral-quality broadcast-style capture of my own screen.

## Operator habit that WILL corrupt charting if ignored

**Elijah opens the `PASS PROTECTION` / blocking-adjustment panel before nearly every one of his own offensive play calls** (confirmed by him, 2026-07-31) — on runs as much as passes. It is a pre-snap ritual, not a play-call tell.

Consequences, both observed live on the UNC–West Virginia re-chart:
- Vision agents that read the on-screen words "PASS PROTECTION" tag the snap `pass`. This systematically inflates the user's own pass rate and mislabels goal-line rushing touchdowns. **Never let menu text decide `play_type`** — see the menu-title rule in `charting-prompts.md`.
- Agents applying the non-play rule to the panel void the whole window. Menu panels draw *over* live football; the play runs behind them. **A window is non-play only if no frame shows live football.**

When a re-chart is needed, the suspect set for a Lane A game is **every one of the user's own offensive snaps**, not just the goal-line ones.

## Intake

- `yt-dlp -J <url>` first. If it fails with a token-null error (auth-gated VOD):
  query Twitch GQL for `seekPreviewsURL` (Client-Id `kimne78kx3ncx6brgo4mv6wki5h1ko`), build `<cdn-base>/chunked/index-dvr.m3u8`, download with `ffmpeg -i <m3u8> -c copy video.mp4` (background).
- 16:9 already — no geometry work. Confirm with `cropdetect` anyway if the stream layout ever changes (webcam overlays, letterboxing).

## Transcription + adjudication

- Extract 16k mono wav; faster-whisper `large-v3-turbo`, cpu/int8, vad_filter → `transcript.json`. (mlx-whisper is broken on M5.)
- **Audio check:** ~0 segments = silent capture (Whisper hallucinates "Thank you." on silent slices) → fall through to the Lane B adjudication path (`adjudicate_hud.py`).
- Transcript adjudication (step 7): haiku text-only subagents, ~40 plays/batch. Transcript window for play N = `[snap_N, snap_N+18s]` — announcers narrate into the next play's window; include the next play's dd for context. Output: final play_type, result, yards, key_event.
- Free ground truth: calling coverages aloud on stream once or twice a drive gives every later charting pass a validation set at zero cost.

## Gemini cloud respot (optional upgrade, Lane A only)

Claude vision is the primary charting lane (step 6, `references/charting-prompts.md`). Gemini is a **respot pass** for coverage-judgment fields (`g_*` columns) when wanted:

- **Delivery: PUBLIC YouTube URLs + `videoMetadata` start/end offsets** clipped to `seg/plays.csv` windows. Twitch's server-side export-to-YouTube means the Mac never uploads archive bytes. Gemini's YouTube ingestion is public-videos-only (unlisted deliberately blocked mid-2025). This is why the lane is Lane-A-only: opponent film can never be posted publicly.
- Requires `GEMINI_API_KEY` in `~/CFB27-film/.env` (the CLI OAuth free tier is deprecated/dead). Clipped game ≈ 274k tokens at default res.
- Offsets have a known intermittent bug — validate on a small calibration batch before a full run. Fallback: `ffmpeg -c copy` per-play clips sent inline (<100 MB each).
- Record video id + offset-alignment check in the game dir's `youtube.json`.
- Charting clips get `fps: 2` (default 1fps misses jet motion and CB hip-flips); segmentation chunks stay default. Flash-tier models fail *judgment* fields regardless of fps — route judgment to pro tier per `references/extraction-framework.md`.
- Provenance: tag respotted columns with the model/date; never mix Claude-frames and Gemini reads in one column without a source tag.
