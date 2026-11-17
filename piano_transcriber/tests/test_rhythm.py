import numpy as np
from ptx.notes import Note
from ptx.rhythm import (cluster_onsets, track_grid, quantize_pos, quantize_notes,
                        estimate_period, merge_rolled_chords, finalize_durations)


def _grid_times(n, period, t0=1.0, rit_from=None, rit_factor=1.0):
    t, p, out = t0, period, []
    for k in range(n):
        out.append(t)
        if rit_from is not None and k >= rit_from:
            p *= rit_factor
        t += p
    return np.array(out)


def test_steady_tempo_tracks_exactly():
    times = _grid_times(60, 0.3)
    events = cluster_onsets(list(times[::2]) + list(times[1::3]))  # gaps in the onsets
    grid, res = track_grid(events, 0.3, events[0], 0)
    for k, t in enumerate(times):
        assert abs(grid.pos(t) - k) < 0.01


def test_ritardando_keeps_barlines():
    times = _grid_times(80, 0.3, rit_from=60, rit_factor=1.03)  # slows down ~ +80% by the end
    grid, _ = track_grid(list(times), 0.3, times[0], 0)
    assert all(abs(grid.pos(t) - k) < 0.05 for k, t in enumerate(times))


def test_quantize_prefers_coarsest_level():
    assert quantize_pos(3.04) == 3.0
    assert quantize_pos(2.47) == 2.5
    assert quantize_pos(0.26) == 0.25          # 32nd note in eighth-note units
    assert quantize_pos(0.74) == 0.75


def test_estimate_period_ignores_subdivisions():
    times = _grid_times(40, 0.3)
    ev = list(times) + [t + 0.15 for t in times[::7]]
    assert abs(estimate_period(sorted(ev)) - 0.3) < 0.01


def test_rolled_chord_merged_but_fast_run_kept():
    roll = [Note(10.0, 12.0, 43), Note(10.1, 12.1, 50), Note(10.2, 12.0, 55), Note(10.3, 12.2, 67)]
    run = [Note(20.0, 20.07, 72), Note(20.075, 20.15, 75), Note(20.15, 21.0, 79)]
    out = merge_rolled_chords(roll + run)
    assert all(n.onset_s == 10.0 and n.rolled for n in out if n.pitch in (43, 50, 55, 67))
    assert sorted(n.onset_s for n in out if n.pitch in (72, 75, 79)) == [20.0, 20.075, 20.15]


def test_durations_legato_and_clip():
    a = Note(0, 0, 60, onset_q=0, dur_q=0.75, hand='R')   # nearly reaches next note -> extend
    b = Note(0, 0, 62, onset_q=1, dur_q=3.0, hand='R')    # overlaps next note -> clip
    c = Note(0, 0, 64, onset_q=2, dur_q=1.0, hand='R')
    finalize_durations([a, b, c], measure=6)
    assert (a.dur_q, b.dur_q, c.dur_q) == (1, 1, 1)
