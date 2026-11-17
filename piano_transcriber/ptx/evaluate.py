"""Compare transcribed notes against a reference note list (CSV).

CSV columns: measure,onset_eighths,dur_eighths,pitch,hand  (pitch like D#4, B-4)
"""
import csv
from music21 import pitch as m21pitch


def load_reference(path, measure_tatums=6):
    ref = []
    with open(path) as f:
        for r in csv.DictReader(f):
            pos = (int(r['measure']) - 1) * measure_tatums + float(r['onset_eighths'])
            p = m21pitch.Pitch(r['pitch'])
            ref.append(dict(pos=pos, dur=float(r['dur_eighths']), midi=p.midi, name=r['pitch'], hand=r['hand']))
    return ref


def compare(notes, ref, spell=None, last_measure=None, measure_tatums=6):
    end = (last_measure or 10**6) * measure_tatums
    est = [n for n in notes if n.onset_q < end]
    pool = {}
    for n in est:
        pool.setdefault((n.onset_q, n.pitch), []).append(n)
    matched, hand_ok, dur_ok, spell_ok, missing = 0, 0, 0, 0, []
    for r in ref:
        cand = pool.get((r['pos'], r['midi']))
        if cand:
            n = cand.pop(0)
            matched += 1
            hand_ok += n.hand == r['hand']
            dur_ok += abs(n.dur_q - r['dur']) < 1e-6
            if spell:
                spell_ok += spell(n.pitch).nameWithOctave == r['name']
        else:
            missing.append(r)
    extra = [n for c in pool.values() for n in c]
    P = matched / max(1, len(est)); R = matched / max(1, len(ref))
    return {
        'ref_notes': len(ref), 'est_notes': len(est), 'matched': matched,
        'precision': round(P, 3), 'recall': round(R, 3),
        'f1': round(2 * P * R / max(1e-9, P + R), 3),
        'hand_acc': round(hand_ok / max(1, matched), 3),
        'dur_acc': round(dur_ok / max(1, matched), 3),
        'spelling_acc': round(spell_ok / max(1, matched), 3) if spell else None,
        'missing': [(r['pos'] // measure_tatums + 1, r['pos'] % measure_tatums, r['name']) for r in missing],
        'extra': [(n.onset_q // measure_tatums + 1, n.onset_q % measure_tatums, n.pitch) for n in extra],
    }


def onset_f1_seconds(notes, ref, t_measure1, tatum_s, t_max, tol=0.05):
    """Gate B: model accuracy in seconds, before any quantization."""
    import numpy as np, mir_eval
    r_on = np.array([t_measure1 + r['pos'] * tatum_s for r in ref])
    r_iv = np.stack([r_on, r_on + 0.1], 1)
    r_p = np.array([440 * 2 ** ((r['midi'] - 69) / 12) for r in ref])
    est = [n for n in notes if n.onset_s < t_max]
    e_on = np.array([n.onset_s for n in est])
    e_iv = np.stack([e_on, e_on + 0.1], 1)
    e_p = np.array([440 * 2 ** ((n.pitch - 69) / 12) for n in est])
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(r_iv, r_p, e_iv, e_p, onset_tolerance=tol, offset_ratio=None)
    return round(p, 3), round(r, 3), round(f, 3)
