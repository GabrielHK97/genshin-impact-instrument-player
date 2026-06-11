"""Mapping between MIDI notes and Genshin instrument keys.

The in-game instruments expose 3 octaves of the C major scale:
    Q W E R T Y U  ->  C5 D5 E5 F5 G5 A5 B5   (MIDI 72-83)
    A S D F G H J  ->  C4 D4 E4 F4 G4 A4 B4   (MIDI 60-71)
    Z X C V B N M  ->  C3 D3 E3 F3 G3 A3 B3   (MIDI 48-59)
"""

# Pitch classes of the C major scale (white keys): C D E F G A B
C_MAJOR_PITCH_CLASSES = frozenset({0, 2, 4, 5, 7, 9, 11})

LOWEST_NOTE = 48   # C3
HIGHEST_NOTE = 83  # B5

_ROWS = {
    48: "zxcvbnm",  # C3..B3
    60: "asdfghj",  # C4..B4
    72: "qwertyu",  # C5..B5
}

_SCALE_OFFSETS = (0, 2, 4, 5, 7, 9, 11)

NOTE_TO_KEY = {
    base + offset: row[i]
    for base, row in _ROWS.items()
    for i, offset in enumerate(_SCALE_OFFSETS)
}

_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def note_name(midi_note: int) -> str:
    """Human-readable name, e.g. 60 -> 'C4' (middle C convention)."""
    return f"{_NOTE_NAMES[midi_note % 12]}{midi_note // 12 - 1}"


def is_in_c_major(midi_note: int) -> bool:
    return midi_note % 12 in C_MAJOR_PITCH_CLASSES
