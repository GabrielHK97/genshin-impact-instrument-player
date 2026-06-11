import mido
from collections import Counter
from dataclasses import dataclass, field

# --- Assumptions for keymap constants based on your imports ---
C_MAJOR_PITCH_CLASSES = {0, 2, 4, 5, 7, 9, 11}  # C, D, E, F, G, A, B
LOWEST_NOTE = 48   # C3 in MIDI standard (sometimes labeled C4, adjusting to 48)
HIGHEST_NOTE = 83  # B5 in MIDI standard
def is_in_c_major(note: int) -> bool: return (note % 12) in C_MAJOR_PITCH_CLASSES
def note_name(note: int) -> str:
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return f"{names[note % 12]}{note // 12 - 1}"

@dataclass
class NoteEvent:
    time: float  # Absolute time in seconds
    note: int

# ==============================================================================
# 1. NEW MIDI PREPROCESSING & FILTERING FUNCTIONS
# ==============================================================================

def load_and_preprocess_midi(file_path: str) -> list[NoteEvent]:
    """Load a MIDI file, squash all tracks into one timeline, drop percussion.

    Iterating a MidiFile yields every track's messages merged in time order,
    with msg.time as a delta in SECONDS (tempo already applied) -- so this
    both flattens to a single track and gives us absolute times for free.
    """
    mid = mido.MidiFile(file_path)
    events: list[NoteEvent] = []

    absolute_time = 0.0
    for msg in mid:
        absolute_time += msg.time  # delta time in SECONDS
        # A note_on with velocity 0 is a note_off; ignore it and percussion
        # (General MIDI puts drums on channel 10, which is index 9 in mido).
        if msg.type == 'note_on' and msg.velocity > 0 and msg.channel != 9:
            events.append(NoteEvent(time=absolute_time, note=msg.note))

    events.sort(key=lambda e: e.time)
    return events


# Re-encode at a fixed 120 BPM / 480 ticks-per-beat grid. Because we captured
# the source timing in real seconds (tempo already baked in), 1 second = 960
# ticks here reproduces the original wall-clock timing exactly.
TICKS_PER_BEAT = 480
TICKS_PER_SECOND = 960
NOTE_TICKS = 40  # short "button tap" so notes never hang


def save_clean_midi(events: list[NoteEvent], total_shift: int, output_path: str):
    """Apply the shift and save a single-track MIDI, preserving chords.

    We build one timeline of note_on/note_off events at absolute ticks and
    emit them sorted, so notes that share a start time stay simultaneous
    (a chord) instead of being serialized, and no timing drift accumulates.
    """
    shifted_events = apply_shift(events, total_shift)

    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(120), time=0))

    # (absolute_tick, priority, message) -- at the same tick, note_off (0) is
    # ordered before note_on (1) so a voice is released before it's reused.
    timeline: list[tuple[int, int, mido.Message]] = []
    for ev in shifted_events:
        on_tick = int(round(ev.time * TICKS_PER_SECOND))
        timeline.append((on_tick, 1, mido.Message('note_on', note=ev.note, velocity=64)))
        timeline.append((on_tick + NOTE_TICKS, 0, mido.Message('note_off', note=ev.note, velocity=0)))
    timeline.sort(key=lambda item: (item[0], item[1]))

    prev_tick = 0
    for absolute_tick, _priority, msg in timeline:
        msg.time = absolute_tick - prev_tick
        track.append(msg)
        prev_tick = absolute_tick

    mid.save(output_path)
    print(f"✓ Saved single-track MIDI ({len(shifted_events)} notes) to {output_path}")

# ==============================================================================
# YOUR ORIGINAL LOGIC (RETAINED)
# ==============================================================================

@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    semitone_shift: int = 0        
    octave_shift: int = 0          
    note_count: int = 0
    duration: float = 0.0          
    note_range: tuple[str, str] | None = None  

    @property
    def total_shift(self) -> int:
        return self.semitone_shift + self.octave_shift

def _signed(semitones: int) -> int:
    return semitones if semitones <= 6 else semitones - 12

def detect_transposition(events: list[NoteEvent]) -> int:
    pitch_class_counts = Counter(e.note % 12 for e in events)
    def in_scale_after(shift: int) -> int:
        return sum(count for pc, count in pitch_class_counts.items() if (pc + shift) % 12 in C_MAJOR_PITCH_CLASSES)
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
            f"C major / A minor scale, with no single key that fits them all: {_summarize(off_scale)}"
        )

    lowest, highest = min(notes), max(notes)
    if highest - lowest > HIGHEST_NOTE - LOWEST_NOTE:
        result.ok = False
        result.errors.append(f"Note range spans more than 3 octaves: {note_name(lowest)} to {note_name(highest)}.")
    else:
        shifts = [s for s in range(-120, 121, 12) if lowest + s >= LOWEST_NOTE and highest + s <= HIGHEST_NOTE]
        if not shifts:
            result.ok = False
            result.errors.append(f"Notes ({note_name(lowest)} to {note_name(highest)}) cross a C-to-B octave boundary.")
        else:
            result.octave_shift = min(shifts, key=abs)
            result.note_range = (note_name(lowest + result.octave_shift), note_name(highest + result.octave_shift))

    return result

def apply_shift(events: list[NoteEvent], total_shift: int) -> list[NoteEvent]:
    if total_shift == 0:
        return events
    return [NoteEvent(time=e.time, note=e.note + total_shift) for e in events]

# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================

def process_midi_pipeline(input_file: str, output_file: str) -> bool:
    """Adapt one raw MIDI into a Genshin-ready single-track file.

    Returns True if the file passed validation and was written, False otherwise.
    """
    print(f"Processing: {input_file}...")

    # 1. Flatten all tracks into one timeline, dropping channel-10 percussion.
    try:
        raw_events = load_and_preprocess_midi(input_file)
    except (OSError, ValueError, EOFError, IndexError) as exc:
        print(f"❌ Could not read '{input_file}' as a MIDI file: {exc}")
        return False

    # 2. Detect the key, transpose to C major / A minor, and check the range.
    result = validate(raw_events)

    if not result.ok:
        print("❌ Validation failed -- this MIDI can't be adapted:")
        for error in result.errors:
            print(f"  - {error}")
        return False

    print(f"➔ Diatonic alignment: transposed {result.semitone_shift} semitone(s).")
    print(f"➔ Octave alignment: shifted {result.octave_shift // 12} octave(s).")
    print(f"➔ Range achieved: {result.note_range[0]} to {result.note_range[1]}")

    # 3. Apply the shift and export a single-track MIDI.
    save_clean_midi(raw_events, result.total_shift, output_file)
    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) not in (2, 3):
        print("Usage: python validator.py <input.mid> [output.mid]")
        print("  Adapts a raw MIDI to a diatonic, 3-octave, single-track file.")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) == 3 else src.rsplit(".", 1)[0] + "_genshin.mid"
    sys.exit(0 if process_midi_pipeline(src, dst) else 1)