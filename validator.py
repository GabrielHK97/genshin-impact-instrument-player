"""Validation + automatic key transposition for the Genshin instrument layout.

The in-game instruments play only the white keys of three octaves, C3-B5 —
which is exactly the C major scale and its relative, A minor. A song written
in any other major/minor key is automatically transposed by whole semitones
so its notes land on those white keys. This is musically faithful: it changes
the key the song is played in, not the melody.

A song is playable when, after transposition:
  1. it contains at least one note,
  2. every note lands on a white key (C major / A minor), and
  3. all notes fit one C-to-B aligned 3-octave window — whole-octave shifts
     to line it up with C3-B5 are applied automatically and are lossless.
"""

from collections import Counter
from dataclasses import dataclass, field

from keymap import (
    C_MAJOR_PITCH_CLASSES,
    HIGHEST_NOTE,
    LOWEST_NOTE,
    is_in_c_major,
    note_name,
)
from midi_loader import NoteEvent


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    semitone_shift: int = 0        # transposition applied to reach C major / A minor
    octave_shift: int = 0          # extra multiple of 12 to fit the C3-B5 keys
    note_count: int = 0
    duration: float = 0.0          # seconds
    note_range: tuple[str, str] | None = None  # (lowest, highest) after all shifts

    @property
    def total_shift(self) -> int:
        return self.semitone_shift + self.octave_shift


def _signed(semitones: int) -> int:
    """Reduce a 0-11 transposition to its smallest equivalent move, e.g. 7 -> -5."""
    return semitones if semitones <= 6 else semitones - 12


def detect_transposition(events: list[NoteEvent]) -> int:
    """Pick the semitone shift that lands the most notes on white keys.

    Tries every transposition 0-11, scoring by how many note events fall in
    the C major scale (weighted by how often each pitch is played); ties break
    toward the smallest pitch movement, and toward no shift at all. A song
    already in C major / A minor scores best at 0 and is left untouched.
    """
    pitch_class_counts = Counter(e.note % 12 for e in events)

    def in_scale_after(shift: int) -> int:
        return sum(
            count for pc, count in pitch_class_counts.items()
            if (pc + shift) % 12 in C_MAJOR_PITCH_CLASSES
        )

    best = max(range(12), key=lambda s: (in_scale_after(s), -abs(_signed(s))))
    return _signed(best)


def _summarize(notes: Counter, limit: int = 10) -> str:
    parts = [f"{note_name(n)} x{c}" for n, c in sorted(notes.items())]
    shown = ", ".join(parts[:limit])
    if len(parts) > limit:
        shown += f", ... and {len(parts) - limit} more"
    return shown


def validate(events: list[NoteEvent]) -> ValidationResult:
    if not events:
        return ValidationResult(ok=False, errors=["The file contains no playable notes."])

    semitone_shift = detect_transposition(events)
    notes = [e.note + semitone_shift for e in events]

    result = ValidationResult(
        ok=True,
        semitone_shift=semitone_shift,
        note_count=len(events),
        duration=events[-1].time,
    )

    off_scale = Counter(n for n in notes if not is_in_c_major(n))
    if off_scale:
        result.ok = False
        prefix = "even after transposing to the nearest key, " if semitone_shift else ""
        result.errors.append(
            f"{prefix}{sum(off_scale.values())} note(s) fall outside the "
            f"C major / A minor scale, with no single key that fits them all "
            f"(the song is chromatic): {_summarize(off_scale)}"
        )

    lowest, highest = min(notes), max(notes)
    if highest - lowest > HIGHEST_NOTE - LOWEST_NOTE:
        result.ok = False
        result.errors.append(
            f"Note range spans more than 3 octaves: "
            f"{note_name(lowest)} to {note_name(highest)}."
        )
    else:
        # Octave shifts (multiples of 12) that bring every note into C3-B5.
        shifts = [
            s for s in range(-120, 121, 12)
            if lowest + s >= LOWEST_NOTE and highest + s <= HIGHEST_NOTE
        ]
        if not shifts:
            result.ok = False
            result.errors.append(
                f"Notes ({note_name(lowest)} to {note_name(highest)}) span 3 octaves "
                f"or less but cross a C-to-B octave boundary, so they cannot fit "
                f"the instrument's C3-B5 layout."
            )
        else:
            # Prefer the smallest shift (0 when already in range).
            result.octave_shift = min(shifts, key=abs)
            result.note_range = (
                note_name(lowest + result.octave_shift),
                note_name(highest + result.octave_shift),
            )

    return result


def apply_shift(events: list[NoteEvent], total_shift: int) -> list[NoteEvent]:
    if total_shift == 0:
        return events
    return [NoteEvent(time=e.time, note=e.note + total_shift) for e in events]
