import sys
import time
from pathlib import Path

import mido
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from input_backends import DryRunInput
from keymap import NOTE_TO_KEY, is_in_c_major, note_name
from midi_loader import NoteEvent, load_midi
from player import Player, build_chords
from validator import apply_shift, validate


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
    assert result.octave_shift == 0
    assert result.note_count == 8


def test_a_minor_song_passes_same_pitch_classes():
    # A minor (relative of C major) uses the same white keys.
    result = validate(ev(57, 60, 64, 69, 71, 72, 76, 81))  # A3..A5
    assert result.ok
    assert result.octave_shift == 0


def test_empty_song_rejected():
    result = validate([])
    assert not result.ok
    assert "no playable notes" in result.errors[0]


def test_accidentals_rejected_with_names():
    result = validate(ev(60, 61, 66))
    assert not result.ok
    assert "C#4" in result.errors[0]
    assert "F#4" in result.errors[0]


def test_range_over_three_octaves_rejected():
    result = validate(ev(36, 84))  # C2 to C6 = 4 octaves
    assert not result.ok
    assert "more than 3 octaves" in result.errors[0]


def test_out_of_range_but_octave_shiftable_passes():
    result = validate(ev(36, 40, 43))  # C2 E2 G2, one octave below range
    assert result.ok
    assert result.octave_shift == 12
    assert result.note_range == ("C3", "G3")


def test_high_song_shifts_down():
    result = validate(ev(96, 100))  # C7 E7
    assert result.ok
    assert result.octave_shift == -24


def test_span_crossing_c_boundary_rejected():
    # A2 to G5 spans < 3 octaves but no C-aligned window holds it.
    result = validate(ev(45, 79))
    assert not result.ok
    assert "C-to-B" in result.errors[0]


def test_accidentals_and_range_both_reported():
    result = validate(ev(30, 61, 90))
    assert not result.ok
    assert len(result.errors) == 2


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
