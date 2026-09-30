"""Name normalisation for matching the same person across honorific changes.

"Dato' Seri Anwar bin Ibrahim", "Dato' Seri Anwar Ibrahim" and "Tuan Anwar bin Ibrahim" all have the
core name "anwar ibrahim".

- Leading titles are removed; multi-word titles only as a whole: "Tan" is a title only in "Tan Sri"
  (it is also a surname), "Seri"/"Sri" only right after Dato'/Datuk ("Tuan Sri Ram" keeps "Sri").
- Titles that also appear inside names ("bin Haji Yusof", "bin Tun Hussein", "bin Dato' Mohd Nor")
  are removed anywhere: Haji, Hajah, Hj, Dato', Datuk, Tun, Dr.
- "Name @ Alias": the core is the part before "@"; aliases() gives the part after it.
- Every apostrophe look-alike (’ ʼ ‘ ` ´) is treated the same; "Dato'Seri" is split.
"""

from __future__ import annotations

import re
import unicodedata

LEADING_TITLES = {
    "tuan", "puan", "cik", "dato", "datuk", "datin", "tun", "toh", "senator", "yb", "yang", "berhormat",
    "amat", "mulia", "dr", "ir", "ts", "haji", "hajah", "hj", "hjh", "ustaz", "ustazah", "prof", "profesor",
    "madya", "emeritus", "kapten", "komander", "mejar", "leftenan", "jeneral", "laksamana", "sahabat",
}  # fmt: skip
# Only titles right after Dato'/Datuk/another continuation ("Dato' Seri Utama", "Dato' Seri Diraja").
TITLE_CONTINUATIONS = {
    "seri",
    "sri",
    "utama",
    "panglima",
    "amar",
    "indera",
    "wira",
    "setia",
    "paduka",
    "diraja",
}
# Standard abbreviations of ONE name only. "Mohd" is not here: it abbreviates several spellings.
EXPAND = {"abd": "abdul"}
AFTER_WHICH_CONTINUE = {"dato", "datuk", "datin", "toh"} | TITLE_CONTINUATIONS
ANYWHERE_TITLES = {"haji", "hajah", "hj", "hjh", "dato", "datuk", "tun", "dr"}
CONNECTORS = {"bin", "binti", "bt", "bte", "b", "a/l", "a/p", "anak"}
_APOSTROPHES = str.maketrans({c: "'" for c in "’‘ʼ`´′"})


def _prep(name: str) -> str:
    text = unicodedata.normalize("NFKC", name).translate(_APOSTROPHES)
    text = re.sub(r"\b(Dato|Datuk)'(?=[A-Za-z])", r"\1' ", text)  # "Dato'Seri" -> "Dato' Seri"
    text = re.sub(r"\([^)]*\)", " ", text)  # "(Dr.)", "(B)"
    text = re.sub(r"\s+(TLDM|TUDM|TDM)\b.*$", "", text.strip())  # military post-nominals
    return re.sub(
        r"(,\s*[A-Z][A-Za-z]{1,5}\.?\s*)+$", "", text.strip(" .,")
    )  # ", Pjn.", ", Asdk.", "., Dimp."


def tokens(name: str) -> list[str]:
    text = _prep(name).lower().replace("a/l", " a/l ").replace("a/p", " a/p ")
    return [EXPAND.get(t, t) for t in re.split(r"[^\w/]+", text.replace("'", "")) if t]


def _core(toks: list[str]) -> str:
    i = 0
    while i < len(toks):
        t, nxt = toks[i], toks[i + 1] if i + 1 < len(toks) else ""
        prev = toks[i - 1] if i else ""
        if t in LEADING_TITLES:
            i += 1
        elif t in ("tan", "puan") and nxt == "sri":
            i += 2
        elif t in TITLE_CONTINUATIONS and i > 0 and prev in AFTER_WHICH_CONTINUE:
            i += 1
        else:
            break
    return " ".join(t for t in toks[i:] if t not in CONNECTORS and t not in ANYWHERE_TITLES)


def core_name(name: str) -> str:
    return _core(tokens(name.split("@")[0]))


def aliases(name: str) -> list[str]:
    """Core forms of the names after "@" ("Gapari bin Katingan @ Geoffrey Kitingan" -> ["geoffrey kitingan"])."""
    return [c for part in name.split("@")[1:] if (c := _core(tokens(part)))]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
