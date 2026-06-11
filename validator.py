"""Strict validation of a MIDI song against the Genshin instrument layout.

A song is playable when:
  1. it contains at least one note,
  2. every note belongs to the C major scale (no sharps/flats),
  3. all notes fit inside one C-to-B aligned 3-octave window.

Shifting the whole song by whole octaves to line it up with the in-game
C3-B5 range is lossless, so it is applied automatically and reported.
"""

from collections import Counter
from dataclasses import dataclass, field

from keymap import HIGHEST_NOTE, LOWEST_NOTE, is_in_c_major, note_name
from midi_loader import NoteEvent


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    octave_shift: int = 0          # semitones (multiple of 12) applied to fit C3-B5
    note_count: int = 0
    duration: float = 0.0          # seconds
    note_range: tuple[str, str] | None = None  # (lowest, highest) after shift


def _summarize(notes: Counter, limit: int = 10) -> str:
    parts = [f"{note_name(n)} x{c}" for n, c in sorted(notes.items())]
    shown = ", ".join(parts[:limit])
    if len(parts) > limit:
        shown += f", ... and {len(parts) - limit} more"
    return shown


def validate(events: list[NoteEvent]) -> ValidationResult:
    if not events:
        return ValidationResult(ok=False, errors=["The file contains no playable notes."])

    result = ValidationResult(ok=True, note_count=len(events), duration=events[-1].time)

    off_scale = Counter(e.note for e in events if not is_in_c_major(e.note))
    if off_scale:
        result.ok = False
        result.errors.append(
            f"{sum(off_scale.values())} note(s) outside the C major scale "
            f"(sharps/flats): {_summarize(off_scale)}"
        )

    lowest = min(e.note for e in events)
    highest = max(e.note for e in events)

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


def apply_shift(events: list[NoteEvent], octave_shift: int) -> list[NoteEvent]:
    if octave_shift == 0:
        return events
    return [NoteEvent(time=e.time, note=e.note + octave_shift) for e in events]
