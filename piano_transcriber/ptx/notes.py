from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Note:
    onset_s: float
    offset_s: float
    pitch: int
    velocity: int = 64
    # filled in by later stages
    onset_q: Optional[float] = None   # position in eighth notes from start of measure 1
    dur_q: Optional[float] = None     # duration in eighth notes
    hand: Optional[str] = None        # 'R' or 'L'
    rolled: bool = False              # member of a rolled (arpeggiated) chord


@dataclass
class Pedal:
    start_s: float
    end_s: float


def load_midi(path):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(str(path))
    notes, pedals = [], []
    for inst in pm.instruments:
        for n in inst.notes:
            notes.append(Note(n.start, n.end, n.pitch, n.velocity))
        down = None
        for cc in sorted((c for c in inst.control_changes if c.number == 64), key=lambda c: c.time):
            if cc.value >= 64 and down is None:
                down = cc.time
            elif cc.value < 64 and down is not None:
                pedals.append(Pedal(down, cc.time)); down = None
    notes.sort(key=lambda n: (n.onset_s, n.pitch))
    return notes, pedals


def save_midi(notes, path, pedals=()):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for n in notes:
        inst.notes.append(pretty_midi.Note(velocity=int(n.velocity), pitch=int(n.pitch),
                                           start=float(n.onset_s), end=float(max(n.offset_s, n.onset_s + 0.01))))
    for p in pedals:
        inst.control_changes.append(pretty_midi.ControlChange(64, 127, p.start_s))
        inst.control_changes.append(pretty_midi.ControlChange(64, 0, p.end_s))
    pm.instruments.append(inst)
    pm.write(str(path))
