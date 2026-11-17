"""Audio -> notes with a pretrained piano transcription model (Transkun by default)."""
from pathlib import Path

from .audio import load_audio
from .notes import Note, Pedal


def transcribe_transkun(audio_path, device='cpu', start=None, end=None, progress=True):
    import torch
    import moduleconf
    import transkun

    pkg = Path(transkun.__file__).parent / 'pretrained'
    conf_mgr = moduleconf.parseFromFile(str(pkg / '2.0.conf'))
    TransKun = conf_mgr['Model'].module.TransKun
    model = TransKun(conf=conf_mgr['Model'].config).to(device)
    ckpt = torch.load(str(pkg / '2.0.pt'), map_location=device, weights_only=False)
    model.load_state_dict(ckpt.get('best_state_dict', ckpt.get('state_dict')), strict=False)
    model.eval()
    torch.set_grad_enabled(False)

    audio = load_audio(audio_path, sr=model.fs, start=start, end=end)
    offset = float(start or 0.0)
    est = model.transcribe(torch.from_numpy(audio).to(device), discardSecondHalf=False)

    notes, pedals = [], []
    for n in est:
        if n.pitch > 0:
            notes.append(Note(n.start + offset, n.end + offset, int(n.pitch), int(n.velocity)))
        elif -n.pitch == 64:
            pedals.append(Pedal(n.start + offset, n.end + offset))
    notes.sort(key=lambda n: (n.onset_s, n.pitch))
    return notes, pedals
