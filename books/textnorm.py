"""Text the way a search and a matcher need it (spec BK2, 12.7).

Hebrew spines and catalogue records disagree in ways that are not errors:
vowel marks, final letters at the end of a word that an OCR read as the
regular form, geresh and gershayim written with three different quote
characters, an English title with or without "The". `normalize()` folds all
of that to one shape, stored in `search_text` columns and used on both sides
of every comparison, so "מִיכָאֵל שֶׁלִּי" and "מיכאל שלי" are the same string.

Identifiers: ISBN-10 and ISBN-13 are checked and folded to ISBN-13; a danacode
is the digits as printed (there is no public checksum to verify).
"""

import re
import unicodedata
from difflib import SequenceMatcher

NIQQUD = re.compile(r"[֑-ׇ]")
FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
QUOTES = str.maketrans({"׳": "", "״": "", "'": "", '"': "", "’": "", "‘": "", "“": "", "”": ""})
PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
SPACES = re.compile(r"\s+")
ARTICLES = ("the ", "a ", "an ")


def normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = NIQQUD.sub("", text)
    text = text.translate(FINALS).translate(QUOTES).lower()
    text = PUNCT.sub(" ", text)
    text = SPACES.sub(" ", text).strip()
    for article in ARTICLES:
        if text.startswith(article):
            text = text[len(article):]
            break
    return text


def tokens(text):
    return [tok for tok in normalize(text).split(" ") if tok]


def similarity(a, b):
    """0..1: sequence similarity blended with token overlap, both on the
    normalised forms. Cheap enough to rank a few hundred candidates."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    # How much of what was asked for is present, so a short query against a
    # long "title author" string is not punished for the string's length.
    recall = len(ta & tb) / max(len(ta), 1)
    return round(0.5 * seq + 0.5 * recall, 4)


def digits(value):
    return re.sub(r"[^0-9Xx]", "", str(value or "")).upper()


def isbn10_to_13(isbn10):
    core = "978" + isbn10[:9]
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(core))
    return core + str((10 - total % 10) % 10)


def valid_isbn13(isbn):
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(isbn[:12]))
    return (10 - total % 10) % 10 == int(isbn[12])


def valid_isbn10(isbn):
    if len(isbn) != 10 or not isbn[:9].isdigit() or not (isbn[9].isdigit() or isbn[9] == "X"):
        return False
    total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(isbn))
    return total % 11 == 0


def normalize_isbn(value):
    """ISBN-13 as a string, or None when it is not a valid ISBN."""
    raw = digits(value)
    if valid_isbn13(raw):
        return raw
    if valid_isbn10(raw):
        return isbn10_to_13(raw)
    return None


def normalize_danacode(value):
    """Digits as printed, 8 to 14 of them. A 13-digit number that starts
    like an ISBN but fails its checksum is a mistyped ISBN, not a danacode."""
    raw = re.sub(r"[^0-9]", "", str(value or ""))
    if len(raw) == 13 and raw[:3] in ("978", "979"):
        return None
    return raw if 8 <= len(raw) <= 14 else None


def identifier_scheme(value):
    """What a typed identifier most likely is: ('isbn13', v) / ('danacode', v) / None."""
    isbn = normalize_isbn(value)
    if isbn:
        return "isbn13", isbn
    dana = normalize_danacode(value)
    if dana:
        return "danacode", dana
    return None
