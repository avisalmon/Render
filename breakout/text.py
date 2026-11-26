"""Person-typed text, tidied once on the way in (spec 5: "sanitizer on every
person-typed text"), and a readable ASCII slug for a Hebrew title.

Escaping on the way out is Django's: no template in this app marks a
person's text as safe, and a test greps for the ways of doing so. What is done here is what
escaping cannot do: strip control characters and zero-width marks a paste
brings along, normalise line endings, and keep a text from being mostly
blank lines.
"""

import re
import unicodedata

from django.utils.text import slugify

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​‌‍⁠﻿]")
_MANY_BLANKS = re.compile(r"\n{3,}")


def tidy(text, one_line=False):
    """Normalised text: no control characters, unix line breaks, at most one
    blank line in a row, trimmed. `one_line` folds everything to one line."""
    text = unicodedata.normalize("NFC", str(text or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = _MANY_BLANKS.sub("\n\n", text)
    if one_line:
        text = " ".join(text.split())
    return text.strip()


# Hebrew letters to Latin, for a slug a person can read in a URL. Final
# forms map like their base letter; vowels are not written, as in street signs.
_HEBREW = {
    "א": "a", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "ch", "ט": "t", "י": "y",
    "כ": "k", "ך": "k", "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "a", "פ": "p", "ף": "f",
    "צ": "tz", "ץ": "tz", "ק": "k", "ר": "r", "ש": "sh", "ת": "t",
}


def transliterate(text):
    return "".join(_HEBREW.get(ch, ch) for ch in text or "")


def slug_for(title, taken, max_length=60):
    """An ASCII slug from a (Hebrew) title, unique against `taken(slug) -> bool`."""
    base = slugify(transliterate(title))[: max_length - 4].strip("-") or "experience"
    slug, n = base, 2
    while taken(slug):
        slug = f"{base}-{n}"
        n += 1
    return slug
