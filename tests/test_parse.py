"""Parsing on synthetic PDFs laid out like the Hansard (placeholder names and text only)."""

from tanyadewan.parse.attendance import parse_attendance, parse_entry, split_numbered
from tanyadewan.parse.extract import debate_start, extract_pages
from tanyadewan.parse.labels import parse_label
from tanyadewan.parse.lang import dominant_language
from tanyadewan.parse.segment import segment

HEADER = 4


def front_page(roman: str) -> list:
    return [[("DR.01.01.2099", "")], [(roman, "")], [("Ahli-Ahli Yang Hadir:", "")], [("1.", "")],
            [("Tuan Lorem bin Ipsum (Kawasan_A)", "")]]  # fmt: skip


def debate_pages() -> list:
    return [
        [  # page 1
            [("DR.01.01.2099", "")],
            [("1", "")],
            [("PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN", "b")],
            [("1.", "")],
            [("Tuan Lorem bin Ipsum [Kawasan_A]", "b"), (" minta Menteri Contoh menyatakan LOREM.", "")],
            [("Menteri Contoh dan Ujian [Puan Dolor binti", "b")],
            [("Sit]:", "b"), (" Terima kasih. MINISTER_REPLY_ONE", "")],
            [("berterusan di baris kedua. ", ""), ("[Tepuk]", "i")],
            [("Seorang Ahli:", "b"), (" [Bercakap tanpa pembesar suara]", "i")],
            [("Menteri Contoh dan Ujian [Puan Dolor binti Sit]:", "b"), (" SAMBUNG.", "")],
        ],
        [  # page 2: its page number is missing, but it is still debate
            [("DR.01.01.2099", "")],
            [("Tuan Yang di-Pertua:", "b"), (" Terima kasih.", "")],
            [("RANG UNDANG-UNDANG", "b")],
            [("Rang Undang-undang Contoh 2099", "b")],
            [("Tuan Amet [Kawasan_B]:", "b"), (" MP_B said LOREM.", "")],
            [("Tuan Lorem bin Ipsum [Kawasan_A]:", "b"), (" [Bangun]", "i")],
        ],
    ]


def parse(pdf):  # type: ignore[no-untyped-def]
    path = pdf([front_page("i"), front_page("ii"), *debate_pages()])
    pages = extract_pages(path, HEADER)
    return pages, *segment(pages, 220, 0.7)


def test_front_matter_and_page_furniture(pdf):  # type: ignore[no-untyped-def]
    pages, turns, _ = parse(pdf)
    assert debate_start(pages) == 2
    assert [p.label for p in pages] == ["i", "ii", "1", None]
    assert all("DR.01.01.2099" not in t.text for t in turns)
    assert turns[-1].page_start == 4  # the unnumbered page was not dropped


def test_turns_labels_and_sections(pdf):  # type: ignore[no-untyped-def]
    _, turns, _ = parse(pdf)
    got = [(t.kind, t.label.raw, t.section) for t in turns]
    assert got == [
        ("written_question", "Tuan Lorem bin Ipsum [Kawasan_A]", "oral_questions"),
        (
            "speech",
            "Menteri Contoh dan Ujian [Puan Dolor binti Sit]",
            "oral_questions",
        ),  # wrapped label joined
        ("action", "Seorang Ahli", "oral_questions"),  # only a stage direction, no words
        ("speech", "Menteri Contoh dan Ujian [Puan Dolor binti Sit]", "oral_questions"),
        ("speech", "Tuan Yang di-Pertua", "oral_questions"),
        ("speech", "Tuan Amet [Kawasan_B]", "bill"),
        ("action", "Tuan Lorem bin Ipsum [Kawasan_A]", "bill"),
    ]
    assert turns[0].question_no == 1 and turns[1].question_no == 1 and turns[1].question_group == 1
    assert turns[5].subheading == "Rang Undang-undang Contoh 2099"


def test_stage_directions_never_stay_in_speech(pdf):  # type: ignore[no-untyped-def]
    _, turns, _ = parse(pdf)
    reply = turns[1]
    assert reply.text == "Terima kasih. MINISTER_REPLY_ONE berterusan di baris kedua."
    assert reply.stage_directions == ["Tepuk"]
    assert turns[2].text == "" and turns[2].stage_directions == ["Bercakap tanpa pembesar suara"]
    assert turns[6].stage_directions == ["Bangun"]


def test_written_question_text_and_attribution(pdf):  # type: ignore[no-untyped-def]
    _, turns, _ = parse(pdf)
    q = turns[0]
    assert q.label.name == "Tuan Lorem bin Ipsum" and q.label.constituency == "Kawasan_A"
    assert q.text.startswith("minta Menteri Contoh")


def test_labels():
    assert parse_label("Tuan Lorem bin Ipsum [Kawasan_A]").constituency == "Kawasan_A"
    minister = parse_label("Menteri Contoh [Puan Dolor binti Sit]")
    assert (minister.role, minister.name, minister.constituency) == (
        "Menteri Contoh",
        "Puan Dolor binti Sit",
        None,
    )
    deputy = parse_label("Timbalan Yang'di-Pertua [Dato' Amet]")
    assert (deputy.role, deputy.name) == ("Timbalan Yang di-Pertua", "Dato' Amet")
    both = parse_label("Menteri Contoh, Datuk Seri Lorem bin Ipsum [Kawasan_C]")
    assert (both.role, both.name, both.constituency) == (
        "Menteri Contoh",
        "Datuk Seri Lorem bin Ipsum",
        "Kawasan_C",
    )
    for anon in ("Seorang Ahli", "Beberapa Ahli"):
        label = parse_label(anon)
        assert label.unattributed and label.name is None
    assert parse_label("Tuan Yang di-Pertua").role == "Tuan Yang di-Pertua"


def test_attendance_both_numbering_styles():
    per_line = ["Ahli-Ahli Yang Hadir:", "1.", "Menteri Contoh, Sains dan Ujian, Tuan Lorem bin Ipsum",
                "(Kawasan_A)", "2.", "Puan Dolor (Kawasan_B)", "Ahli-Ahli Yang Tidak Hadir:", "1.", "Tuan Amet (Kawasan_C)",
                "Senator Yang Turut Hadir:", "1.", "Timbalan Menteri Contoh, Senator Puan Sit", "Diterbitkan Oleh:", "1.", "X"]  # fmt: skip
    got = [(e.status, e.role, e.name, e.constituency) for e in parse_attendance(per_line)]
    assert got == [
        ("present", "Menteri Contoh, Sains dan Ujian", "Tuan Lorem bin Ipsum", "Kawasan_A"),
        ("present", None, "Puan Dolor", "Kawasan_B"),
        ("absent", None, "Tuan Amet", "Kawasan_C"),
        ("present_senator", "Timbalan Menteri Contoh", "Senator Puan Sit", None),
    ]
    inline = ["KEHADIRAN AHLI-AHLI PARLIMEN", "1 Menteri Contoh, Tuan Lorem (Kawasan_A) 2 Puan Dolor",
              "(Kawasan_B) 3 Timbalan Menteri Di Bawah P.M. 14 Contoh, Tuan Amet (Kawasan_C)"]  # fmt: skip
    assert [e.name for e in parse_attendance(inline)] == ["Tuan Lorem", "Puan Dolor", "Tuan Amet"]


def test_split_numbered_ignores_out_of_sequence_numbers():
    assert split_numbered("1 Satu 2 Dua di bawah P.M. 14 3 Tiga") == ["Satu", "Dua di bawah P.M. 14", "Tiga"]


def test_role_printed_without_comma():
    e = parse_entry("Timbalan Menteri Contoh (Undang-undang Ujian) Tuan Lorem (Kawasan_A)", "present")
    assert (e.role, e.name, e.constituency) == (
        "Timbalan Menteri Contoh (Undang-undang Ujian)",
        "Tuan Lorem",
        "Kawasan_A",
    )


def test_language_tag():
    assert dominant_language("saya fikir yang ini dan itu untuk kita", 3, 0.25) == "ms"
    assert dominant_language("we think that the plan is for the people", 3, 0.25) == "en"
    assert dominant_language("saya rasa the plan ini is not untuk kita and the rakyat", 3, 0.25) == "mixed"
    assert dominant_language("LOREM IPSUM", 3, 0.25) == "unknown"


def test_honorific_before_a_ministerial_role_is_not_part_of_the_name() -> None:
    # Real labels: the honorific used to make "Perdana Menteri dan Menteri Kewangan" look like an MP's name and
    # the minister's own name look like a seat, so the turn could only match the wrong person or no one.
    for raw in (
        "Yang Amat Berhormat Perdana Menteri dan Menteri Kewangan [Dato' Seri Anwar bin Ibrahim]",
        "Yang Berhormat Perdana Menteri dan Menteri Kewangan [Dato' Seri Anwar bin Ibrahim]",
    ):
        label = parse_label(raw)
        assert label.name == "Dato' Seri Anwar bin Ibrahim"
        assert label.role == "Perdana Menteri dan Menteri Kewangan"
        assert label.constituency is None
        assert label.raw == raw  # the printed label is kept as printed
    # An honorific before a person stays as it was: a name with a seat.
    mp = parse_label("Yang Berhormat Tuan Syed Saddiq bin Syed Abdul Rahman [Muar]")
    assert mp.name == "Yang Berhormat Tuan Syed Saddiq bin Syed Abdul Rahman" and mp.constituency == "Muar"
    assert mp.role is None
