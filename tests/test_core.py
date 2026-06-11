import sys
import time
from pathlib import Path

import mido
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from input_backends import DryRunInput
from keymap import HIGHEST_NOTE, LOWEST_NOTE, NOTE_TO_KEY, is_in_c_major, note_name
from midi_loader import NoteEvent, load_midi
from player import Player, build_chords
from validator import (
    apply_adaptation,
    apply_shift,
    choose_octave_shift,
    detect_transposition,
    validate,
)


def ev(*notes, spacing=0.5):
    return [NoteEvent(time=i * spacing, note=n) for i, n in enumerate(notes)]


# --- keymap -----------------------------------------------------------------

def test_keymap_covers_exactly_the_21_keys():
    assert len(NOTE_TO_KEY) == 21
    assert NOTE_TO_KEY[48] == "z"   # C3
    assert NOTE_TO_KEY[59] == "m"   # B3
    assert NOTE_TO_KEY[60] == "a"   # C4
    assert NOTE_TO_KEY[71] == "j"   # B4
    assert NOTE_TO_KEY[72] == "q"   # C5
    assert NOTE_TO_KEY[83] == "u"   # B5
    assert all(is_in_c_major(n) for n in NOTE_TO_KEY)


def test_note_names():
    assert note_name(60) == "C4"
    assert note_name(61) == "C#4"
    assert note_name(48) == "C3"


# --- validator --------------------------------------------------------------

def test_valid_c_major_song_passes():
    result = validate(ev(60, 62, 64, 65, 67, 69, 71, 72))
    assert result.ok
    assert result.semitone_shift == 0
    assert result.octave_shift == 0
    assert result.note_count == 8


def test_a_minor_song_passes_same_pitch_classes():
    # A minor (relative of C major) uses the same white keys.
    result = validate(ev(57, 60, 64, 69, 71, 72, 76, 81))  # A3..A5
    assert result.ok
    assert result.semitone_shift == 0
    assert result.octave_shift == 0


def test_g_major_song_is_transposed_to_c_major():
    # Full G major scale -> only the shift G->C (up 5 semitones) fits.
    g_major = ev(55, 57, 59, 60, 62, 64, 66, 67)  # G3 A3 B3 C4 D4 E4 F#4 G4
    result = validate(g_major)
    assert result.ok
    assert result.semitone_shift == 5
    # After transposing, every note lands on a white key.
    shifted = apply_shift(g_major, result.total_shift)
    assert all(is_in_c_major(e.note) for e in shifted)


def test_e_minor_song_is_transposed_to_a_minor():
    # E minor shares G major's notes; transposing up 5 lands on A minor.
    e_minor = ev(52, 54, 55, 57, 59, 60, 62)  # E3 F#3 G3 A3 B3 C4 D4
    result = validate(e_minor)
    assert result.ok
    assert result.semitone_shift == 5
    shifted = apply_shift(e_minor, result.total_shift)
    assert all(is_in_c_major(e.note) for e in shifted)


def test_detect_transposition_prefers_no_shift_when_already_in_key():
    assert detect_transposition(ev(60, 62, 64, 65, 67, 69, 71)) == 0


def test_detect_transposition_finds_downward_shift():
    # Full D-flat major scale -> unique fit is down 1 semitone to C major.
    db_major = ev(61, 63, 65, 66, 68, 70, 72)  # C# D# F F# G# A# C
    assert detect_transposition(db_major) == -1


def test_empty_song_rejected():
    result = validate([])
    assert not result.ok
    assert "no playable notes" in result.errors[0]


def test_chromatic_song_is_snapped_not_rejected():
    # Three consecutive semitones never fit a scale -> the odd note is snapped.
    result = validate(ev(60, 61, 62))  # C C# D
    assert result.ok
    assert result.chromatic
    assert result.snapped_count == 1
    out = apply_adaptation(ev(60, 61, 62), result)
    assert all(is_in_c_major(e.note) for e in out)
    assert all(LOWEST_NOTE <= e.note <= HIGHEST_NOTE for e in out)
    # C# sits between C and D, both equally common here -> flattens down to C.
    assert out[1].note == 60


def test_wide_range_is_compressed_not_rejected():
    result = validate(ev(36, 84))  # C2 to C6 = 4 octaves
    assert result.ok
    assert result.compressed
    assert result.folded_count >= 1
    out = apply_adaptation(ev(36, 84), result)
    assert all(LOWEST_NOTE <= e.note <= HIGHEST_NOTE for e in out)
    assert all(is_in_c_major(e.note) for e in out)


def test_out_of_range_but_octave_shiftable_passes_without_folding():
    result = validate(ev(36, 40, 43))  # C2 E2 G2, one octave below range
    assert result.ok
    assert result.octave_shift == 12
    assert not result.compressed
    assert result.folded_count == 0
    assert result.note_range == ("C3", "G3")


def test_high_song_shifts_down():
    result = validate(ev(96, 100))  # C7 E7
    assert result.ok
    assert result.octave_shift == -24
    assert not result.compressed


def test_span_crossing_c_boundary_is_compressed():
    # A2 to G5 spans < 3 octaves but no C-aligned window holds it -> fold.
    result = validate(ev(45, 79))
    assert result.ok
    assert result.compressed
    out = apply_adaptation(ev(45, 79), result)
    assert all(LOWEST_NOTE <= e.note <= HIGHEST_NOTE for e in out)


def test_chromatic_and_wide_are_both_handled():
    # An off-scale note AND a 3+ octave span: snap the note, fold the range.
    result = validate(ev(60, 61, 98))  # C C# D7
    assert result.ok
    assert result.chromatic and result.snapped_count == 1
    assert result.compressed
    out = apply_adaptation(ev(60, 61, 98), result)
    assert all(is_in_c_major(e.note) for e in out)
    assert all(LOWEST_NOTE <= e.note <= HIGHEST_NOTE for e in out)


def test_snap_prefers_more_common_neighbor():
    # Full C major scale (pins the key) + extra G's + one F#. F# is equidistant
    # from F and G, but G is far more common here, so F# snaps up to G.
    events = ev(60, 62, 64, 65, 67, 69, 71, 67, 67, 66)
    result = validate(events)
    assert result.ok and result.chromatic and result.snapped_count == 1
    assert result.snap_delta == {6: 1}  # F# -> G
    out = apply_adaptation(events, result)
    assert out[-1].note == 67  # the F# became G4
    assert all(is_in_c_major(e.note) for e in out)


def test_snap_tie_flattens_down():
    # Full C major scale + one F#; F and G occur equally -> tie -> flatten to F.
    events = ev(60, 62, 64, 65, 67, 69, 71, 66)
    result = validate(events)
    assert result.chromatic and result.snap_delta == {6: -1}  # F# -> F
    out = apply_adaptation(events, result)
    assert out[-1].note == 65  # F4


def test_diatonic_song_is_not_marked_chromatic():
    result = validate(ev(60, 62, 64, 65, 67, 69, 71))  # clean C major
    assert result.ok
    assert not result.chromatic
    assert result.snapped_count == 0
    assert result.snap_delta == {}


def test_compression_keeps_melody_intervals_intact():
    # A compact upper melody plus one deep bass note, spanning > 3 octaves.
    melody = [72, 74, 76, 77, 79]  # C5 D5 E5 F5 G5
    events = ev(*(melody + [36]))  # + C2 bass, four octaves below the top
    result = validate(events)
    assert result.ok and result.compressed
    out = [e.note for e in apply_adaptation(events, result)]
    # The melody moves as one block, so its internal intervals are unchanged.
    orig_diffs = [b - a for a, b in zip(melody, melody[1:])]
    out_diffs = [b - a for a, b in zip(out[:5], out[1:5])]
    assert out_diffs == orig_diffs
    # The lone bass outlier is the note that got folded into range.
    assert result.folded_count == 1
    assert LOWEST_NOTE <= out[-1] <= HIGHEST_NOTE


def test_choose_octave_shift_zero_folds_when_it_fits():
    # A song that fits gets a fold-free placement equal to the old fit logic.
    notes = [60 + s for s in (0, 2, 4, 5, 7, 9, 11)]  # C major octave, in range
    assert choose_octave_shift(notes) == 0


def test_apply_adaptation_makes_everything_playable():
    events = ev(24, 36, 60, 96, 108)  # C1..C8, all C's, diatonic but huge span
    result = validate(events)
    assert result.ok and result.compressed
    out = apply_adaptation(events, result)
    assert all(LOWEST_NOTE <= e.note <= HIGHEST_NOTE for e in out)
    assert all(e.note % 12 == 0 for e in out)  # every C folds onto a C key


def test_apply_shift():
    shifted = apply_shift(ev(36, 40), 12)
    assert [e.note for e in shifted] == [48, 52]
    assert apply_shift([], 0) == []


# --- chords -----------------------------------------------------------------

def test_simultaneous_notes_grouped_into_chord():
    events = [NoteEvent(0.0, 60), NoteEvent(0.005, 64), NoteEvent(0.5, 67)]
    chords = build_chords(events)
    assert chords == [(0.0, ["a", "d"]), (0.5, ["g"])]


def test_duplicate_note_in_chord_deduped():
    chords = build_chords([NoteEvent(0.0, 60), NoteEvent(0.0, 60)])
    assert chords == [(0.0, ["a"])]


# --- midi loading -----------------------------------------------------------

def make_midi(path, notes, channel=0, ticks=480):
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    for note in notes:
        track.append(mido.Message("note_on", note=note, velocity=64, channel=channel, time=0))
        track.append(mido.Message("note_off", note=note, velocity=0, channel=channel, time=ticks))
    mid.save(path)


def test_load_midi_extracts_note_ons(tmp_path):
    path = tmp_path / "song.mid"
    make_midi(path, [60, 64, 67])
    events = load_midi(str(path))
    assert [e.note for e in events] == [60, 64, 67]
    assert events[0].time == 0.0
    assert events[1].time == pytest.approx(0.5)  # 480 ticks at 120bpm


def test_load_midi_skips_percussion(tmp_path):
    path = tmp_path / "drums.mid"
    make_midi(path, [35, 38], channel=9)
    assert load_midi(str(path)) == []


def test_load_midi_rejects_garbage(tmp_path):
    path = tmp_path / "not_midi.mid"
    path.write_bytes(b"this is not midi data")
    with pytest.raises(ValueError):
        load_midi(str(path))


# --- player -----------------------------------------------------------------

def test_player_presses_all_chords_in_order():
    backend = DryRunInput(log=lambda _: None)
    player = Player(backend)
    player.load([(0.0, ["a"]), (0.05, ["s", "d"]), (0.1, ["q"])])
    player.play()
    deadline = time.time() + 2
    while player.state != "idle" and time.time() < deadline:
        time.sleep(0.01)
    assert player.state == "idle"
    assert backend.pressed == [["a"], ["s", "d"], ["q"]]


def test_player_timing_respects_speed():
    backend = DryRunInput(log=lambda _: None)
    player = Player(backend)
    player.speed = 2.0
    player.load([(0.0, ["a"]), (0.4, ["s"])])
    start = time.perf_counter()
    player.play()
    while player.state != "idle" and time.perf_counter() - start < 2:
        time.sleep(0.01)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.35  # 0.4s gap halved by 2x speed


def test_player_stop_interrupts():
    backend = DryRunInput(log=lambda _: None)
    player = Player(backend)
    player.load([(0.0, ["a"]), (5.0, ["s"])])
    player.play()
    time.sleep(0.1)
    player.stop()
    time.sleep(0.1)
    assert player.state == "idle"
    assert backend.pressed == [["a"]]


def test_player_pause_resume():
    backend = DryRunInput(log=lambda _: None)
    player = Player(backend)
    player.load([(0.0, ["a"]), (0.2, ["s"])])
    player.play()
    time.sleep(0.05)
    player.toggle_pause()
    assert player.state == "paused"
    time.sleep(0.3)
    assert backend.pressed == [["a"]]  # second chord held back
    player.toggle_pause()
    deadline = time.time() + 2
    while player.state != "idle" and time.time() < deadline:
        time.sleep(0.01)
    assert backend.pressed == [["a"], ["s"]]
