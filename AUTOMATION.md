# Anatomove automation runbook

This file is the instruction set for Claude's scheduled runs that manage the Anatomove Instagram (anatomove.physio). Muhammad asked for the account to run without him. He only posts stories and adds them to Highlights.

## Fixed facts

- Metricool brand id: `8062056`, timezone `Asia/Karachi`. FREE plan: max 20 scheduled posts per calendar month, 30 days of analytics.
- This repo: `usamaartworkbackup-dev/anatomove-reels`, branch `reels`. Public raw link pattern:
  `https://raw.githubusercontent.com/usamaartworkbackup-dev/anatomove-reels/reels/<path>`
- Google Drive "Reels" folder id `1LzUNnD8dscPbs2kpt2C4xztSYwk5O81w` (Muhammad's own edited reels may also appear there as `Anatomove - <Topic>.mp4` + `Caption - <Topic>.txt` + `Cover - <Topic>.jpg`; Drive links work in Metricool as `https://drive.google.com/uc?export=download&id=<file id>`).
- Voice: Kokoro `af_heart` (sweet, engaging female voice), speed 1.05. Every reel uses an AI voice, so set `instagramData.isAiGenerated: true`.
- Style: dark background, bold orange `#FF5C1F` and cyan `#22D3EE`, Inter fonts. Reels 1080x1920, 35–45 s. Carousels 1080x1350, 5–8 slides.

## Setup at the start of every run

```bash
cd /home/claude
git clone --depth 1 -b reels https://github.com/usamaartworkbackup-dev/anatomove-reels anatomove-reels
pip install --break-system-packages -q kokoro-onnx soundfile
mkdir -p tts && cd tts
curl -sSL -o kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -sSL -o voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

If cloning or pushing fails, stop and tell Muhammad exactly what failed. Never publish a reel whose file is not in the repo.

## Accuracy gate (non-negotiable)

Anatomove is educational health content. Nothing is made up.
- Every number, study or claim in a script or caption must come from a page you actually opened (journal, StatPearls/NCBI, NHS, textbook, major hospital). Not from memory, not from a search snippet alone.
- State limits honestly: a computer model is a model, a case report "can contribute", a correlation is "a link, not a cause".
- Include a red-flag line when relevant (numbness, weakness, fainting, pain that doesn't settle → see a physio or doctor).
- If a claim cannot be verified, drop it. If the topic falls apart, pick another topic. Never publish to fill a slot.

## Weekly run (Sunday)

1. Setup (above).
2. Report: Metricool `getAnalyticsDataByMetrics` for the last 7 and 30 days. Reels: IGRE01 date, IGRE03 caption, IGRE23 views, IGRE11 reach, IGRE10 likes, IGRE07 comments, IGRE12 saves, IGRE21 shares, IGRE24 avg watch time, IGRE30 skip rate. Account: IGEV01 followers, IGEV43 gained, IGEV44 lost, IGEV30 avg reach per reel. Ignore reels under 72 h old. Best and worst reel and why.
3. Days: read `SCHEDULE.md` for next week's reel days and carousel day. On the run of Sunday 13 Dec 2026, make the day decision from `data/day-test-log.csv` as SCHEDULE.md describes, write it into SCHEDULE.md, and use it from then on. After that, keep those days.
4. Budget: `getScheduledPosts` for the current and next month; count posts. Never exceed 20 in a calendar month. If tight, drop the carousel first, then reels.
5. Topics: read `topics.md` and the captions from step 2. Pick 3 new reel topics in the niche: everyday habits and moments, and the body mechanics behind them (sitting, sleeping, phones, walking, lifting, standing, desk work, common sensations). Strong first-3-second hook: a "try this right now" check or a surprising specific number. Part 1 / Part 2 series are welcome. Never repeat a topic.
6. For each reel:
   - Research and verify (accuracy gate).
   - Write `reels/<YYYY-MM-DD>-<slug>/script.json` for `pipeline/render_reel.py` (scene types: `tilt` head/neck figure with angle steps and cue words, `pool` standing body with blood drain/pump, `big` headline + sub, `cta` question + 2–3 options). You may add a new scene type to the renderer when a topic needs a different picture; keep the style. Put spoken numbers as words in `tts`, digits in `say`. Set `footer` to the short source names.
   - Render sample frames first: `python3 -I pipeline/render_reel.py <script> <out> /home/claude/tts --frames 1.5,8,15,25,35`, look at them (Read the jpgs), fix overlaps or sync problems, then render fully. Copy the final mp4 to `reels/<date>-<slug>/reel.mp4`.
   - Write `caption.txt`: hook line, mechanism in plain words, one real number, honest caveat, tips, red flag, binary comment prompt in caps, send/save CTA, follow CTA, Sources, "Educational content, not medical advice.", 3–5 hashtags ending `#anatomove`.
7. Carousel (one a week, if budget allows): `carousels/<date>-<slug>/carousel.json` for `pipeline/render_carousel.py`; ideas in the Playbook (myths recap, body by the numbers, sleeper guide, balance test, desk survival guide, red flags, study of the week, Ask a Physio answers). Same accuracy gate.
8. Commit and push to `reels` (commit message ends with the Co-Authored-By and Claude-Session lines your environment gives you). Confirm each raw link returns HTTP 200 with `curl -sI`.
9. Schedule in Metricool with `createScheduledPost`: reels at 10:00, carousel at 18:00, Asia/Karachi, `draft: false`, `autoPublish: true`, `media` = raw links (carousel: all slide links in order), `instagramData.type` = `REEL` (or `POST` for a carousel), `isAiGenerated: true` for reels.
10. Add each new topic to `topics.md`, commit, push. Then update the Drive file "Anatomove - reel links.txt" (file id `14W0Lc70M4JWF4_iEFhy1JmCxZ23e6ccC`, in the Reels folder) with the Google Drive `update_file` tool: keep everything already there and add one block per new post at the top of the list (date and time, title, raw video link, caption link, Metricool plannerUrl).
11. Send Muhammad one short message (SendUserMessage): numbers table, 3 takeaways, what is scheduled (dates, titles, plannerUrl links), any topic dropped by the accuracy gate, and 2 story ideas for the week tied to the new reels.

## Daily log run

1. Clone the repo (no TTS needed).
2. `getAnalyticsDataByMetrics` for reels of the last 10 days (IGRE02 date-time, IGRE03, IGRE23, IGRE11, IGRE10, IGRE07, IGRE12, IGRE21, IGRE24, IGRE30).
3. For every reel posted 72–96 hours ago that is not yet in `data/day-test-log.csv`, append one row (age_hours = hours since posting, slug = first 6 words of the caption, weekday of the post date in Asia/Karachi). Commit and push only if a row was added. No message to Muhammad unless something failed.
