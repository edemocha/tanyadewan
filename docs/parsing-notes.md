# Parsing notes: what the Hansard PDFs actually look like

Findings from inspecting and parsing real sittings (Parlimen 15, Dec 2022 to Aug 2026), 27 Sep 2026.
This is the raw material for the README's "parsing challenges" section.

## Sources and coverage
- **Two official sources.**
  - `repositori.parlimen.gov.my` (DSpace) covers Dec 2022 to Dec 2024; its Penggal 4 collection is empty.
  - `www.parlimen.gov.my` exposes the archive as an XML tree and covers everything up to the current meeting.
  - One record per sitting. The repository is preferred where both list it, since that's where amended transcripts appear; the website URL is kept in `alternate_urls`.
  - The current meeting is on the website's main page before it reaches the archive tree.
- **File names come in five shapes**, all parsed without guessing:
  - `DR<Bil>-<DDMMYYYY>.pdf`
  - The same without `.pdf` (mid 2024).
  - `DR-<DDMMYYYY>` with no Bil. (late 2024 onward).
  - Amended transcripts: `DR49-09102023.PINDAAN20032025.pdf` (pindaan = amendment, dated 20 Mar 2025).
  - A trailing free-text note: `DR-15102025 - BDR APRIL - DISEMAK.PM.pdf` (disemak = revised). The note is kept verbatim.
  - File names can contain spaces, so URLs are escaped.
- **Drafts.** "Naskhah belum disemak" (unrevised copy) is printed on the cover of many sittings, including the amended 2023 file. Every record carries `is_draft` and a SHA-256 of the PDF. `--recheck-drafts` re-downloads drafts; a changed file moves the old one to `superseded/`.
- **Bil.** comes from the file name if present, else from the cover page.

## Text layer
- Born-digital, roughly 2,500 to 3,700 characters per page.
- **Exception: six sittings from Feb–Mar 2023, plus opening days.**
  - Pages render normally (bold labels, italic stage directions), but only the running header can be extracted as text; the body isn't in the text layer.
  - Both sources serve the same broken file, so switching source doesn't help. (The fetcher still checks: a copy with text on under 90% of pages is replaced by the other source's copy when that one is more complete.)
  - These pages are OCR'd with RapidOCR, approved 27 Sep 2026. See `src/tanyadewan/parse/ocr.py`.
- **OCR details that matter for attribution:**
  - A few lines (in our test, exactly the bold label lines) come out as garbage at one resolution but read perfectly at another. Low-confidence lines are re-read from crops at 150–400 dpi, and the best reading is kept.
  - A line still unreadable after that becomes a **boundary turn with no speaker** (`resolution: ocr_unreadable`). Text after it is never merged into the previous speaker.
  - OCR loses bold and italic, so they are restored from the label pattern, all-caps headings and brackets. Every turn from an OCR page has `ocr: true`, so OCR quality can be measured separately.
  - OCR reads the header and page number as one line ("DR.28.02.2023 31"). It is recognised and stripped.
- A PDF page with nothing on it at all (a real blank) is detected with a low-resolution render and skipped.

## Page furniture (stripped)
- Running header, in four spellings: `DR.14.03.2023`, `DR. 2.7.2024`, `DR 26.2.2024`, `DR 22.10.2025`.
- Page number: roman numerals in the front matter, arabic in the debate. Header and number appear in either order.
- The debate starts at the first arabic-numbered page. A later page whose number wasn't found is **still debate**; pages are never dropped.
- Time marks `■1040` sit on their own line. They are kept as `times` on the turn they fall in.

## Speaker turns
- **Speaker labels are bold, in every year 2022 to 2026.** A label is a bold run at the start of a line ending in `:`. It is joined across line breaks, because long ministerial titles wrap.
- A bold run can also swallow what is above the label (a heading, a question number, a subheading like `Kepala B.14 [Jadual] –`). The label is found backwards from the colon: the latest line that starts like a label, with balanced brackets.
- Label forms:
  - `Name [Constituency]` for an MP.
  - `Role [Name]` for a minister or the Deputy Speaker: **the brackets hold the name, not the seat**.
  - `Role, Name [Constituency]` occurs occasionally.
  - `Name` alone for someone already introduced.
  - `Tuan Yang di-Pertua` (the Speaker) and `Tuan Pengerusi` (the committee chair) with no name.
- **Unattributed:** `Seorang Ahli` / `Beberapa Ahli` ("a Member" / "several Members"). These are never resolved to a person.
- **Stage directions are italic**: `[Tepuk]`, `[Dewan riuh]`, `[Bangun]`. They are removed from speech text into `stage_directions`. A label followed only by a stage direction (`[Bangun]`, an MP rising) becomes an `action` turn with no text.
- **Interjections** are flagged: a short turn between two turns by the same other speaker, or any unattributed turn.
- **Sections** come from bold all-caps headings: Question Time, oral questions, bills, motions, statements, royal address.
- **Oral questions:** a number line, then a bold `Name [Seat]` followed by "minta Menteri … menyatakan …" (the written question). Replies carry `question_no`. Minister's Question Time has no printed numbers, so every question gets a running `question_group` for Q+A chunking.

## Attendance lists: the source of speaker identity
- **Titles vary.** "Ahli-Ahli Yang Hadir", "Ahli-ahli Yang Tidak Hadir", "… Di Bawah Peraturan Mesyuarat 91", "Senator Yang Turut Hadir", "(Samb/-)" continuations, "Digantung …" (suspended), and "KEHADIRAN AHLI-AHLI PARLIMEN" at the first sitting. Case and the trailing colon vary.
- **Two numbering styles**: one number per line (`1.`), or inline (`1 Perdana Menteri …, Name (Seat) 2 …`). Lists are split on **sequential** numbers only, so "P.M. 14" inside a role can't start an entry.
- **Role and name are split at the last comma followed by an honorific.** Roles contain commas ("Menteri Sumber Asli, Alam Sekitar dan Perubahan Iklim, Tuan …"). Some entries omit the comma entirely ("… (Undang-undang dan Reformasi Institusi) Tuan M. Kulasegaran").
- **Seats change hands**: by-elections in Kemaman, Pulai and Kinabatangan. A seat identifies a person only together with the sitting date.

## Names: the same person, printed differently
- Stacked and changing honorifics: "Dato' Seri Utama", "Datuk Seri Panglima", "Dato' Seri Diraja", "Prof. Emeritus".
- Titles inside names: "bin Haji Yusof", "bin Tun Hussein", "bin Dato' Mohd Nor".
- Post-nominal honours: ", Pjn.", ", Asdk.", "., Dimp.", "TLDM (B)".
- Aliases after "@": "Gapari bin Katingan @ Geoffrey Kitingan".
- "Abd" / "Abdul". "Mohd" is **not** normalised: it abbreviates several spellings.
- Four apostrophe characters (’ ʼ ‘ '), and "Dato'Seri" with no space.
- "Tan" is a title only in "Tan Sri" (it is also a surname). "Sri" is a title only after Dato'/Datuk ("Tuan Sri …" keeps it).
- **The Hansard itself has typos**: "Ibharim" for Ibrahim, "Hamdan" for "Hamzan", seat "Kuala fasal", "KassimP", a label giving one member's name with another member's seat.

## Resolution policy
Identity comes only from the attendance lists plus `src/tanyadewan/speakers/aliases.yaml`, which is curated by hand. Labels never create a person. Each turn records how it was resolved, from strongest to weakest:

| Method | Meaning |
|---|---|
| `label_constituency` | Name matches, and that person held the labelled seat on that date |
| `label_name` | Name matches exactly one person |
| `label_name_seat_unmatched` | Exact name, but the labelled seat is held by no one (a typo in the seat) |
| `label_fuzzy` | A spelling variant of exactly one person in *this sitting's* attendance list, and, if a seat is given, that seat's holder on that date |
| `attendance_role` | A role-only label matched to the one person holding that role in this sitting |
| `chair_named` | A chair label carrying the chair's name |
| `chair_carried` | A bare chair label, resolved to the chair most recently named in this sitting |

Unresolved turns keep a reason: `unattributed`, `unknown_name`, `ambiguous_name`, `seat_mismatch`, `no_chair_named`, `unknown_role`. A seat held by someone else is **never** resolved. The two Dec 2022 swearing-in sittings leave "Tuan Yang di-Pertua" unresolved: the Speaker was elected that day and isn't in that day's attendance list.

Check any method by eye with `scripts/spot_check.py --method <name>`.
