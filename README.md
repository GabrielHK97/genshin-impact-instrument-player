# Genshin Instrument Player

Desktop app that plays Genshin Impact instruments (Windsong Lyre, Floral
Zither, Vintage Lyre, drum) by pressing the in-game keys from a MIDI file.

## How it works

The in-game instruments expose 3 octaves of the C major scale:

| Octave | Keys | Notes |
|--------|------------------|----------|
| High | Q W E R T Y U | C5 - B5 |
| Middle | A S D F G H J | C4 - B4 |
| Low | Z X C V B N M | C3 - B3 |

The app loads a MIDI file (all tracks merged, percussion ignored), then
validates and prepares it:

- **Automatic transposition.** The white keys C3-B5 are exactly the C major
  scale (and its relative, A minor). A song written in any other major or
  minor key is automatically transposed by whole semitones so every note
  lands on a white key. This changes the key the song plays in, not the
  melody, so it stays faithful. A song already in C major / A minor is left
  untouched.
- **Octave fitting.** Whole-octave shifts to line the song up with C3-B5 are
  applied automatically and are lossless.
- **Range compression.** A song wider than 3 octaves is folded to fit. The
  window is placed where the *fewest* notes fall outside it, so the melody
  (the largest in-range band) stays put — or moves as one block, which keeps
  its shape exactly — while the outliers (usually the bass) fold by whole
  octaves into range. Folds preserve pitch class, so the result stays in-key.
- **Chromatic snapping.** After transposing to the best-fitting key, any
  leftover off-scale notes (sharps/flats that don't belong to that key) are
  nudged a semitone onto the nearest white key. An accidental sits exactly
  between two white keys, so the tie is broken toward whichever neighbor is
  **more common in the song** (the more harmonically central one), otherwise
  it flattens down. The app **warns** you when this happens — telling you how
  many notes (and what fraction) were adjusted and how (e.g. `F#→G, A#→A`) —
  so you know playback differs slightly from the original.

The only files that can't be played are ones that **can't be read** as MIDI
or contain **no notes** at all (e.g. a drums-only file once percussion is
dropped). Any readable, non-empty MIDI is made playable: transposed,
chromatically snapped if needed, octave-fitted, and compressed if wider than
3 octaves.

## Setup (Windows, same PC as the game)

1. Install [Python 3.11+](https://www.python.org/downloads/) (check
   "Add python.exe to PATH" in the installer).
2. In this folder:
   ```
   pip install -r requirements.txt
   ```
3. Run the app **as administrator** (right-click → Run as administrator on
   a shortcut to `python app.py`, or use an elevated terminal):
   ```
   python app.py
   ```
   Genshin runs elevated, so key presses from a non-elevated app are
   silently ignored by Windows.

> Every `python`/`pip` command in this README also works as
> `python3`/`pip3` — use whichever your system provides (on macOS/Linux
> it's usually `python3`).

## Usage

1. Click **Open MIDI...** and pick a `.mid` file. The validation report
   tells you if it's playable.
2. Switch to Genshin with the instrument open.
3. Global hotkeys (work while the game is focused):
   - **F6** — play / resume
   - **F7** — pause / resume
   - **F8** — stop
4. The speed slider (0.5x-1.5x) applies the next time you press play.

## Building a standalone .exe

On the Windows PC:

```
pip install pyinstaller
python build.py
```

The executable appears in `dist/GenshinInstrumentPlayer.exe` and requests
administrator rights on launch (required — see above). PyInstaller does
not cross-compile, so build on the OS you target.

## Development on macOS/Linux

Without `pydirectinput` the app runs in **dry-run mode**: key presses are
logged in the window instead of sent, so song timing can be checked
without the game. Run the app with `python3 app.py` and the tests with:

```
python3 -m pytest tests/
```

## Notes

- Automated input falls under miHoYo's third-party-tool policy. Lyre
  macro tools are widely used without issue, but use at your own risk.
- If hotkeys don't respond, the `keyboard` library needs the app elevated
  (see setup step 3).
