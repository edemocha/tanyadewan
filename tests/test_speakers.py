"""Speaker names and resolution. Placeholder people only; never real MPs (CLAUDE.md)."""

import pytest

from tanyadewan.parse.attendance import AttendanceEntry
from tanyadewan.parse.labels import parse_label
from tanyadewan.speakers.names import aliases, core_name
from tanyadewan.speakers.registry import Registry, chair_from_stage


@pytest.mark.parametrize("a, b", [
    ("Dato' Seri Lorem bin Ipsum", "Tuan Lorem Ipsum"),
    ("Datuk Seri Panglima Dr. Lorem bin Haji Ipsum", "Lorem bin Ipsum"),     # mid-name Haji, stacked titles
    ("Datoʼ Lorem bin Datoʼ Ipsum", "Dato' Lorem bin Ipsum"),      # U+02BC apostrophe, father's title
    ("Dato'Seri Lorem Ipsum", "Lorem Ipsum"),                               # glued title
    ("Datuk Lorem Ipsum, Pjn.", "Lorem Ipsum"),                             # post-nominal honour
    ("Tuan Lorem bin Abd Ipsum", "Lorem bin Abdul Ipsum"),                  # Abd = Abdul
    ("Tan Sri Dato' (Dr.) Lorem bin Ipsum", "Lorem Ipsum"),
    ("Senator Dato' Seri Diraja Prof. Emeritus Lorem Ipsum", "Lorem Ipsum"),
])  # fmt: skip
def test_same_person_same_core(a, b):
    assert core_name(a) == core_name(b)


@pytest.mark.parametrize("a, b", [
    ("Tuan Tan Lorem", "Tuan Lorem"),         # "Tan" is a surname unless followed by "Sri"
    ("Tuan Sri Lorem", "Tuan Lorem"),         # "Sri" is a name after Tuan (only a title after Dato'/Datuk)
    ("Tuan Lorem bin Mohd Ipsum", "Tuan Lorem bin Ipsum"),   # Mohd is not expanded or dropped
])  # fmt: skip
def test_different_people_stay_different(a, b):
    assert core_name(a) != core_name(b)


def test_at_alias():
    assert core_name("Datuk Lorem bin Ipsum @ Dolor Sit") == "lorem ipsum"
    assert aliases("Datuk Lorem bin Ipsum @ Dolor Sit") == ["dolor sit"]


def entry(name, seat=None, role=None, status="present"):  # type: ignore[no-untyped-def]
    return AttendanceEntry(status, name, role, name, seat)


D1, D2 = "2099-01-01", "2099-06-01"
SITTING_1 = [
    entry("Tan Sri Dato' Placeholder bin Chair", role="Yang di-Pertua Dewan Rakyat"),
    entry("Tuan Lorem bin Ipsum", "Kawasan_A"),
    entry("Puan Dolor binti Sit", "Kawasan_B", role="Menteri Contoh"),
    entry("Tuan Amet Consectetur", "Kawasan_C"),
]
SITTING_2 = [e for e in SITTING_1 if e.constituency != "Kawasan_C"] + [
    entry("Tuan Adipiscing Elit", "Kawasan_C")
]


@pytest.fixture()
def reg() -> Registry:
    r = Registry(alias_file=None)
    r.add_attendance(SITTING_1, D1)
    r.add_attendance(SITTING_2, D2)  # by-election: Kawasan_C changed hands
    return r


def resolve(reg, label, sitting=SITTING_1, when=D1, chair=None):  # type: ignore[no-untyped-def]
    return reg.resolve(parse_label(label), sitting, chair, when)


def sid(reg, name):  # type: ignore[no-untyped-def]
    return reg.by_core[core_name(name)].speaker_id


def test_name_and_seat(reg):  # type: ignore[no-untyped-def]
    r = resolve(reg, "Dato' Lorem bin Ipsum [Kawasan_A]")
    assert (r.speaker_id, r.method) == (sid(reg, "Lorem Ipsum"), "label_constituency")


def test_seat_is_checked_by_date(reg):  # type: ignore[no-untyped-def]
    assert resolve(reg, "Tuan Amet Consectetur [Kawasan_C]").method == "label_constituency"
    # after the by-election the seat belongs to someone else: a mismatch is never guessed
    assert resolve(reg, "Tuan Amet Consectetur [Kawasan_C]", SITTING_2, D2).speaker_id is None


def test_spelling_variant_only_within_the_sitting_and_seat(reg):  # type: ignore[no-untyped-def]
    r = resolve(reg, "Tuan Lorem bin Ipsun [Kawasan_A]")  # one-letter variant, same seat
    assert (r.speaker_id, r.method) == (sid(reg, "Lorem Ipsum"), "label_fuzzy")
    assert resolve(reg, "Tuan Lorem bin Ipsun [Kawasan_B]").speaker_id is None  # seat held by someone else
    assert resolve(reg, "Tuan Totally Different [Kawasan_A]").speaker_id is None


def test_role_labels_use_the_sittings_attendance(reg):  # type: ignore[no-untyped-def]
    r = resolve(reg, "Tuan Yang di-Pertua")
    assert (r.speaker_id, r.method) == (sid(reg, "Placeholder Chair"), "attendance_role")
    r = resolve(reg, "Menteri Contoh")
    assert (r.speaker_id, r.method) == (sid(reg, "Dolor Sit"), "attendance_role")
    r = resolve(reg, "Menteri Contoh [Puan Dolor binti Sit]")
    assert r.speaker_id == sid(reg, "Dolor Sit")


def test_unattributed_is_never_resolved(reg):  # type: ignore[no-untyped-def]
    for label in ("Seorang Ahli", "Beberapa Ahli"):
        r = resolve(reg, label)
        assert (r.speaker_id, r.method) == (None, "unattributed")


def test_bare_chair_needs_a_named_chair(reg):  # type: ignore[no-untyped-def]
    assert resolve(reg, "Tuan Pengerusi").method == "no_chair_named"
    r = resolve(reg, "Tuan Pengerusi", chair="Tuan Lorem bin Ipsum")
    assert (r.speaker_id, r.method) == (sid(reg, "Lorem Ipsum"), "chair_carried")


def test_seat_typo_with_exact_name(reg):  # type: ignore[no-untyped-def]
    r = resolve(reg, "Tuan Lorem bin Ipsum [Kawasan_Typo]")
    assert (r.speaker_id, r.method) == (sid(reg, "Lorem Ipsum"), "label_name_seat_unmatched")


def test_attendance_variants_merge_only_on_same_seat():
    r = Registry(alias_file=None)
    r.add_attendance([entry("Puan Dolor", "Kawasan_B")], D1)
    r.add_attendance([entry("Puan Dolor Sit", "Kawasan_B")], D2)  # fuller printing, same seat
    r.add_attendance([entry("Puan Dolor Amet", "Kawasan_Z")], D2)  # same first name, other seat
    assert len(r.by_core) == 2


def test_corrupt_attendance_list_teaches_no_seats():
    r = Registry(alias_file=None)
    r.add_attendance([entry("Tuan Lorem", "Kawasan_A"), entry("Puan Dolor", "Kawasan_B")], D1)
    r.add_attendance([entry("Tuan Lorem", "Kawasan_X"), entry("Puan Dolor", "Kawasan_X")], D2)  # corrupt list
    assert r.conflicts and ("kawasan x", D2) not in r.seats
    assert list(r.by_core["lorem"].constituencies) == ["Kawasan_A"]


def test_chair_from_stage_direction():
    assert chair_from_stage("Timbalan Yang di-Pertua (Dato' Lorem) mempengerusikan Mesyuarat") == (
        "Dato' Lorem",
        True,
    )
    assert chair_from_stage("Tuan Yang di-Pertua mempengerusikan Mesyuarat") == (None, True)
    assert chair_from_stage("Tepuk") == (None, False)
