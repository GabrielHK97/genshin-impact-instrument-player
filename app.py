"""Genshin Instrument Player — desktop app.

Import a MIDI file, validate it against the in-game 3-octave C major
layout, and play it by pressing the mapped keys while the game is focused.

Hotkeys (global, work while the game has focus):
    F6 = play / resume    F7 = pause / resume    F8 = stop
"""

import os
import tkinter as tk
from tkinter import filedialog

from input_backends import create_backend
from midi_loader import load_midi
from player import Player, build_chords
from validator import apply_shift, validate

POLL_MS = 100


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Genshin Instrument Player")
        root.geometry("520x420")
        root.minsize(440, 360)

        self.backend, self.is_game_input = create_backend(log=self._log_line)
        self.player = Player(self.backend)
        self.song_name = None

        self._build_ui()
        self._register_hotkeys()
        self._poll_status()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- UI -----------------------------------------------------------------

    def _build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=(10, 0))
        tk.Button(top, text="Open MIDI...", command=self._open_file).pack(side="left")
        self.file_label = tk.Label(top, text="No file loaded", anchor="w")
        self.file_label.pack(side="left", padx=10)

        controls = tk.Frame(self.root)
        controls.pack(fill="x", padx=10, pady=8)
        tk.Button(controls, text="▶ Play (F6)", command=self.player.play).pack(side="left")
        tk.Button(controls, text="⏸ Pause (F7)", command=self.player.toggle_pause).pack(side="left", padx=6)
        tk.Button(controls, text="⏹ Stop (F8)", command=self.player.stop).pack(side="left")

        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Label(controls, text="Speed").pack(side="left", padx=(20, 4))
        tk.Scale(
            controls, from_=0.5, to=1.5, resolution=0.05, orient="horizontal",
            variable=self.speed_var, length=130, showvalue=True,
        ).pack(side="left")

        self.report = tk.Text(self.root, height=12, wrap="word", state="disabled")
        self.report.pack(fill="both", expand=True, padx=10)
        self.report.tag_configure("ok", foreground="#1a7f37")
        self.report.tag_configure("error", foreground="#c62828")
        self.report.tag_configure("info", foreground="#555555")

        self.status = tk.Label(self.root, text="", anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")

        if not self.is_game_input:
            self._log_line(
                "DRY RUN mode: pydirectinput not available (non-Windows or not "
                "installed). Key presses are logged here instead of sent.\n", "info",
            )

    def _log_line(self, text, tag="info"):
        self.report.configure(state="normal")
        self.report.insert("end", text if text.endswith("\n") else text + "\n", tag)
        self.report.see("end")
        self.report.configure(state="disabled")

    def _clear_report(self):
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.configure(state="disabled")

    # --- file handling --------------------------------------------------------

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Choose a MIDI file",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if not path:
            return
        self._clear_report()
        self.player.load([])
        self.song_name = None
        self.file_label.configure(text=os.path.basename(path))

        try:
            events = load_midi(path)
        except ValueError as exc:
            self._log_line(f"✗ {exc}", "error")
            return

        result = validate(events)
        if not result.ok:
            self._log_line("✗ This file cannot be played:", "error")
            for error in result.errors:
                self._log_line(f"  • {error}", "error")
            self._log_line(
                "\nThe instrument plays only the white keys C3-B5 (C major / "
                "A minor). Songs in other keys are transposed automatically, "
                "but a chromatic song (no single key fits its notes), or one "
                "wider than 3 octaves, can't be played.", "info",
            )
            return

        chords = build_chords(apply_shift(events, result.total_shift))
        self.player.load(chords)
        self.song_name = os.path.basename(path)
        minutes, seconds = divmod(int(result.duration), 60)
        self._log_line("✓ Valid song — ready to play.", "ok")
        self._log_line(
            f"  {result.note_count} notes in {len(chords)} chords, "
            f"{minutes}:{seconds:02d}, range {result.note_range[0]}-{result.note_range[1]}", "ok",
        )
        if result.semitone_shift:
            self._log_line(
                f"  Transposed {abs(result.semitone_shift)} semitone(s) "
                f"{'up' if result.semitone_shift > 0 else 'down'} into "
                f"C major / A minor (the song wasn't in that key).", "info",
            )
        if result.octave_shift:
            self._log_line(
                f"  Shifted {abs(result.octave_shift) // 12} octave(s) "
                f"{'up' if result.octave_shift > 0 else 'down'} to fit the C3-B5 keys.", "info",
            )
        self._log_line(
            "\nSwitch to the game with the instrument open, then press F6.", "info",
        )

    # --- hotkeys & status -----------------------------------------------------

    def _register_hotkeys(self):
        try:
            import keyboard

            keyboard.add_hotkey("f6", self.player.play)
            keyboard.add_hotkey("f7", self.player.toggle_pause)
            keyboard.add_hotkey("f8", self.player.stop)
            self.hotkeys_ok = True
        except Exception as exc:
            self.hotkeys_ok = False
            self._log_line(
                f"Global hotkeys unavailable ({exc}). Use the buttons instead.", "error",
            )

    def _poll_status(self):
        # Speed only applies when the next playback starts.
        self.player.speed = self.speed_var.get()
        done, total = self.player.progress
        state = self.player.state
        if state == "idle" and total and done == total:
            text = f"Finished — {self.song_name or ''}"
        elif state == "idle":
            text = "Idle"
        else:
            text = f"{state.capitalize()} — chord {done}/{total}"
        self.status.configure(text=f" {text}")
        self.root.after(POLL_MS, self._poll_status)

    def _on_close(self):
        self.player.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
