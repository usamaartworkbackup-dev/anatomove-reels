# Anatomove reels

Public media host for the Anatomove Instagram (anatomove.physio). Claude renders each reel here and Metricool pulls the video from its raw link to publish it.

- `reels/<date>-<slug>/` — `script.json` (narration + scenes), `caption.txt`, `reel.mp4`
- `pipeline/render_reel.py` — free renderer: Kokoro TTS + PIL + ffmpeg
- `highlights/` — Instagram Highlight covers

Educational content, not medical advice.
