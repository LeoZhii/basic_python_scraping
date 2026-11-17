#!/usr/bin/env python3
"""Transcribe a piano recording into sheet music (MIDI + MusicXML + PDF).

Example:
  python transcribe.py song.mp3 -o out/ --tempo 200 --tempo-unit eighth \
      --time-sig 6/8 --key G --pickup 2 --title "日落计数器"
"""
import argparse
import json
from pathlib import Path

import numpy as np

from ptx.notes import load_midi, save_midi
from ptx.rhythm import merge_rolled_chords, cluster_onsets, estimate_period, track_grid, quantize_notes, finalize_durations
from ptx.hands import split_hands
from ptx.spelling import detect_key, parse_key, speller
from ptx.score import build_score, export
from ptx.render import render

UNIT_QL = {'quarter': 1.0, 'eighth': 0.5, 'dotted-quarter': 1.5, 'half': 2.0}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('audio', help='input audio (mp3/wav/...) or an existing .mid to skip the model')
    ap.add_argument('-o', '--out', default='out', help='output directory')
    ap.add_argument('--name', help='output file stem (default: input stem)')
    ap.add_argument('--start', type=float, help='ignore audio before this time (s)')
    ap.add_argument('--end', type=float, help='ignore audio after this time (s)')
    ap.add_argument('--tempo', type=float, help='tempo number, e.g. 200')
    ap.add_argument('--tempo-unit', default='eighth', choices=UNIT_QL, help='note value the tempo refers to')
    ap.add_argument('--time-sig', default='6/8', help='time signature, e.g. 6/8, 3/4, 4/4')
    ap.add_argument('--key', help='key, e.g. G, Bb, "e minor" (default: detect)')
    ap.add_argument('--pickup', type=float, default=0,
                    help='number of tatums (eighths for x/8, quarters... see README) before the first downbeat')
    ap.add_argument('--grid', default='1,0.5,0.25', help='allowed subdivisions of the tatum, coarsest first')
    ap.add_argument('--title', help='score title (default: input file name)')
    ap.add_argument('--subtitle', help='line under the title, e.g. an English title')
    ap.add_argument('--composer', help='printed top right, e.g. the band or composer')
    ap.add_argument('--arranger', help='printed under the composer as "Arr. <name>"')
    ap.add_argument('--paper', default='a4', choices=['a4', 'letter'], help='paper size for the PDF')
    ap.add_argument('--no-pdf', action='store_true')
    a = ap.parse_args(argv)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    src = Path(a.audio)
    stem = a.name or src.stem

    # 1. audio -> notes
    if src.suffix.lower() in ('.mid', '.midi'):
        notes, pedals = load_midi(src)
    else:
        from ptx.model import transcribe_transkun
        notes, pedals = transcribe_transkun(src)
        save_midi(notes, out / f'{stem}.raw.mid', pedals)
    if a.start is not None:
        notes = [n for n in notes if n.onset_s >= a.start]
    if a.end is not None:
        notes = [n for n in notes if n.onset_s <= a.end]
    if not notes:
        raise SystemExit('no notes found')

    notes = merge_rolled_chords(notes)

    # 2. rhythm: tatum = denominator of the time signature (eighth for x/8)
    num, den = (int(x) for x in a.time_sig.split('/'))
    tatum_ql = 4 / den
    events = cluster_onsets([n.onset_s for n in notes])
    if a.tempo:
        period = 60.0 / a.tempo * (tatum_ql / UNIT_QL[a.tempo_unit])
    else:
        period = estimate_period(events)
    measure_tatums = num
    # music begins `pickup` tatums before the first downbeat; measure 1 is padded to full length
    anchor_index = int(round((measure_tatums - a.pickup) % measure_tatums)) if a.pickup else 0
    grid, res = track_grid(events, period, events[0], anchor_index)
    levels = tuple(float(x) for x in a.grid.split(','))
    quantize_notes(notes, grid, levels=levels)

    # 3. hands, key, spelling
    split_hands(notes)
    pedals_q = [(grid.pos(pd.start_s), grid.pos(pd.end_s)) for pd in pedals]
    finalize_durations(notes, measure=measure_tatums, pedals_q=pedals_q)
    k = parse_key(a.key) if a.key else detect_key(notes)
    spell = speller(k)

    # 4. score
    tempo_number = a.tempo or round(60.0 / period * tatum_ql / UNIT_QL[a.tempo_unit])
    title = a.title or stem
    sc = build_score(notes, k, spell, a.time_sig, tempo_number, UNIT_QL[a.tempo_unit],
                     title, a.composer, a.arranger, a.subtitle, a.paper)
    xml = out / f'{stem}.musicxml'
    export(sc, xml, out / f'{stem}.mid')
    pages = None
    if not a.no_pdf:
        pages = render(xml, out / f'{stem}.pdf', png_prefix=str(out / f'{stem}_page'), paper=a.paper,
                       title=title, subtitle=a.subtitle, composer=a.composer, arranger=a.arranger)

    report = {
        'notes': len(notes), 'pedals': len(pedals), 'key': str(k),
        'tatum_period_s_initial': round(period, 4),
        'grid_residual_ms_median': round(float(np.median(np.abs(res))) * 1000, 1) if len(res) else None,
        'grid_residual_ms_p95': round(float(np.percentile(np.abs(res), 95)) * 1000, 1) if len(res) else None,
        'measures': len(sc.parts[0].getElementsByClass('Measure')),
        'pdf_pages': pages,
    }
    (out / f'{stem}.report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return notes, grid


if __name__ == '__main__':
    main()
