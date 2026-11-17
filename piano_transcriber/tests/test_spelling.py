from ptx.spelling import speller, parse_key


def test_g_major_spelling():
    sp = speller(parse_key('G'))
    names = {m: sp(m).nameWithOctave for m in (66, 63, 68, 61, 70, 65, 59)}
    assert names == {66: 'F#4', 63: 'D#4', 68: 'G#4', 61: 'C#4', 70: 'B-4', 65: 'F4', 59: 'B3'}


def test_flat_and_minor_keys():
    sp = speller(parse_key('Bb'))
    assert sp(63).name == 'E-' and sp(70).name == 'B-'
    sp = speller(parse_key('e minor'))            # relative major G
    assert sp(63).name == 'D#'
