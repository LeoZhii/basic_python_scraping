# piano_transcriber

Turn a recording of solo piano into sheet music: **MP3/WAV → MIDI → MusicXML → PDF**.

```
python transcribe.py song.mp3 -o out/ --time-sig 6/8 --pickup 2 \
    --title "日落计数器" --subtitle "Sunset Counter" --composer "莫非定律乐团 (More Feel)" --arranger "声不可测"
```

Outputs in `out/`:

| File | What it is |
|---|---|
| `song.raw.mid` | the model's note-for-note transcription (real timing, pedal) |
| `song.musicxml` | the score: open it in MuseScore to edit |
| `song.mid` | the quantized score as MIDI |
| `song.pdf`, `song_page1.png` | print-ready score (A4 or US Letter) and a page-1 preview |
| `song.report.json` | key, tempo fit, measure count |

## Pipeline

1. **Notes**: [Transkun](https://pypi.org/project/transkun/) piano transcription (notes, velocities, sustain pedal). Runs on CPU; about 1.5 min for a 4.5 min recording.
2. **Rolled chords**: notes that start in quick succession with rising pitch, span more than an octave and are released together become one chord with an arpeggio mark.
3. **Rhythm**:
   - A phase-locked tracker follows the beat grid (eighth notes for x/8 meters), so tempo changes such as a ritardando don't shift barlines.
   - Onsets snap to the coarsest subdivision that fits (eighth, 16th, then 32nd).
4. **Hands**: each chord is split between treble and bass by distance to each hand's recent notes and running centre, with penalties for impossible spans and crossings. A fixed middle-C split is wrong whenever the right hand dips below C4 or a left-hand arpeggio climbs above it.
5. **Lengths**: per hand, a chord lasts until its release. It is extended to the hand's next note if it stops just short of it, or while the sustain pedal is down, and it is clipped at the next note.
6. **Key and spelling**: the key comes from `--key` or Krumhansl analysis. Accidentals are spelled by scale degree (♯1 ♭3 ♯4 ♯5 ♭7), so G major gives G♯ B♭ C♯ D♯ F.
7. **Engraving**: [music21](https://web.mit.edu/music21/) builds a two-staff score with title credits, and [verovio](https://www.verovio.org/) lays it out for print. cairosvg writes vector PDF pages.

## Printing

- **Pages:** exact A4 (`--paper a4`, default) or US Letter (`--paper letter`) pages with 15 mm margins. Staves are about 7 mm high, the usual size for piano music.
- **Layout:** systems are spread evenly down each page, with page numbers from page 2 on. The last page stays top-aligned.
- **Title block:** a bold centred title, an italic subtitle, and the composer and "Arr. …" credits on the right. The same title, author and subject go into the PDF metadata.
- **Chinese, Japanese and Korean text:** needs a CJK font. Install one with `apt-get install fonts-noto-cjk`; Noto Serif CJK SC is used when present. verovio ignores MEI font families, so the renderer assigns the CJK font to those text runs itself. Without one, cairo silently drops the characters.
- **Same title in MuseScore:** the MusicXML carries the page size and title credits, so it opens there with the same title block.

## Hints

All hints are optional, but use them when you know the score: copy them from page 1 of a score preview, for example.

| Option | Meaning |
|---|---|
| `--time-sig 6/8` | meter (default 6/8). The tracking grid uses its denominator. |
| `--pickup 2` | tatums of music before the first downbeat. Measure 1 is padded with rests. |
| `--tempo 200 --tempo-unit eighth` | tempo mark (default: estimated from the onsets) |
| `--key G` / `--key "e minor"` | key (default: detected) |
| `--start/--end` | ignore notes outside a time window, e.g. talking or UI sounds |
| `--grid 1,0.5,0.25` | allowed subdivisions of the tatum, coarsest first |
| `--title --subtitle --composer --arranger` | title block (arranger printed as "Arr. …") |
| `--paper a4` / `--paper letter` | PDF paper size |

You can pass an existing `.mid` instead of audio to rerun only the notation stages (seconds instead of minutes).

## Setup

```
python3 -m venv .venv && . .venv/bin/activate
pip install torch torchaudio
pip install -r requirements.txt
python -m pytest -q tests
```

`ffmpeg` must be on PATH for audio decoding. For titles in Chinese, Japanese or Korean, install `fonts-noto-cjk` (see Printing). The renderer installs verovio's music font into `~/.local/share/fonts` the first time it runs, so cairo can draw tempo-mark notes.

## Accuracy on the test piece

The test was a computer playback of a 148-measure arrangement, checked against a hand-entered copy of page 1 (measures 1–17, 136 notes):

| Check | Result |
|---|---|
| Notes found (onset within 50 ms, right pitch) | F1 0.996 |
| Right pitch, measure and beat | 136 / 136 |
| Sharps and flats spelled as on the page | 100% |
| Right staff | 97.8% |
| Same written length | 94.1% |

The remaining differences are arranger's choices that no rule can infer, such as which hand plays a note under a held melody note.

## Limits

- **Live performances** with rubato transcribe less cleanly than computer playback. The model is still accurate, but the beat grid and quantization degrade.
- **One voice per hand**: a note held under moving notes in the same hand is cut off where the next note starts.
- **Meter and pickup aren't detected**: give `--time-sig` and `--pickup`.
- **No dynamics, slurs or pedal marks** in the score yet; pedal is used only to set note lengths.
