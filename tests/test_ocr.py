"""Restoring structure to OCR'd lines (placeholder names only). No OCR engine needed."""

from tanyadewan.parse.labels import parse_label
from tanyadewan.parse.ocr import UNREADABLE_LABEL, OcrLine, merge_rows, style_lines


def lines(*texts: str, low: tuple[int, ...] = ()) -> list[OcrLine]:
    return [OcrLine(t, 0.5 if i in low else 0.99, 50, 20 * i, 10) for i, t in enumerate(texts)]


def bold_parts(styled):  # type: ignore[no-untyped-def]
    return [[t for t, b, _ in row if b] for row in styled]


def test_labels_headings_and_stage_directions():
    styled = style_lines(lines(
        "PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN",
        "Tuan Lorem bin Ipsum [Kawasan_A]: Terima kasih. [Tepuk] LOREM.",
        "sambungan ucapan LOREM IPSUM.",
        "[Dewan riuh]",
        "1040",
    ), 0.85, 220)  # fmt: skip
    assert bold_parts(styled) == [
        ["PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN"],
        ["Tuan Lorem bin Ipsum [Kawasan_A]:"],
        [],
        [],
        [],
    ]
    assert (" [Tepuk]", False, True) not in styled[1] and ("[Tepuk]", False, True) in styled[1]
    assert styled[3] == [("[Dewan riuh]", False, True)]
    assert styled[4] == [("■1040", False, False)]


def test_wrapped_label_over_two_lines():
    styled = style_lines(
        lines("Menteri Contoh (Hal Ehwal Lorem, Ipsum", "dan Dolor) [Datuk Amet]: Terima kasih."), 0.85, 220
    )
    assert bold_parts(styled) == [["Menteri Contoh (Hal Ehwal Lorem, Ipsum"], ["dan Dolor) [Datuk Amet]:"]]


def test_written_question_name_is_bold():
    styled = style_lines(lines("Tuan Lorem [Kawasan_A] minta Menteri Contoh menyatakan LOREM."), 0.85, 220)
    assert bold_parts(styled) == [["Tuan Lorem [Kawasan_A]"]]


def test_unreadable_line_becomes_a_boundary_with_no_speaker():
    styled = style_lines(
        lines("Tuan Lorem [Kawasan_A]: LOREM.", "Timn yY Y : Y g Ya", "IPSUM.", low=(1,)), 0.85, 220
    )
    assert styled[1] == [(UNREADABLE_LABEL + ":", True, False)]
    label = parse_label(UNREADABLE_LABEL)
    assert label.unreadable and label.name is None and not label.unattributed


def test_sentences_with_colons_are_not_labels():
    styled = style_lines(lines("Jumlahnya seperti berikut: LOREM, IPSUM."), 0.85, 220)
    assert bold_parts(styled) == [[]]


def test_boxes_on_one_line_are_merged_left_to_right():
    boxes = [
        OcrLine("IPSUM", 0.9, 200, 100, 12),
        OcrLine("LOREM", 0.95, 50, 102, 12),
        OcrLine("next", 0.9, 50, 130, 12),
    ]
    assert [(ln.text, ln.score) for ln in merge_rows(boxes)] == [("LOREM IPSUM", 0.9), ("next", 0.9)]
