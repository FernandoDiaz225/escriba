"""Turn transcript segments into the downloadable formats.

The timestamped formats (SRT/VTT/JSON) are the whole point of the tool — they
carry the timing that plain ChatGPT-style transcription throws away.
"""

import json


def _stamp(seconds: float, sep: str) -> str:
    """Format a time as HH:MM:SS<sep>mmm. SRT uses ',', VTT uses '.'."""
    ms = int(round((seconds % 1) * 1000))
    whole = int(seconds)
    h, m, s = whole // 3600, (whole % 3600) // 60, whole % 60
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_txt(segments) -> str:
    lines = []
    for seg in segments:
        m, s = int(seg["start"]) // 60, int(seg["start"]) % 60
        lines.append(f"[{m:02d}:{s:02d}] {seg['text']}")
    return "\n".join(lines)


def to_srt(segments) -> str:
    blocks = []
    for i, seg in enumerate(segments, 1):
        blocks.append(
            f"{i}\n{_stamp(seg['start'], ',')} --> {_stamp(seg['end'], ',')}\n{seg['text']}\n"
        )
    return "\n".join(blocks)


def to_vtt(segments) -> str:
    body = "\n".join(
        f"{_stamp(seg['start'], '.')} --> {_stamp(seg['end'], '.')}\n{seg['text']}\n"
        for seg in segments
    )
    return "WEBVTT\n\n" + body


def to_json(segments, language: str) -> str:
    return json.dumps(
        {"tool": "Escriba", "model": "whisperx", "language": language, "segments": segments},
        ensure_ascii=False,
        indent=2,
    )


BUILDERS = {"txt": to_txt, "srt": to_srt, "vtt": to_vtt}
