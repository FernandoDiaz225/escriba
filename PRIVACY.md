# Privacy

Escriba is built to respect the people who use it. Here's exactly how it handles
your data — in plain language.

## Your audio and transcripts never leave your computer

All transcription happens locally, on your own machine. Your audio files and the
transcripts they produce are **never uploaded anywhere**. The audio is deleted
from temporary storage as soon as a transcript is produced; the transcript stays
on your computer.

## Anonymous usage stats (your choice)

To understand how Escriba is used and keep improving it, the app can share a small
amount of **anonymous** usage information. You choose whether to share this the
first time you run it, and the app works fully either way.

**If you agree, Escriba shares only:**

- an anonymous random ID for your installation (not linked to your name or email),
- the number of transcriptions you've run,
- the total minutes of audio processed,
- the app version.

**Escriba never shares:**

- your audio,
- your transcripts or any of their text,
- file names,
- your name, email, IP address, or any other personal information.

This is sent only when both (a) you have agreed and (b) a collection endpoint has
been configured by the person who gave you Escriba. If either isn't true, nothing
is ever sent.

## Turning it off

You can decline when first asked ("Use without sharing"). To change your mind
later, edit the file `config.json` in the `.escriba` folder in your home directory
and set `"consent": false`, or delete that file to be asked again.

## A note to anyone deploying Escriba

If you turn on telemetry, keep this document truthful: the data your endpoint
receives must match the list above exactly. Don't collect more than you disclose.
