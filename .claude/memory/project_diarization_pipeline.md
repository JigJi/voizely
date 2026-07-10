---
name: Diarization Pipeline Winner
description: Proven pipeline for mono Teams recordings — Deepgram timestamps + spectral clustering speakers + Gemini audio-correct
type: project
---

Tested extensively on BD_Weekly_15min.mp4 (mono 16kHz Teams recording, 4 speakers, Jabra mic).

**Winning pipeline (ID 134):**
1. Deepgram → utterance timestamps + raw text (aligned to audio)
2. speechbrain ECAPA embeddings + Spectral Clustering (n=speakers) → speaker labels per utterance
3. Gemini Flash audio-correct → send Deepgram text + audio clip per chunk, Gemini fixes text while listening
4. Post-process: fix Thai word splits (THAI_CANT_START chars), merge consecutive same-speaker

**Why:** Deepgram diarization fails on mono Teams (sees 1 speaker). Pyannote sees 74% one speaker. Gemini-only gets speakers but timestamps are random. Spectral clustering on embeddings was the breakthrough — much better than Agglomerative clustering.

**How to apply:** This should be the default mode for mono meeting recordings. Key params: spectral n_clusters (user-selectable or auto-detect), chunk size ~3min for Gemini correction.

**Cost:** ~$0.05 per 15min file (Deepgram $0.04 + Gemini $0.007 + summary)
