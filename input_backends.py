"""Key-press backends.

GameInput uses pydirectinput, which generates the scan-code level events
Genshin listens for (regular synthetic input is ignored by the game).
DryRunInput just logs, for development and testing without the game.
"""

import time


class GameInput:
    def __init__(self):
        import pydirectinput

        # pydirectinput sleeps 0.1s after every call by default, which
        # would wreck note timing. Chord/tap pacing is handled in press().
        pydirectinput.PAUSE = 0
        self._pdi = pydirectinput

    def press(self, keys: list[str]) -> None:
        for key in keys:
            self._pdi.keyDown(key)
        time.sleep(0.02)  # long enough for the game to register the tap
        for key in keys:
            self._pdi.keyUp(key)


class DryRunInput:
    """Logs presses instead of sending them. Used off-Windows and in tests."""

    def __init__(self, log=print):
        self._log = log
        self.pressed: list[list[str]] = []

    def press(self, keys: list[str]) -> None:
        self.pressed.append(keys)
        self._log(f"[dry-run] press {'+'.join(keys).upper()}")


def create_backend(log=print):
    """GameInput when pydirectinput is available (Windows), else dry-run."""
    try:
        return GameInput(), True
    except ImportError:
        return DryRunInput(log), False
