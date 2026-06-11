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

The app loads a MIDI file (all tracks merged, percussion ignored) and
**strictly validates** it:

- every note must be in the **C major scale** (white keys only — songs in
  **A minor** work too, since it's the relative minor with the same notes);
- all notes must fit one **C-to-B aligned 3-octave window**. Whole-octave
  shifts to line the song up with C3-B5 are applied automatically and are
  lossless. Note for A minor songs: because the window is C-aligned, a
  melody centered on A effectively has less usable range — songs that
  overflow the window are rejected with a report.

Files that fail get a report listing exactly which notes are out of scale
or out of range.

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
