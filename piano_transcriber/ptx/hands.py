"""Left/right hand separation for a single piano track."""
from itertools import groupby


def split_hands(notes, lh_init=48.0, rh_init=67.0, alpha=0.3, w_last=0.6, max_span=14,
                span_penalty=6.0, cross_penalty=4.0, min_gap=12):
    """Assign each note's `hand` ('L' or 'R').

    Notes sharing an onset are sorted by pitch and split at the index that minimises,
    for each hand, a mix of the distance to that hand's running centre (EMA) and the
    distance to the nearest pitch that hand played most recently (melodic / arpeggio
    continuity), plus penalties for a hand spanning more than `max_span` semitones and
    for a hand jumping across the other hand's last position. Requires `onset_q`.
    """
    cl, cr = lh_init, rh_init
    last_l, last_r = [lh_init], [rh_init]

    def hand_cost(p, centre, last):
        near = min(abs(p - q) for q in last)
        return (1 - w_last) * abs(p - centre) + w_last * near

    for _, grp in groupby(sorted(notes, key=lambda n: (n.onset_q, n.pitch)), key=lambda n: n.onset_q):
        grp = list(grp)
        ps = [n.pitch for n in grp]
        best, best_cost = 0, float('inf')
        for s in range(len(ps) + 1):
            lh, rh = ps[:s], ps[s:]
            cost = sum(hand_cost(p, cl, last_l) for p in lh) + sum(hand_cost(p, cr, last_r) for p in rh)
            for h in (lh, rh):
                if h and h[-1] - h[0] > max_span:
                    cost += span_penalty * (h[-1] - h[0] - max_span)
            # left-hand notes above the right hand's lowest recent note (or vice versa) cross over
            if lh and lh[-1] > min(last_r):
                cost += cross_penalty
            if rh and rh[0] < max(last_l):
                cost += cross_penalty
            if cost < best_cost:
                best, best_cost = s, cost
        for i, n in enumerate(grp):
            n.hand = 'L' if i < best else 'R'
        lh, rh = ps[:best], ps[best:]
        if lh:
            cl = (1 - alpha) * cl + alpha * (sum(lh) / len(lh)); last_l = lh
        if rh:
            cr = (1 - alpha) * cr + alpha * (sum(rh) / len(rh)); last_r = rh
        if cr - cl < min_gap:
            mid = (cr + cl) / 2
            cl, cr = mid - min_gap / 2, mid + min_gap / 2
    return notes
