"""Build a two-staff music21 score from quantized, hand-assigned notes."""
from fractions import Fraction
from itertools import groupby

from music21 import (stream, note, chord, meter, key as m21key, clef, tempo, duration,
                     metadata, layout, instrument, expressions)


def _ql(eighths):
    return Fraction(eighths).limit_denominator(64) / 2


def _hand_part(notes, hand, spell, measure_eighths, total_eighths):
    events = []
    hn = sorted((n for n in notes if n.hand == hand), key=lambda n: (n.onset_q, n.pitch))
    groups = [(on, list(g)) for on, g in groupby(hn, key=lambda n: n.onset_q)]
    for i, (on, g) in enumerate(groups):
        nxt = groups[i + 1][0] if i + 1 < len(groups) else total_eighths
        dur = min(max(n.dur_q for n in g), nxt - on)
        dur = max(dur, 0.25)
        events.append((on, dur, sorted({n.pitch for n in g}), any(n.rolled for n in g)))
    part = stream.Part()
    t = 0.0
    for on, dur, pitches, rolled in events:
        if on > t:
            r = note.Rest(); r.quarterLength = _ql(on - t); part.insert(_ql(t), r)
        if len(pitches) == 1:
            el = note.Note(spell(pitches[0]))
        else:
            el = chord.Chord([spell(p) for p in pitches])
            if rolled:
                el.expressions.append(expressions.ArpeggioMark())
        el.quarterLength = _ql(dur)
        part.insert(_ql(on), el)
        t = on + dur
    if t < total_eighths:
        r = note.Rest(); r.quarterLength = _ql(total_eighths - t); part.insert(_ql(t), r)
    return part


def build_score(notes, k, spell, time_sig='6/8', tempo_bpm=200, tempo_unit_ql=0.5,
                title=None, composer=None, arranger=None):
    ts = meter.TimeSignature(time_sig)
    measure_eighths = ts.barDuration.quarterLength * 2
    end = max(n.onset_q + n.dur_q for n in notes)
    n_measures = int(-(-end // measure_eighths))
    total = n_measures * measure_eighths

    sc = stream.Score()
    md = metadata.Metadata()
    md.title = title or ''
    if composer:
        md.composer = composer
    if arranger:
        md.addContributor(metadata.Contributor(role='arranger', name=arranger))
    sc.metadata = md

    for hand, cl in (('R', clef.TrebleClef()), ('L', clef.BassClef())):
        p = _hand_part(notes, hand, spell, measure_eighths, total)
        p.insert(0, cl)
        p.insert(0, m21key.KeySignature(k.sharps))
        p.insert(0, meter.TimeSignature(time_sig))
        if hand == 'R':
            p.insert(0, tempo.MetronomeMark(number=tempo_bpm,
                                            referent=duration.Duration(tempo_unit_ql)))
        p.partName = ''
        p.partAbbreviation = ''
        sc.insert(0, p)
    sc.insert(0, layout.StaffGroup([sc.parts[0], sc.parts[1]], symbol='brace', barTogether=True))
    sc = sc.makeNotation()
    return sc


def export(sc, musicxml_path, midi_path=None):
    sc.write('musicxml', fp=str(musicxml_path))
    if midi_path:
        sc.write('midi', fp=str(midi_path))
