"""Audio processing — the workbench behind the platform.

Two different jobs, two different tools (this is the key design decision):

  * TRANSCRIPTION PREP (automatic, no human needed): normalize + high-pass +
    light broadband denoise via ffmpeg. Goal = clear speech for Whisper, NOT a
    pretty master. Safe to run unattended.

  * LISTENING MASTER (human-in-the-loop): SoX noise-print reduction, where a
    person picks a silent region as the noise sample and tunes the amount, with
    an A/B preview against the original. This is the professional method and it
    is deliberately conservative — research shows over-reduction adds artifacts.

UNBREAKABLE RULE (every archival source agrees): never modify the original.
Every function writes a NEW file and leaves the source untouched.

The two knobs to tune by ear on a real tape are marked  >>> TUNE <<<.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def probe_seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            capture_output=True, text=True, check=True)
        return float(out.stdout.strip() or 0.0)
    except Exception:
        return 0.0


# --------------------------------------------------------------------------
# Join Side A + Side B  (no nuance needed — concatenation is just correct)
# --------------------------------------------------------------------------
def join_sides(side_a: Path, side_b: Path, dest: Path) -> Path:
    """Concatenate two audio files into one. Re-encodes to a common format so
    mismatched inputs (different codecs/rates) join cleanly."""
    dest = dest.with_suffix(".wav")
    _run(["ffmpeg", "-y", "-i", str(side_a), "-i", str(side_b),
          "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
          "-map", "[out]", "-ar", "44100", "-ac", "1",
          "-loglevel", "error", str(dest)])
    return dest


# --------------------------------------------------------------------------
# Transcription prep  (automatic; tuned for Whisper, not for listening)
# --------------------------------------------------------------------------
def prep_for_transcription(src: Path, dest: Path) -> Path:
    """Light, safe cleanup that helps speech recognition without destroying the
    consonant detail Whisper relies on. Runs unattended."""
    dest = dest.with_suffix(".wav")
    # highpass=80  -> remove rumble below the human voice
    # afftdn=nr=12 -> GENTLE broadband denoise (ffmpeg default; do not crank)
    # loudnorm     -> consistent speech level
    af = "highpass=f=80,afftdn=nr=12:nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
    _run(["ffmpeg", "-y", "-i", str(src), "-af", af,
          "-ar", "16000", "-ac", "1", "-loglevel", "error", str(dest)])
    return dest


# --------------------------------------------------------------------------
# Listening master  (human-in-the-loop, SoX noise-print method)
# --------------------------------------------------------------------------
def make_noise_profile(src: Path, start: float, end: float, prof: Path) -> Path:
    """Extract a noise sample from a silent region [start,end] and build a SoX
    noise profile from it. The user picks this region — that's the whole point."""
    if not have("sox"):
        raise RuntimeError("SoX isn't installed. Run setup again, or: brew install sox")
    noise_wav = prof.with_suffix(".noise.wav")
    dur = max(0.2, end - start)
    _run(["ffmpeg", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
          "-ar", "44100", "-ac", "1", "-loglevel", "error", str(noise_wav)])
    _run(["sox", str(noise_wav), "-n", "noiseprof", str(prof)])
    noise_wav.unlink(missing_ok=True)
    return prof


def restore_master(src: Path, prof: Path, dest: Path,
                   amount: float = 0.21, highpass: int = 60,
                   dehum: bool = True, gentle: bool = False) -> Path:
    """Produce a listening master following the professional order of operations.

    Pros peel problems off in sequence, denoising LAST, because steady hiss is
    handled after tonal/structural problems are gone (iZotope's documented
    workflow). Our achievable chain on ffmpeg + SoX:

        1) high-pass        -> remove sub-voice rumble
        2) dehum (optional) -> notch out 60 Hz mains hum + harmonics (US tapes)
        3) denoise          -> SoX profile-based reduction, applied LAST

    'gentle' runs the denoise as TWO lighter passes instead of one hard pass —
    the professional trick for avoiding the watery/robotic artifact that comes
    from over-reducing in a single hit.

      >>> TUNE <<<  amount   (0.2-0.3 is the practitioners' sweet spot)
      >>> TUNE <<<  highpass (50-80 Hz typical for voice)
    """
    if not have("sox"):
        raise RuntimeError("SoX isn't installed. Run setup again, or: brew install sox")
    dest = dest.with_suffix(".wav")

    # 1) + 2) high-pass, then dehum via harmonic notch filters at 60 Hz.
    #    anequalizer notches the mains fundamental and its first few harmonics.
    af = f"highpass=f={highpass}"
    if dehum:
        notches = ",".join(
            f"equalizer=f={60*k}:t=q:w=12:g=-22" for k in (1, 2, 3, 4)
        )
        af = f"{af},{notches}"
    pre = dest.with_suffix(".pre.wav")
    _run(["ffmpeg", "-y", "-i", str(src), "-af", af,
          "-ar", "44100", "-ac", "1", "-loglevel", "error", str(pre)])

    # 3) denoise LAST — one pass, or two gentler passes for fewer artifacts.
    if gentle:
        soft = max(0.05, amount * 0.6)
        mid = dest.with_suffix(".p1.wav")
        _run(["sox", str(pre), str(mid), "noisered", str(prof), str(soft)])
        _run(["sox", str(mid), str(dest), "noisered", str(prof), str(soft),
              "gain", "-n", "-3"])
        mid.unlink(missing_ok=True)
    else:
        _run(["sox", str(pre), str(dest), "noisered", str(prof), str(amount),
              "gain", "-n", "-3"])
    pre.unlink(missing_ok=True)
    return dest


def to_mp3(src: Path, dest: Path) -> Path:
    """Export a shareable MP3 of a master."""
    dest = dest.with_suffix(".mp3")
    _run(["ffmpeg", "-y", "-i", str(src), "-codec:a", "libmp3lame",
          "-qscale:a", "2", "-loglevel", "error", str(dest)])
    return dest
