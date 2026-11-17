"""Key handling and key-aware enharmonic spelling."""
from music21 import key as m21key, pitch as m21pitch

STEP_SEMI = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
# chromatic offsets from the major tonic -> (scale degree index 0..6, alteration)
CHROMATIC = {1: (0, +1), 3: (2, -1), 6: (3, +1), 8: (4, +1), 10: (6, -1)}
DIATONIC = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}


def detect_key(notes):
    from music21 import stream, note
    s = stream.Stream()
    for n in notes:
        x = note.Note(n.pitch)
        x.quarterLength = max(0.25, (n.offset_s - n.onset_s) * 2)
        s.append(x)
    return s.analyze('key')


def parse_key(name):
    """'G', 'e', 'Bb', 'g minor' -> music21 Key."""
    name = name.strip()
    if ' ' in name:
        tonic, mode = name.split()[0], name.split()[1].lower()
        return m21key.Key(tonic.replace('b', '-') if len(tonic) > 1 else tonic, mode)
    tonic = name[0] + name[1:].replace('b', '-')
    return m21key.Key(tonic)


def speller(k):
    """Return f(midi) -> music21 Pitch spelled for key `k`."""
    major = k if k.mode == 'major' else k.relative
    scale = [major.pitchFromDegree(d) for d in range(1, 8)]
    tonic_pc = scale[0].pitchClass

    def spell(midi):
        rel = (midi - tonic_pc) % 12
        if rel in DIATONIC:
            deg, delta = DIATONIC[rel], 0
        else:
            deg, delta = CHROMATIC[rel]
        base = scale[deg]
        alter = (base.accidental.alter if base.accidental else 0) + delta
        octave = (midi - STEP_SEMI[base.step] - alter) / 12 - 1
        p = m21pitch.Pitch(base.step)
        if alter:
            p.accidental = m21pitch.Accidental(alter)
        p.octave = int(round(octave))
        assert p.midi == midi, (midi, p)
        return p
    return spell
