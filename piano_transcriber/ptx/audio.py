import subprocess
import numpy as np


def load_audio(path, sr=44100, mono=False, start=None, end=None):
    """Decode any ffmpeg-readable file to float32 (frames, channels) at `sr`."""
    cmd = ['ffmpeg', '-v', 'error']
    if start is not None:
        cmd += ['-ss', str(start)]
    if end is not None:
        cmd += ['-to', str(end)]
    channels = 1 if mono else 2
    cmd += ['-i', str(path), '-ac', str(channels), '-ar', str(sr), '-f', 'f32le', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, channels).copy()
