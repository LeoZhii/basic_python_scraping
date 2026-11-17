from ptx.notes import Note
from ptx.hands import split_hands


def test_arpeggio_under_melody():
    notes, truth = [], []
    melody = [74, 72, 71, 67, 69, 71]               # D5 C5 B4 G4 A4 B4 on beats
    arp = [43, 50, 55, 59, 55, 45]                  # G2 D3 G3 B3 G3 A2 eighths (B3 is LH!)
    for i, p in enumerate(arp):
        notes.append(Note(0, 0, p, onset_q=i)); truth.append('L')
    for i, p in enumerate(melody[::2]):
        notes.append(Note(0, 0, p, onset_q=2 * i)); truth.append('R')
    split_hands(notes)
    assert [n.hand for n in notes] == truth


def test_chord_split_by_register():
    notes = [Note(0, 0, p, onset_q=0) for p in (36, 43, 64, 67, 72)]
    split_hands(notes)
    assert [n.hand for n in notes] == ['L', 'L', 'R', 'R', 'R']
