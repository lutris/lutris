#!/usr/bin/env python3
"""Makes the default navigation sounds of Big Picture mode.

The sounds are a few soft, low notes: sine waves with a trace of the octave
above, which swell in and die away. They are meant to be felt more than
heard, as they are played hundreds of times in a session. Nothing is
sampled or recorded.

Run it from anywhere to write the sound pack anew:

    bigpicture/tools/make_sounds.py

It needs ffmpeg, built with libvorbis, to encode the files. The Ogg files it
writes differ in their bytes from one version of the encoder to the next,
but not in what is heard.
"""

import argparse
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave
from typing import NamedTuple

SAMPLE_RATE = 44100

# Vorbis at this many bits per second is transparent for sounds this simple.
BIT_RATE = "96k"

# The notes are written quietly, which leaves most of a file's range unused.
# They are stored this much louder, and the pack is played this much quieter
# to make up for it: the volume in its pack.json.
STORED_GAIN = 7.49
PACK_VOLUME = 0.13
PACK_NAME = "Default"

# A note swells in over this long instead of striking, and its tail is eased
# to nothing over this long, so that nothing clicks. In seconds.
ATTACK = 0.012
RELEASE = 0.04

# How much of the octave above is mixed in. It adds warmth, and keeps low
# notes audible on small speakers.
OCTAVE_LEVEL = 0.12

# 16-bit samples.
SAMPLE_BYTES = 2
FULL_SCALE = 32767

# The pitches used, in Hz.
G3, F3 = 196.0, 174.6
C4, D4, E4, G4, A4, B4 = 261.6, 293.7, 329.6, 392.0, 440.0, 493.9
C5, D5, E5 = 523.3, 587.3, 659.3


class Note(NamedTuple):
    start: float  # when it begins, in seconds
    pitch: float  # in Hz
    length: float  # in seconds
    loudness: float  # of full scale, before STORED_GAIN
    fade: float  # how fast it dies away: the rate of its exponential decay


SOUNDS = {
    # The everyday sounds: one muted note each.
    "move": [Note(0.0, G4, 0.11, 0.040, 38.0)],
    "key": [Note(0.0, C5, 0.07, 0.028, 60.0)],
    "tab": [Note(0.0, E4, 0.16, 0.045, 24.0)],
    # Two notes that melt into each other, rising to confirm...
    "select": [Note(0.0, G4, 0.26, 0.045, 16.0), Note(0.06, D5, 0.30, 0.040, 14.0)],
    "toggle": [Note(0.0, B4, 0.18, 0.034, 24.0), Note(0.05, E5, 0.22, 0.030, 20.0)],
    # ...and falling to step back.
    "back": [Note(0.0, A4, 0.22, 0.042, 18.0), Note(0.06, D4, 0.28, 0.042, 15.0)],
    # An open fifth, like a breath.
    "open": [Note(0.0, D4, 0.32, 0.034, 11.0), Note(0.0, A4, 0.32, 0.028, 12.0)],
    # A slow chime for the one moment worth marking.
    "launch": [
        Note(0.00, C4, 0.90, 0.040, 4.5),
        Note(0.11, G4, 0.80, 0.036, 4.5),
        Note(0.22, C5, 0.75, 0.032, 4.5),
        Note(0.33, E5, 0.70, 0.028, 4.5),
    ],
    # Low and unhurried, not an alarm.
    "error": [Note(0.0, G3, 0.34, 0.060, 9.0), Note(0.13, F3, 0.40, 0.060, 8.0)],
}


def ease(position: float) -> float:
    """From 0 to 1 as the position goes from 0 to 1, gently at both ends."""
    return 0.5 - 0.5 * math.cos(math.pi * min(max(position, 0.0), 1.0))


def render(notes: list[Note]) -> list[float]:
    """The samples of a sound, from -1 to 1."""
    seconds = max(note.start + note.length for note in notes)
    samples = [0.0] * int(seconds * SAMPLE_RATE)

    for note in notes:
        first = int(note.start * SAMPLE_RATE)
        count = min(int(note.length * SAMPLE_RATE), len(samples) - first)

        for index in range(count):
            time = index / SAMPLE_RATE
            swell = ease(index / (ATTACK * SAMPLE_RATE))
            tail = ease((count - index) / (RELEASE * SAMPLE_RATE))
            envelope = swell * tail * math.exp(-time * note.fade)

            phase = math.tau * note.pitch * time
            tone = math.sin(phase) + OCTAVE_LEVEL * math.sin(2.0 * phase)

            samples[first + index] += tone * envelope * note.loudness * STORED_GAIN

    return samples


def write_wav(path: str, samples: list[float]) -> None:
    with wave.open(path, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(SAMPLE_BYTES)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(b"".join(struct.pack("<h", round(sample * FULL_SCALE)) for sample in samples))


def encode(wav_path: str, ogg_path: str) -> None:
    command = ["ffmpeg", "-loglevel", "error", "-y", "-i", wav_path]
    # Nothing that changes from one run to the next goes into the file.
    command += ["-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact"]
    command += ["-c:a", "libvorbis", "-b:a", BIT_RATE, ogg_path]

    subprocess.run(command, check=True)


def main() -> int:
    source_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    default_dir = os.path.join(source_root, "share", "lutris", "bigpicture", "sounds", "default")

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("directory", nargs="?", default=default_dir, help="where to write the pack (%(default)s)")
    parser.add_argument("--wav", action="store_true", help="write WAV files, which takes no ffmpeg")
    options = parser.parse_args()

    os.makedirs(options.directory, exist_ok=True)

    for name, notes in SOUNDS.items():
        samples = render(notes)
        peak = max(abs(sample) for sample in samples)

        if peak > 1.0:
            print(f"{name} is too loud to store: it peaks at {peak:.2f} of full scale", file=sys.stderr)

            return 1

        if options.wav:
            write_wav(os.path.join(options.directory, name + ".wav"), samples)
        else:
            with tempfile.TemporaryDirectory() as scratch:
                wav_path = os.path.join(scratch, name + ".wav")
                write_wav(wav_path, samples)
                encode(wav_path, os.path.join(options.directory, name + ".ogg"))

        print(f"{name}: {len(samples) / SAMPLE_RATE:.2f} s, peak {peak:.2f}")

    with open(os.path.join(options.directory, "pack.json"), "w", encoding="utf-8") as manifest:
        json.dump({"name": PACK_NAME, "volume": PACK_VOLUME}, manifest)
        manifest.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
