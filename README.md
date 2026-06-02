# Escriba — Tape Ministry Workbench

A free, local platform built for Apóstol Bernabé Garcia's tape ministry. It helps
a small team turn a large cassette archive into clean **transcripts** and
good-sounding **listening masters**, as efficiently as possible — with audio
prep, quick quality audits, and an organized library, all in one place.

Everything runs on your own computer. Your audio and transcripts are **never
uploaded** — transcription is free and private. Finished work is saved
automatically so it's never lost, and can also sync to a shared team folder.

---

## The four stations

| Tab | What it does |
|-----|--------------|
| **Prepare** | Join a split tape (Side A + Side B) into one file and apply a light, automatic cleanup tuned for transcription. Originals are never changed. |
| **Transcribe** | Produce a word-level timestamped transcript, shown **live** as it's recognized so you can stop a bad tape early. Exports TXT/SRT/VTT/JSON. |
| **Master** | Restore a listening-quality version. Hands-on by design: pick a quiet moment so Escriba learns *that tape's* noise, tune, and compare against the original. Exports WAV + MP3. |
| **Library** | Quick tape audits (flag quality before transcribing), plus every transcript, master, and audit you've made — and the shared-folder setting. |

There's a built-in **Help** tab with an About section and step-by-step How-To.

---

## Why two different audio paths (the key design decision)

Transcription and listening quality are different jobs, so Escriba uses the right
tool for each:

- **Transcription prep** is automatic and light — normalize, cut rumble, gentle
  broadband denoise (ffmpeg). Whisper needs clear speech, not a pretty master, and
  aggressive cleanup actually *hurts* recognition.
- **Listening master** is human-in-the-loop using the professional noise-print
  method (SoX): you select a silent region, Escriba samples that tape's specific
  noise, removes only that, and you A/B against the original. There's deliberately
  no one-click "master" button, because every tape's noise differs and
  over-reduction adds artifacts — this mirrors what audio archivists actually do.

---

## Install (macOS)

1. Install **Python 3** (python.org).
2. Download/clone this project, open the folder in Terminal.
3. `chmod +x setup.command start.command` (one time — zips drop the run flag).
4. `./setup.command` — installs ffmpeg, SoX, and the Python packages (the
   transcription engine is several GB; first run takes a while).
5. `./start.command` — launches the app and opens your browser. Use this every time.

**Windows:** double-click `setup.bat`, then `start.bat`.

**Manual:** `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 run.py` (needs `ffmpeg` and `sox` on PATH).

---

## A typical tape, start to finish

1. **Audit it** (Library) — listen for a few seconds, flag quality. Catch bad tapes before wasting time.
2. **Prepare** — join Side A + B if split; light cleanup on; click Prepare.
3. **Transcribe** — pick language, watch it live, download the format you need.
4. **Master** (only if worth it) — restore a clean listening version for tapes people will actually hear.

---

## Language support

Pick Spanish, English, or auto-detect. If a tape has a live interpreter, choose
the language you want to keep — best results if that language is on its own track.
The live transcription view helps you catch a bad mixed tape within seconds.

---

## Project layout

```
escriba/
├── setup.command / setup.bat     # one-time setup (ffmpeg + SoX + packages)
├── start.command / start.bat     # launch the app
├── run.py · requirements.txt · README.md · PRIVACY.md · LICENSE
├── app/
│   ├── main.py        # FastAPI: all stations, SSE streaming, library
│   ├── pipeline.py    # faster-whisper streaming + WhisperX alignment
│   ├── audio.py       # join / transcription-prep / SoX restoration
│   ├── storage.py     # transcripts, masters, audits, shared-folder copies
│   ├── telemetry.py   # local usage counter + opt-in anonymous ping
│   ├── exports.py     # TXT / SRT / VTT / JSON
│   └── config.py      # paths + guardrail constants
├── web/
│   └── index.html     # the whole interface (Nielsen-heuristics based)
└── telemetry-server/  # optional Cloudflare Worker for aggregate usage numbers
```

---

## Usability

The interface is built around Nielsen's heuristics: the four stations are always
visible as tabs (recognition over recall); the Master station shows the waveform
and a live before/after so you can *see* and *hear* system status; plain-language
labels and tooltips throughout; forgiving, reversible steps; and a Help tab with
About + How-To so nothing is mysterious.

---

## Honest status

Built fast, with informed sign-off. The structure, every endpoint, the audio
join, the transcription prep, the live streaming, and the library/storage are all
tested. The two things to verify on a real machine with a real Bernabé Garcia tape:
(1) the **WhisperX transcription** itself (needs the ML stack installed), and
(2) the **listening-master quality** — the two restoration knobs (noise-reduction
amount, low-end cut) should be tuned by ear on one test tape before doing the
archive, exactly as audio archivists recommend. Both knobs are clearly labeled in
`app/audio.py` (marked `>>> TUNE <<<`).

---

## License

MIT — see [LICENSE](LICENSE). Privacy details in [PRIVACY.md](PRIVACY.md).
