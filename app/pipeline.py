"""The transcription work, now STREAMING.

Why two engines:
  * faster-whisper streams segments as they're decoded -> we push each one to
    the UI live, so the user can watch it work and bail early on a bad tape.
  * WhisperX then does a second alignment pass for accurate WORD-level
    timestamps (the differentiator), and we swap those into the final result.

The worker runs in a background thread and communicates with the SSE endpoint
through job["queue"]. Design choices tagged inline:
  [GUARDRAIL] cheap checks before expensive compute
  [PRIVACY]   the audio is deleted as soon as the job ends
  [UX]        Standard/Fast maps to CPU/GPU; live segments give early feedback
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .config import MAX_SECONDS, MODEL_SIZE, BEAM_SIZE
from . import telemetry, storage


def _probe_seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip() or 0.0)
    except Exception:
        return 0.0


def _friendly(err: str) -> str:
    low = err.lower()
    if "faster_whisper" in low or ("whisperx" in low and "import" in low) or "no module" in low:
        return "The transcription engine isn't installed yet. Run setup again, or: pip install -r requirements.txt"
    if "ffmpeg" in low or "ffprobe" in low:
        return "Couldn't read the audio — make sure ffmpeg is installed."
    if "cuda" in low or "nvidia" in low or "cudnn" in low:
        return "Fast mode needs an NVIDIA graphics card. Try Standard mode instead."
    if "longer than" in low:
        return err
    return "Something went wrong while transcribing. Please try again."


def run_pipeline(job: dict, raw_path: Path, mode: str, language: str) -> None:
    q = job["queue"]
    emit = q.put
    try:
        # [UX] Standard = CPU/int8 (any computer); Fast = CUDA/float16 (NVIDIA only)
        device, compute_type = ("cuda", "float16") if mode == "fast" else ("cpu", "int8")

        emit({"type": "stage", "stage": "Preparing your audio…", "progress": 4})
        duration = _probe_seconds(raw_path)
        if duration and duration > MAX_SECONDS:                  # [GUARDRAIL]
            raise ValueError("That recording is longer than 4 hours.")

        from faster_whisper import WhisperModel

        lang = None if language == "auto" else language
        model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute_type)

        emit({"type": "stage", "stage": "Transcribing…", "progress": 8})
        seg_iter, info = model.transcribe(str(raw_path), language=lang, beam_size=BEAM_SIZE)
        total = float(getattr(info, "duration", 0) or duration or 0)
        detected = getattr(info, "language", None) or lang or "en"
        emit({"type": "language", "language": detected})

        # ---- stream rough segments live ------------------------------------
        collected = []
        for seg in seg_iter:
            if job.get("cancel"):                                # [UX] stop early
                job.update(status="cancelled")
                emit({"type": "cancelled"})
                return
            item = {"start": round(seg.start, 2), "end": round(seg.end, 2),
                    "text": (seg.text or "").strip()}
            collected.append(item)
            prog = 8 + (min(seg.end / total, 1.0) * 77 if total else 0)   # 8..85
            emit({"type": "segment", **item, "progress": round(prog, 1)})

        # ---- alignment pass: precise word-level timestamps -----------------
        emit({"type": "stage", "stage": "Aligning word-level timestamps…", "progress": 88})
        segments = [{**c, "words": []} for c in collected]       # fallback
        try:
            import whisperx
            audio = whisperx.load_audio(str(raw_path))
            amodel, meta = whisperx.load_align_model(language_code=detected, device=device)
            aligned = whisperx.align(collected, amodel, meta, audio, device,
                                     return_char_alignments=False)
            segments = []
            for s in aligned["segments"]:
                segments.append({
                    "start": round(float(s.get("start", 0.0)), 2),
                    "end": round(float(s.get("end", 0.0)), 2),
                    "text": (s.get("text") or "").strip(),
                    "words": [
                        {"word": w.get("word", ""),
                         "start": round(float(w.get("start", s.get("start", 0.0))), 2),
                         "end": round(float(w.get("end", s.get("end", 0.0))), 2)}
                        for w in s.get("words", [])
                    ],
                })
        except Exception:
            pass  # keep segment-level timing if alignment isn't available

        minutes = round((total or 0) / 60, 2)
        # Save to the permanent library (+ shared folder) so work is never lost.
        record = storage.save_transcript(job.get("name", "transcript"),
                                         segments, detected, minutes)
        job.update(status="done", segments=segments, language=detected,
                   minutes=minutes, saved=record)
        telemetry.record_completion(minutes)                     # local count (+ping if opted in)
        emit({"type": "done", "progress": 100, "saved_to_output": record.get("saved_to_output")})

    except Exception as e:
        job.update(status="error", error=_friendly(str(e)))
        emit({"type": "error", "message": job["error"]})
    finally:
        try:
            raw_path.unlink(missing_ok=True)                     # [PRIVACY]
        except OSError:
            pass
