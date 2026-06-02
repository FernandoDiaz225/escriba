# Escriba

A free, local tool that turns audio (sermons, talks, long recordings) into a clean
transcript **with accurate word-level timestamps** — the one thing the free AI
transcription tools people already use don't do well. You can **watch it
transcribe live** and stop early if a recording isn't working out.

Transcription runs entirely on your own computer, so it's free to run and your
**audio and transcripts never leave your machine**. (Optional, opt-in anonymous
usage counts are the only thing that can be shared — see
[PRIVACY.md](PRIVACY.md).)

---

## What makes it different

- **Word-level timestamps** via WhisperX, exported in formats that keep the timing:
  `.txt`, `.srt`, `.vtt`, and word-level `.json`.
- **Live transcription** — text appears as it's recognized, so you get an instant
  read on quality and can stop a bad job immediately.
- **Runs locally** — no account, no upload, no compute cost.

---

## Easiest install (non-technical)

1. Install **Python 3** (python.org) — on Windows, check "Add to PATH".
2. Download this project (green **Code → Download ZIP** on GitHub, then unzip).
3. **macOS:** double-click `setup.command` (first time: right-click → Open).
   **Windows:** double-click `setup.bat`.
   It checks for ffmpeg (installing it if it can), then installs everything. The
   transcription engine is several GB, so the first setup takes a while.
4. To run it any time after: double-click **`start.command`** (Mac) or
   **`start.bat`** (Windows). Your browser opens to the app.

There's also a short setup video, and you're welcome to book a time to set it up
together over a call.

## Manual install (developers)

```bash
git clone https://github.com/YOUR-USERNAME/escriba.git
cd escriba
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # several GB (PyTorch); grab a coffee
python3 run.py
```

ffmpeg must be installed separately (`brew install ffmpeg` on macOS).

---

## Language support

Pick the language on the upload screen, or detect automatically.

| What you have | Works? | Notes |
|---|---|---|
| All Spanish | ✅ Cleanly | Pick **Spanish** (or auto). |
| All English | ✅ Cleanly | Pick **English** (or auto). |
| Spanish + live English interpreter, you want the **Spanish** | ⚠️ Depends on the recording | Pick **Spanish**. Best if that language is on its own track. The live view helps you catch a bad mixed tape early. |
| English + live Spanish interpreter, you want the **English** | ⚠️ Depends on the recording | Same, with **English** selected. |

If your A/V setup can give you the wanted language on its own feed/channel, use
that — then it's just the clean case. The tool biases toward your chosen language
but can't perfectly separate two voices talking at once in one mixed track.

---

## How it works

```
Browser (web/index.html)
   │  upload + language + mode
   ▼
FastAPI (app/main.py)
   │  validate  →  save temp file  →  start background job
   ▼
Pipeline (app/pipeline.py)
   │  faster-whisper  → stream rough segments live (SSE) ──┐
   │  WhisperX        → word-level alignment at the end    │
   ▼                                                       ▼
Result store ──► delete audio          Browser shows live text + progress,
   ▲                                    then final aligned transcript +
   │  /api/stream (SSE) · /api/result   TXT/SRT/VTT/JSON downloads
```

### Project layout

```
escriba/
├── setup.command / setup.bat     # one-time setup (double-click)
├── start.command / start.bat     # launch the app (double-click)
├── run.py                        # starts server + opens browser
├── requirements.txt
├── README.md  ·  PRIVACY.md  ·  LICENSE
├── app/
│   ├── main.py        # FastAPI app, SSE streaming, consent, exports
│   ├── pipeline.py    # faster-whisper streaming + WhisperX alignment
│   ├── telemetry.py   # local usage counter + opt-in anonymous ping
│   ├── exports.py     # TXT / SRT / VTT / JSON builders
│   └── config.py      # guardrail + telemetry constants
├── web/
│   └── index.html     # the interface (designed around Nielsen's heuristics)
└── telemetry-server/  # optional Cloudflare Worker for aggregate usage numbers
```

### Design decisions worth knowing

- **Runs locally by design** — zero server/compute cost; audio never leaves the machine.
- **Live streaming, accurate timestamps** — rough segments stream from
  faster-whisper for instant feedback; WhisperX then aligns word-level timing.
- **Validate before compute; delete audio after** — cheap checks first; no storage.
- **Standard vs Fast** maps to CPU vs NVIDIA GPU, named for the user's outcome.
- **Consent-based, anonymous telemetry** — off unless the user agrees *and* an
  endpoint is configured; collects only counts, never content.

---

## Usage numbers for your resume

Two ways to get them:

- **Local (no setup):** every install keeps its own counter; the app shows
  "X transcripts, Y min" in the footer. Ask your volunteers for their numbers.
- **Central (opt-in):** deploy the Worker in `telemetry-server/` and set the two
  env vars; then `curl .../stats` returns total users, transcriptions, and hours.

> Built and open-sourced **Escriba**, a local transcription tool (Python, FastAPI,
> faster-whisper, WhisperX, ffmpeg) with live streaming results over Server-Sent
> Events and word-level timestamped export (SRT/VTT/JSON). Designed it to run
> entirely on the user's machine for zero server cost, with a usability-first,
> Nielsen-heuristics-based interface. Used by [N] volunteers to transcribe [X]
> hours of audio.

---

## License

MIT — see [LICENSE](LICENSE).
