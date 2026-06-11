"""Load a MIDI file into a flat list of note events.

All tracks are merged. The percussion channel (10, zero-indexed 9) is
ignored because its "notes" are drum sounds, not pitches.
"""

from dataclasses import dataclass

import mido

PERCUSSION_CHANNEL = 9


@dataclass(frozen=True)
class NoteEvent:
    time: float  # seconds from the start of the song
    note: int    # MIDI note number


def load_midi(path: str) -> list[NoteEvent]:
    """Return note-on events sorted by time.

    Raises ValueError if the file cannot be parsed as MIDI.
    """
    try:
        midi = mido.MidiFile(path)
    except Exception as exc:  # mido raises several unrelated types
        raise ValueError(f"Not a readable MIDI file: {exc}") from exc

    events = []
    now = 0.0
    # Iterating a MidiFile merges all tracks and yields seconds-based
    # delta times with tempo changes already applied.
    for msg in midi:
        now += msg.time
        if (
            msg.type == "note_on"
            and msg.velocity > 0
            and msg.channel != PERCUSSION_CHANNEL
        ):
            events.append(NoteEvent(time=now, note=msg.note))
    return events
