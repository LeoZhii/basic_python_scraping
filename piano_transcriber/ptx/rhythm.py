"""Beat grid tracking and rhythmic quantization.

Positions are measured in eighth-note units (the "tatum") from the start of measure 1.
"""
from bisect import bisect_right
import numpy as np


def merge_rolled_chords(notes, max_gap=0.12, min_notes=3, hold=0.3, min_span=13, release_tol=0.35):
    """Collapse rolled (arpeggiated) chords onto their first onset.

    A roll is >= `min_notes` notes with rising pitch, each starting within `max_gap` s of the
    previous one, released together (within `release_tol` s) and still sounding `hold` s after
    the last one starts, spanning at least
    `min_span` semitones (fast runs within an octave, e.g. 32nd-note pickups held by the
    pedal, are kept as runs). Marks members with `rolled=True`.
    """
    notes = sorted(notes, key=lambda n: (n.onset_s, n.pitch))
    i = 0
    while i < len(notes):
        j = i
        while j + 1 < len(notes) and notes[j + 1].onset_s - notes[j].onset_s <= max_gap:
            j += 1
        grp = notes[i:j + 1]
        # distinct starts (notes within 20 ms count as one start, e.g. both hands together)
        starts = []
        for n in grp:
            if starts and n.onset_s - starts[-1][0].onset_s <= 0.02:
                starts[-1].append(n)
            else:
                starts.append([n])
        if len(starts) >= min_notes:
            means = [sum(n.pitch for n in st) / len(st) for st in starts]
            rising = all(a < b for a, b in zip(means, means[1:]))
            offs = [n.offset_s for n in grp]
            held = min(offs) >= grp[-1].onset_s + hold and max(offs) - min(offs) <= release_tol
            span = max(n.pitch for n in grp) - min(n.pitch for n in grp)
            if rising and held and span >= min_span:
                t0 = grp[0].onset_s
                for n in grp:
                    n.onset_s = t0
                    n.rolled = True
        i = j + 1
    return notes


def cluster_onsets(times, tol=0.03):
    """Merge onsets closer than `tol` seconds; returns sorted event times."""
    events = []
    for t in sorted(times):
        if events and t - events[-1][-1] <= tol:
            events[-1].append(t)
        else:
            events.append([t])
    return [float(np.median(e)) for e in events]


def estimate_period(events, lo=0.15, hi=0.6):
    """Tatum period estimate: the most common inter-onset interval in [lo, hi] (smoothed
    histogram mode), refined by least squares over intervals near small multiples of it.
    Sub-multiples explain every interval too, so a "best fit" criterion would pick them;
    the mode does not, as long as the tatum is the most frequent note value.
    """
    ioi = np.diff(events)
    sel = ioi[(ioi >= lo) & (ioi <= hi)]
    if len(sel) == 0:
        return 0.3
    bins = np.arange(lo, hi + 0.005, 0.005)
    h, _ = np.histogram(sel, bins)
    h = np.convolve(h, [1, 2, 3, 2, 1], mode='same')
    p0 = bins[np.argmax(h)] + 0.0025
    r = ioi / p0
    k = np.round(r)
    ok = (k >= 1) & (k <= 4) & (np.abs(r - k) < 0.1)
    return float(np.sum(ioi[ok] * k[ok]) / np.sum(k[ok] ** 2)) if ok.any() else float(p0)


class Grid:
    """Monotone mapping between seconds and tatum positions, built from tracked grid points."""

    def __init__(self, indices, times):
        self.k = np.asarray(indices, float)
        self.t = np.asarray(times, float)

    def pos(self, t):
        k, g = self.k, self.t
        if t <= g[0]:
            return k[0] + (t - g[0]) / (g[1] - g[0])
        if t >= g[-1]:
            return k[-1] + (t - g[-1]) / (g[-1] - g[-2])
        i = bisect_right(g, t) - 1
        return k[i] + (t - g[i]) / (g[i + 1] - g[i])

    def time(self, pos):
        return float(np.interp(pos, self.k, self.t))


def track_grid(events, period, anchor_time, anchor_index, window=0.22, beta=0.25,
               min_period_ratio=0.6, max_period_ratio=1.6):
    """Phase-locked tatum tracker.

    Starts at `anchor_time` (grid index `anchor_index`), predicts each next grid point
    one period ahead and snaps to the nearest onset within +-window*period, updating the
    period by an exponential moving average of the observed interval. Grid points with no
    onset are advanced by the current period. Handles gradual tempo change (ritardando).
    """
    ev = np.asarray(events)
    p0 = period
    p = period
    k, g = anchor_index, anchor_time
    ks, ts, residuals = [k], [g], []
    last = ev[-1] + 2 * p
    gap = 0  # tatums since the last matched onset
    while g < last:
        pred = g + p
        j = np.searchsorted(ev, pred)
        cand = [i for i in (j - 1, j) if 0 <= i < len(ev)]
        best = min(cand, key=lambda i: abs(ev[i] - pred)) if cand else None
        gap += 1
        if best is not None and abs(ev[best] - pred) <= window * p:
            err = ev[best] - pred
            residuals.append(err)
            g_new = ev[best]
            # observed period over the gap since the last match
            obs = (g_new - ts[-gap]) / gap if gap <= len(ts) else p
            p = (1 - beta) * p + beta * obs
            p = float(np.clip(p, p0 * min_period_ratio, p0 * max_period_ratio))
            gap = 0
        else:
            g_new = pred
        k += 1
        g = g_new
        ks.append(k)
        ts.append(g)
    # extend backwards from the anchor with the initial period (pickup / opening rests)
    first_k = 0 if anchor_index > 0 else -1
    pre_k = list(range(first_k, anchor_index))
    pre_t = [anchor_time - (anchor_index - kk) * period for kk in pre_k]
    grid = Grid(pre_k + ks, pre_t + ts)
    return grid, np.asarray(residuals)


def quantize_pos(pos, levels=(1.0, 0.5, 0.25), tol=0.12):
    """Snap to the coarsest subdivision that lies within `tol` tatums."""
    for L in levels:
        q = round(pos / L) * L
        if abs(pos - q) <= tol:
            return q
    L = levels[-1]
    return round(pos / L) * L


def quantize_notes(notes, grid, levels=(1.0, 0.5, 0.25), tol=0.12, min_dur=0.25):
    for n in notes:
        on = quantize_pos(grid.pos(n.onset_s), levels, tol)
        off = quantize_pos(grid.pos(n.offset_s), levels, tol)
        n.onset_q = on
        n.dur_q = max(min_dur, off - on)
    return notes


def finalize_durations(notes, levels=(1.0, 0.5), tol=0.3, legato_gap=1.0, measure=None, pedals_q=()):
    """Notation durations, per hand and per chord (notes sharing an onset).

    A chord lasts until its longest note's (coarsely snapped) release, but never past the
    next onset in the same hand; if it would stop less than `legato_gap` tatums before that
    onset, it is extended to it (sustain pedal and synth releases make raw offsets noisy).
    If the sustain pedal is down when the chord is released, the sound continues, so the
    chord is extended to the next onset in that hand (but not past the pedal release).
    """
    def pedal_end(t):
        for a, b in pedals_q:
            if a - 0.25 <= t <= b:
                return b
        return None

    from itertools import groupby
    for hand in ('L', 'R'):
        hn = sorted((n for n in notes if n.hand == hand), key=lambda n: (n.onset_q, n.pitch))
        groups = [(on, list(g)) for on, g in groupby(hn, key=lambda n: n.onset_q)]
        for i, (on, g) in enumerate(groups):
            off = max(quantize_pos(on + n.dur_q, levels, tol) for n in g)
            dur = max(off - on, min(n.dur_q for n in g))
            if i + 1 < len(groups):
                nxt = groups[i + 1][0]
                pe = pedal_end(on + dur)
                if pe is not None and pe > on + dur:
                    dur = max(dur, min(nxt, quantize_pos(pe, levels, tol)) - on)
                if dur > nxt - on or (nxt - on) - dur < legato_gap:
                    dur = nxt - on
            elif measure:
                # last note: run to the end of its measure at most
                dur = min(dur, (on // measure + 1) * measure - on) if dur > measure else dur
            for n in g:
                n.dur_q = dur
    return notes
