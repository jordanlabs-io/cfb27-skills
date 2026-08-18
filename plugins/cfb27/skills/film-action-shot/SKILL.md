---
name: film-action-shot
description: Turn a charted play from the CFB 27 film room into a photoreal, football-correct cinematic render via Higgsfield — locate the play in the film workspace, pull its vision frames as references, and generate a Sports-Illustrated-grade action shot (or postgame editorial portrait) that matches the real game's stadium, lighting, weather, and both teams' uniforms. Use when the user wants an "action shot", "cinematic render", "hype image", newsletter/social imagery of a specific play, or a portrait of a dynasty player. Also invoked by the tarstool-newsletter skill.
---

# Film → cinematic action shot

The whole trick: real frames from the charted play anchor atmosphere and uniforms;
the prompt supplies photographic realism and *football-correct geometry*. Both
matter — the user rejects renders that look CGI **or** stage football wrong.

## 1. Locate the play

From the game's film-room file (`dynasties/<dynasty>/film-room/games/*.md`)
pick the play number (pNN in the game-flow table). Frames live in the film
workspace: `~/CFB27-film/<slug>/film/playNNN/` — `strip.jpg` (6 frames in a 3×2
grid), `presnap.jpg`, `result.jpg`, `ghost.jpg`. Request folder access to the
specific `<slug>` workspace if it isn't connected. Read the plays CSV row for
down-and-distance, score, and the commentary quote.

## 2. Build references

- Crop SINGLE cells out of `strip.jpg` (cell = width/3 × height/2) — whole strips
  confuse the model into composites. Pick one cell that shows the field/stadium
  truth and one that shows the action moment.
- Upload: `media_upload` → curl PUT each presigned URL → `media_confirm`. Never
  pass raw URLs or local paths into a generation call.
- **Never use photos of real athletes as references — the moderation filter kills
  the whole batch as `nsfw`.** Game screenshots and in-game player cards only.

## 3. Generate

Model: **`nano_banana_pro`, `resolution: "2k"`, 16:9** — the proven winner.
(`gpt_image_2` silently defaults `quality: "low"`; `nano_banana_flash` reads
video-gamey. If using gpt_image_2, set quality explicitly.) Batch independent
shots via `generate_image_batch` + `jobs_wait` + one `show_generation_by_ids`.

Prompt formula (all clauses matter):
1. "Award-winning professional sports photograph, 400mm f/2.8 telephoto from
   [sideline photo pit / end-line photo row / behind the offense's backfield]" —
   pick a real photographer's vantage.
2. **Football-correct staging, stated explicitly.** QB throws from a pocket BEHIND
   his five linemen ("IN FRONT of him, between the quarterback and the defense").
   Punt formation: personal protector ~7yds deep, punter ~14-15 deep with empty
   hands raised on a fake. INT = defender high-pointing in front of the receiver.
   Name yard numbers/hash marks so field geometry reads true.
3. Exact uniform/kit details in words: team + color + helmet + jersey NUMBERS and
   NAMEPLATES in quotes (e.g. blue #8, nameplate 'O'NEILL'; the fake-punt runner
   wears #0). The model duplicates numbers if you don't assign them.
4. Atmosphere copied from the reference frames: time of day, light quality, crowd
   color, end-zone art, signage, goalposts.
5. Close with: "Sports Illustrated color grade, true-to-life proportions,
   absolutely no CGI or video-game rendering, faces hidden by facemasks. Match the
   stadium, lighting and both teams' uniforms from the reference screenshots."

## 4. Inspect like a football person, then iterate

Download the result and LOOK at it before delivering. Checklist: pocket/formation
geometry sensible for the play · field position matches the story (nobody throwing
*into* an end zone they're standing in) · jersey numbers unique and correct ·
nameplates spelled right · uniforms/stadium match the refs · no CGI sheen.
Fix small flaws by editing, not regenerating: pass the completed `job_id` as the
image reference with "Keep absolutely everything identical ... with ONE
correction: [the fix]". Regenerate from scratch only for staging problems.

## Portraits (Player of the Week etc.)

Likeness source: crop head+shoulders from the in-game player card
(the dynasty's design-system uploads folder), upload as reference. Recipe:
"editorial sports portrait, 85mm f/1.4, waist-up" + "the subject is the player
from the reference headshot — same face, same hair" + moment staging (postgame,
helmet at hip, golden hour, emptying stands) + the same realism close. 3:2 crops
well into layout boxes.

## Pitfalls

- 2k jobs occasionally hang `in_progress` >8 minutes — resubmit; the stuck job is
  lost money, not a blocker.
- Batch rejections (`nsfw`) are almost always a real-person photo in the refs.
- Device-bridge staging of frames flakes above ~3MB/file; strip cells are ~200KB
  and fine.
