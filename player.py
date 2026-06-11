"""Playback engine: schedules key presses on a background thread."""

import threading
import time

from keymap import NOTE_TO_KEY
from midi_loader import NoteEvent

# Notes starting within this window are pressed together as a chord.
CHORD_WINDOW = 0.01  # seconds


def build_chords(events: list[NoteEvent]) -> list[tuple[float, list[str]]]:
    """Convert validated note events into (time, [keys]) chords."""
    chords: list[tuple[float, list[str]]] = []
    for event in sorted(events, key=lambda e: e.time):
        key = NOTE_TO_KEY[event.note]
        if chords and event.time - chords[-1][0] <= CHORD_WINDOW:
            if key not in chords[-1][1]:
                chords[-1][1].append(key)
        else:
            chords.append((event.time, [key]))
    return chords


class Player:
    """Drift-free playback with play / pause / stop, safe to drive from
    hotkey callbacks and the GUI thread. State is polled, never pushed."""

    def __init__(self, backend):
        self._backend = backend
        self._chords: list[tuple[float, list[str]]] = []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self.state = "idle"  # idle | playing | paused
        self.progress = (0, 0)
        self.speed = 1.0  # multiplier, locked in when playback starts

    def load(self, chords: list[tuple[float, list[str]]]) -> None:
        self.stop()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._chords = chords
        self.progress = (0, len(chords))

    def play(self) -> None:
        if self.state == "paused":
            self._paused.clear()
            self.state = "playing"
            return
        if self.state == "playing" or not self._chords:
            return
        self._stop.clear()
        self._paused.clear()
        self.state = "playing"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def toggle_pause(self) -> None:
        if self.state == "playing":
            self._paused.set()
            self.state = "paused"
        elif self.state == "paused":
            self._paused.clear()
            self.state = "playing"

    def stop(self) -> None:
        if self.state != "idle":
            self._stop.set()
            self._paused.clear()
            self.state = "idle"

    def _run(self) -> None:
        speed = max(self.speed, 0.1)
        start = time.perf_counter()
        paused_total = 0.0
        for i, (when, keys) in enumerate(self._chords):
            target = start + paused_total + when / speed
            while True:
                if self._stop.is_set():
                    return
                if self._paused.is_set():
                    pause_start = time.perf_counter()
                    while self._paused.is_set():
                        if self._stop.is_set():
                            return
                        time.sleep(0.02)
                    paused_total += time.perf_counter() - pause_start
                    target = start + paused_total + when / speed
                remaining = target - time.perf_counter()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.02))
            self._backend.press(keys)
            self.progress = (i + 1, len(self._chords))
        self.state = "idle"
