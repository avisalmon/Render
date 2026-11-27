"""Reading Avi's research pages by meaning (Epic P, sprint P.2).

The reference holds, per institution, an overview page and a researchers
page that his site generated in October 2025. Each page was generated on its
own, so they do not share one markup: a researcher is sometimes an <h3>
with a title, sometimes a div called researcher-name, sometimes an English
name under an emoji heading. The first import (A.2) read a few class names
and kept names, areas and links; this module reads what the page says:

- a person is a block that starts with a name carrying a title (פרופ', ד"ר,
  Prof., Dr.) or sits in an element whose class says "name";
- an h-index is a number next to the words h-index, citations are a number
  before the word ציטוטים, "נכון ל" with a year dates them;
- a publication is an item under a heading that says פרסומים (or a
  publication-item), a prize is a line that says פרס / Prize / Nobel / ERC;
- on the overview page, a fact is a number next to a label, a faculty split
  is a name next to "N סטודנטים" or a percentage, a timeline is a year next
  to a sentence, and a section is an <h2> with the text under it.

Pure functions over HTML strings, no Django, so the tests run them on small
pages in several vocabularies and, when the reference folder is present, on
all of it. What a page does not say stays empty; nothing here guesses.
"""
import html as html_lib
import re

TITLE_RE = re.compile(r"(?:פרופ'|פרופ׳|פרופ’|פרופ\b|ד\"ר|ד״ר|ד'ר|Prof\.|Prof\b|Dr\.|Dr\b)")
YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")
NUM_RE = re.compile(r"[~≈]?\d[\d,.]*\+?")
LABEL_WORDS = ("ציטוטים", "citations", "h-index", "h index", "hindex", "נכון ל", "מאמרים", "פרסומים", "publications")
UNIT_WORDS = ("פקולטה", "הפקולטה", "בית הספר", "ביה\"ס", "ביה״ס", "בית ספר", "המחלקה", "מחלקה", "חוג", "School", "Faculty",
              "Department", "Dept")
POSITION_WORDS = ("פרופסור", "מרצה", "ראש ", "דיקן", "נשיא", "רקטור", "Professor", "Lecturer", "Head", "Dean", "Chair",
                  "עמית", "חוקר", "Fellow", "Senior", "PI", "מנהל")
PRIZE_KINDS = (("נובל", "nobel"), ("Nobel", "nobel"), ("פרס ישראל", "israel_prize"), ("Israel Prize", "israel_prize"),
               ("וולף", "wolf"), ("Wolf Prize", "wolf"), ("א.מ.ת", "emet"), ("אמ\"ת", "emet"), ("EMET", "emet"),
               ("טיורינג", "turing"), ("Turing", "turing"), ("ERC", "erc"))
PRIZE_WORDS = ("פרס", "Prize", "Award", "ERC", "Fellow", "עמית ", "מדליית", "Medal")
PUB_HEADS = ("פרסומים", "publications", "ספרים", "מאמרים", "books", "selected works", "עבודות")
SECTION_KINDS = (("סקירה", "overview"), ("אודות", "overview"), ("מצוינות מחקרית", "research"), ("מחקר", "research"),
                 ("יזמות", "innovation"), ("חדשנות", "innovation"), ("דירוג", "rankings"), ("מבנה אקדמי", "structure"),
                 ("פקולטות", "structure"), ("בתי ספר", "structure"), ("תוכניות", "programs"), ("תכניות", "programs"),
                 ("לימוד", "programs"), ("בינה מלאכותית", "ai"), ("AI", "ai"), ("חוזק", "strengths"),
                 ("מאפיינים ייחודיים", "strengths"), ("הישגים", "strengths"), ("שיתופי פעולה", "collaborations"),
                 ("שותפויות", "collaborations"), ("היסטוריה", "history"), ("ציוני דרך", "history"))
SKIP_SECTIONS = ("רוצים לגלות", "סטטיסטיקות", "התפלגות", "קישורים", "מקורות", "מחקר במספרים", "ציוני דרך",
                 "חתני פרס", "זוכי פרס", "פרסומים")
FACT_KEYS = (("תכניות", "programs_count"), ("תוכניות", "programs_count"), ("מסלולי", "programs_count"),
             ("תואר ראשון", "students_undergrad"), ("תארים מתקדמים", None), ("סטודנטים", "students_total"),
             ("students", "students_total"), ("חברי סגל", "faculty_total"), ("סגל", "faculty_total"), ("faculty", "faculty_total"),
             ("שנת ייסוד", "founded"), ("נוסד", "founded"), ("founded", "founded"), ("פקולטות", "faculties_count"),
             ("בתי ספר", "schools_count"), ("מחלקות", "departments_count"), ("בוגרים", "alumni_total"),
             ("מרכזי מחקר", "research_centers_count"),
             ("קמפוסים", "campuses_count"), ("חברות הזנק", "startups_count"), ("סטארט", "startups_count"))


# ------------------------------------------------------------------ helpers

def text_of(fragment):
    """Visible text of an HTML fragment, whitespace folded, entities decoded,
    icon-font tags and emoji pictograms dropped."""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment or "", flags=re.S)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    s = re.sub(r"[\U0001F300-\U0001FAFF☀-➿️‍]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _body(page):
    i = page.find("<body")
    s = page[i:] if i >= 0 else page
    s = re.sub(r"<(script|style|nav|footer)[^>]*>.*?</\1>", " ", s, flags=re.S)
    return re.sub(r"<!--.*?-->", " ", s, flags=re.S)


def number(s):
    """'33,000+' -> (33000, approximate False); '~90' -> (90, True); None when
    there is no number, or when it reads as a year or an h= pattern."""
    if s is None:
        return None, False
    s = str(s).strip()
    approx = s.startswith(("~", "≈")) or s.endswith("+") or "כ-" in s or "כ־" in s
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s.replace(" ", ""))
    if not m:
        return None, False
    try:
        return float(m.group(0).replace(",", "")), approx
    except ValueError:
        return None, False


BLOCK_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "span", "td", "dd", "dt", "strong", "em", "a")


def blocks(fragment):
    """Every element of a fragment as (tag, class, text), nested ones too, in
    the order they open. A real tag walk, because a regex that stops at the
    first closing tag swallows a wrapper's children and loses the value next
    to a label."""
    out = []
    stack = []
    for m in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>", fragment):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if tag not in BLOCK_TAGS:
            continue
        if not closing:
            if attrs.rstrip().endswith("/"):
                continue
            cls = re.search(r'class="([^"]*)"', attrs)
            stack.append((tag, cls.group(1) if cls else "", m.end(), len(out)))
            out.append(None)
        else:
            for k in range(len(stack) - 1, -1, -1):
                if stack[k][0] == tag:
                    open_tag, cls, start, slot = stack.pop(k)
                    del stack[k:]
                    out[slot] = (open_tag, cls, text_of(fragment[start:m.start()]))
                    break
    return [b for b in out if b and b[2]]


def split_name(raw):
    """'פרופ\\' שי מנור (Shie Mannor)' -> ('פרופ׳', 'שי מנור', 'Shie Mannor');
    'Dr. Zohar Barnett-Itzhaki' -> ('ד״ר', '', 'Zohar Barnett-Itzhaki')."""
    s = text_of(raw)
    s = re.sub(r"\b(נובל|Nobel)\s*\d{4}\b", "", s).strip()
    title = ""
    m = TITLE_RE.match(s)
    if m:
        t = m.group(0)
        title = "פרופ׳" if t.startswith(("פרופ", "Prof")) else "ד״ר"
        s = s[m.end():].lstrip("'’׳. ").strip()
    en = ""
    p = re.search(r"\(([^)]*[A-Za-z][^)]*)\)", s) or re.search(r"\(([^)]*[֐-׿][^)]*)\)", s)
    if p:
        inner = p.group(1).strip()
        s = (s[:p.start()] + s[p.end():]).strip(" ,-–")
        if re.search(r"[֐-׿]", inner) and not re.search(r"[֐-׿]", s):
            s, en = inner, s  # 'Yossi Levi-Belz (יוסי לוי-בלז)'
        else:
            en = inner
    if not re.search(r"[֐-׿]", s) and re.search(r"[A-Za-z]", s):
        en, s = en or s, ""
    return title, s.strip(), en.strip()


def normal_name(s):
    """A key for matching the same person across pages: no title, no
    parentheses, no quotes, Hebrew or Latin letters only, lowercased."""
    _, he, en = split_name(s)
    base = he or en
    base = re.sub(r"[\"'’׳״`.\-–]", "", base)
    return re.sub(r"\s+", " ", base).strip().lower()


# ------------------------------------------------------------------ people

def person_blocks(page):
    """Split a researchers page into one HTML block per person."""
    body = _body(page)
    if 'class="researcher-card"' in body or 'class="research-card"' in body:
        parts = re.split(r'(?=<div class="(?:researcher|research)-card")', body)
        return [p for p in parts[1:] if TITLE_RE.search(text_of(p)[:400]) or re.search(r'class="[^"]*name', p)]
    heads = [m for m in re.finditer(r"<h[2-4][^>]*>(.*?)</h[2-4]>", body, re.S) if _is_person_heading(m.group(1))]
    out = []
    for i, m in enumerate(heads):
        start = body.rfind("<", 0, m.start())
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        out.append(body[start:end])
    return out


def _is_person_heading(inner):
    t = text_of(inner)
    return bool(TITLE_RE.search(t)) and len(t) <= 90 and "הערה" not in t


def _name_of(block):
    m = re.search(r'class="[^"]*\bname[^"]*"[^>]*>(.*?)</', block, re.S)
    if m and text_of(m.group(1)):
        return text_of(m.group(1))
    for h in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", block, re.S):
        t = text_of(h.group(1))
        if TITLE_RE.search(t) and len(t) <= 90:
            return t
    t = text_of(block)[:200]
    m = TITLE_RE.search(t)
    if m:
        return t[m.start():].split(" | ")[0][:90]
    return ""


def read_person(block):
    """One researcher's block -> a dict: title, name_he, name_en, position,
    unit, focus, bio, h_index, h_approx, citations, cites_approx, as_of_year,
    publications [(title, venue, year)], links [(kind, url)],
    prizes [(kind, title, year)]."""
    name_raw = _name_of(block)
    title, he, en = split_name(name_raw)
    bl = blocks(block)
    texts = [t for _, _, t in bl]
    person = {"title": title, "name_he": he, "name_en": en, "position": "", "unit": "", "focus": "", "bio": "",
              "h_index": None, "h_approx": False, "citations": None, "cites_approx": False, "as_of_year": None,
              "publications": [], "links": [], "prizes": []}
    if not (he or en):
        return person
    # the line under the name: position | unit. Never a block that holds the
    # name itself (a wrapper), explicit classes before plain divs.
    def holds_name(t):
        return (he and he in t) or (en and en in t) or t == name_raw

    candidates = [(tag, cls, t) for tag, cls, t in bl
                  if not holds_name(t) and 2 < len(t) <= 160 and not re.match(r"(h-?index|ציטוטים|\d)", t, re.I)]
    explicit = [c for c in candidates if re.search(r"(title|position|dept|department|role|affiliation|unit)", c[1])]
    plain = [c for c in candidates if c[0] == "div" and any(w in c[2] for w in UNIT_WORDS + POSITION_WORDS)]
    for tag, cls, t in explicit + plain:
        if "focus" in cls or "publication" in cls:
            continue
        parts = [p.strip(" •·-–") for p in re.split(r"\s*[|•·]\s*", t) if p.strip()]
        for p in parts:
            if any(w in p for w in UNIT_WORDS) and not person["unit"]:
                person["unit"] = p[:200]
            elif not person["position"] and len(p) < 120 and (any(w in p for w in POSITION_WORDS) or "position" in cls
                                                             or "title" in cls):
                person["position"] = p[:120]
        if person["unit"] or person["position"]:
            break
    # focus: a "focus" class, or "התמחות:" / "תחומי מחקר" line, or tags
    for tag, cls, t in bl:
        if "focus" in cls and t and len(t) < 300:
            person["focus"] = re.sub(r"^(התמחות|תחומי מחקר|Focus|Research)[:\s]*", "", t).strip()[:300]
            break
    if not person["focus"]:
        tags = [t for tag, cls, t in bl if re.fullmatch(r"(tag|research-tag|badge|chip)", cls.split()[0] if cls else "")
                and len(t) < 60 and not re.search(r"h-?index|ציטוטים|ORCID|\d{4}", t, re.I)]
        if tags:
            person["focus"] = ", ".join(dict.fromkeys(tags))[:300]
    if not person["focus"]:
        for t in texts:
            m = re.match(r"^(?:תחומי מחקר|התמחות|תחום)[:\s]+(.+)$", t)
            if m and len(m.group(1)) < 300:
                person["focus"] = m.group(1).strip()
                break
    # metrics: label/value pairs, then regex fallbacks
    plain = text_of(block)
    pair = _value_before_label(bl, ("h-index", "h index", "hindex"))
    if pair is not None:
        person["h_index"], person["h_approx"] = pair
    else:
        m = re.search(r"h[\s\-]?index\s*[:=]?\s*([~≈]?\d+\+?)", plain, re.I) or re.search(r"\bh\s*=\s*(\d+)", plain)
        if m:
            v, approx = number(m.group(1))
            if v is not None and v < 400:
                person["h_index"], person["h_approx"] = int(v), approx or "~" in m.group(0)
    pair = _value_before_label(bl, ("ציטוטים", "citations"))
    if pair is not None:
        person["citations"], person["cites_approx"] = pair
    else:
        m = re.search(r"(?<![\w\-])([~≈]?\d[\d,]*\+?)\s*(?:ציטוטים|citations)", plain, re.I) or \
            re.search(r"(?:ציטוטים|citations)\s*[:=]\s*([~≈]?\d[\d,]*\+?)", plain, re.I)
        if m:
            v, approx = number(m.group(1))
            if v is not None:
                person["citations"], person["cites_approx"] = int(v), approx
    m = re.search(r"נכון ל[:\-־\s]*(?:שנת\s*)?(20\d\d)", plain) or _label_value(bl, "נכון ל")
    if m:
        person["as_of_year"] = int(m.group(1) if hasattr(m, "group") else m)
    # bio: the paragraphs
    paras = []
    for m in re.finditer(r"<p\b[^>]*>(.*?)</p>", block, re.S):
        t = text_of(m.group(1))
        t = re.sub(r"^(תחומי מחקר|תרומה מחקרית|מחקרים בולטים|הישגים|Research|Contribution)[:\s]+", "", t)
        if len(t) > 60 and not any(w in t[:30] for w in ("h-index", "ציטוטים")):
            paras.append(t)
    person["bio"] = "\n\n".join(dict.fromkeys(paras))[:2000]
    # publications: under a heading that says so
    person["publications"] = _publications(block)
    # links
    seen = set()
    for href in re.findall(r'href="(https?://[^"]+)"', block):
        href = html_lib.unescape(href)
        low = href.lower()
        if re.search(r"user=[A-Z]{4,}", href) or "TBD" in href or low.rstrip("/") in ("https://scholar.google.com",
                                                                                          "https://orcid.org",
                                                                                          "https://dblp.org"):
            continue  # the site's own placeholders
        kind = ("scholar" if "scholar.google" in low else "orcid" if "orcid.org" in low else "dblp" if "dblp" in low
                else "other" if any(d in low for d in ("researchgate", "linkedin", "semanticscholar", "github")) else
                "homepage" if any(d in low for d in (".ac.il", ".edu", ".org.il")) else None)
        if kind and kind not in seen:
            seen.add(kind)
            person["links"].append((kind, href[:200]))
    m = re.search(r"ORCID[:\s]*(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", plain)
    if m and "orcid" not in seen:
        person["links"].append(("orcid", "https://orcid.org/" + m.group(1)))
    # prizes: badges and lines that name one
    person["prizes"] = _prizes(block, bl)
    return person


def _value_before_label(bl, words):
    """metric boxes: a value element next to a label element."""
    for i, (tag, cls, t) in enumerate(bl):
        low = t.lower()
        if not (low in words or any(low.startswith(w) for w in words)) or len(t) > 40 or re.search(r"\d", t):
            continue  # a label is words only; a box that starts with the label and holds the number is not one
        near = [j for j in (i - 1, i + 1) if 0 <= j < len(bl)]
        near.sort(key=lambda j: 0 if re.search(r"value|number", bl[j][1]) else 1)
        for j in near:
            raw = bl[j][2].strip()
            if re.fullmatch(r"[~≈]?[\d,.]+\+?", raw) or re.fullmatch(r"h\s*=\s*\d+", raw):
                v, approx = number(raw.split("=")[-1])
                if v is not None:
                    return int(v), approx or raw.startswith(("~", "≈"))
    return None


def _label_value(bl, word):
    for i, (tag, cls, t) in enumerate(bl):
        if t.startswith(word):
            for j in (i - 1, i + 1):
                if 0 <= j < len(bl) and re.fullmatch(r"20\d\d", bl[j][2].strip()):
                    return bl[j][2].strip()
    return None


def _publications(block):
    out = []
    for item in re.finditer(r'class="publication-item"[^>]*>(.*?)</div>\s*</div>', block, re.S):
        inner = item.group(1)
        title = re.search(r'class="[^"]*title[^"]*"[^>]*>(.*?)</', inner, re.S)
        venue = re.search(r'class="[^"]*venue[^"]*"[^>]*>(.*?)(?:</|$)', inner, re.S)  # the item's last tag is cut off
        t = text_of(title.group(1) if title else inner).strip('"“”')
        v = text_of(venue.group(1)) if venue else ""
        if t:
            out.append(_pub(t, v))
    if out:
        return out[:8]
    # a list under a heading that says publications
    for m in re.finditer(r"<h[3-5][^>]*>(.*?)</h[3-5]>\s*(<ul\b.*?</ul>|<ol\b.*?</ol>|(?:<p\b.*?</p>\s*){1,6})", block, re.S):
        if any(w in text_of(m.group(1)).lower() for w in PUB_HEADS):
            for li in re.finditer(r"<(li|p)\b[^>]*>(.*?)</\1>", m.group(2), re.S):
                t = text_of(li.group(2))
                if 12 < len(t) < 400:
                    out.append(_pub(t, ""))
            break
    if not out:
        for m in re.finditer(r"<(?:p|div)\b[^>]*>\s*<strong>\s*(?:[^<]*(?:פרסומים|publications)[^<]*)</strong>\s*(.*?)</(?:p|div)>",
                             block, re.S | re.I):
            for part in re.split(r"<br\s*/?>|;", m.group(1)):
                t = text_of(part)
                if 12 < len(t) < 400:
                    out.append(_pub(t, ""))
    return out[:8]


def _pub(text, venue):
    year = None
    m = YEAR_RE.search(venue) or YEAR_RE.search(text)
    if m:
        year = int(m.group(1))
    title = text
    citation_style = bool(re.search(r"\bet al\b|\(\d{4}\)|,\s*(?:19|20)\d\d\b", text.split(" - ")[0]))
    if not venue and not citation_style:
        parts = re.split(r"\s+[-–]\s+", text, maxsplit=1)
        if len(parts) == 2 and len(parts[0]) > 8:
            q = re.search(r"[\"“”']([^\"“”']{8,})[\"“”']", text)
            if q:
                title, venue = q.group(1), re.sub(r"[\"“”'][^\"“”']{8,}[\"“”']", "", text).strip(" -–,")
            else:
                title, venue = parts[0], parts[1]
    return (title.strip('"“”').strip()[:300], venue.strip()[:200], year)


def _prizes(block, bl):
    """A prize is a short, badge-like line: a Nobel badge with its year, a
    chip or list item that starts with פרס / זוכה / מענק ERC. A sentence in
    a bio that happens to mention ERC is not one, nor is a wrapper block
    that holds the whole card."""
    out, seen = [], set()
    plain = text_of(block)
    for m in re.finditer(r"(?:פרס נובל|נובל|Nobel Prize|Nobel)(?:\s+((?:ב|ל)[א-ת]{3,}))?\D{0,12}((?:19|20)\d\d)", plain):
        key = ("nobel", m.group(2))
        field = m.group(1) or ""
        title = ("פרס נובל " + field).strip()
        if key not in seen:
            seen.add(key)
            out.append(("nobel", title, int(m.group(2))))
        elif field:  # the badge said "נובל 2004"; the bio says which: keep the fuller title
            out = [(k, title if (k, y) == ("nobel", int(m.group(2))) and len(title) > len(t) else t, y) for k, t, y in out]
    for tag, cls, t in bl:
        if tag not in ("li", "span", "div", "strong") or not 6 <= len(t) <= 120:
            continue
        if re.search(r"h-?index|ציטוטים|citations|פרסומים", t, re.I):
            continue
        badge_like = bool(re.search(r"badge|tag|chip|highlight|prize|award|honor", cls)) or tag in ("li", "strong")
        starts = t.startswith(("פרס ", "זוכה ", "זוכת ", "זכה ב", "זכתה ב", "מענק ERC", "ERC ", "Winner", "Recipient", "חתן פרס",
                               "כלת פרס", "עמית ", "Fellow"))
        if not (badge_like and (starts or re.match(r"^(?:ERC|מענק ERC)\b", t))):
            continue
        kind = next((k for needle, k in PRIZE_KINDS if needle in t), "other")
        if kind == "nobel":
            continue  # taken above with its year
        y = YEAR_RE.search(t)
        title = re.sub(r"^\W+", "", re.split(r"\s+[-–]\s+|[:(]", t)[0]).strip()[:300]
        if kind == "other" and not title.startswith(("פרס", "חתן פרס", "כלת פרס")):
            continue
        key = (kind, title[:40])
        if key not in seen:
            seen.add(key)
            out.append((kind, title, int(y.group(1)) if y else None))
    return out[:6]


def non_person_headings(page):
    """Headings of a people page that are not people (areas, intros): the
    first import took some of them for researchers."""
    body = _body(page)
    out = []
    for h in re.finditer(r"<h[2-4][^>]*>(.*?)</h[2-4]>", body, re.S):
        t = text_of(h.group(1))
        if t and not TITLE_RE.search(t) and len(t) <= 90:
            out.append(t)
    return out


def read_people(page):
    """All the researchers a page names, as dicts (see read_person), in page
    order, without the blocks that turned out not to be people."""
    out, seen = [], set()
    for block in person_blocks(page):
        p = read_person(block)
        key = normal_name(p["name_he"] or p["name_en"])
        if (p["name_he"] or p["name_en"]) and key and key not in seen:
            seen.add(key)
            out.append(p)
    return out


# ------------------------------------------------------------------ overview

def read_overview(page):
    """The overview page -> dict: tagline, facts [(key, value, approx, year,
    label)], split [(unit, students, approx, pct)], timeline [(year, text)],
    sections [(title, kind, text)], winners [(name, title, year)]."""
    body = _body(page)
    out = {"tagline": _tagline(body), "facts": _facts(body), "split": _split(body), "timeline": _timeline(body),
           "sections": _sections(body), "winners": _winners(body)}
    return out


def _tagline(body):
    """One line under the name: the page's subtitle after its <h1>, or the
    short opening line under its first heading."""
    for anchor in (r"<h1[^>]*>.*?</h1>", r"<h2[^>]*>.*?</h2>"):
        h = re.search(anchor, body, re.S)
        if not h:
            continue
        after = body[h.end():h.end() + 1500]
        for m in re.finditer(r"<(p|div|span)\b([^>]*)>(.*?)</\1>", after, re.S):
            t = text_of(m.group(3))
            if not t:
                continue
            if 12 <= len(t) <= 160 and not re.search(r"\d{3}|%", t) and "|" not in t and not t.endswith(":")                     and not t.startswith(("שם מלא", "שם:", "כתובת")) and re.search(r"[֐-׿]", t):
                return t
            break  # the first text under the heading was not a one-liner
    return ""


def _facts(body):
    out, seen = [], set()
    for m in re.finditer(r'<(?:div|span)\b[^>]*class="[^"]*(?:number|value)[^"]*"[^>]*>(.*?)</(?:div|span)>\s*'
                         r'<(?:div|span)\b[^>]*class="[^"]*label[^"]*"[^>]*>(.*?)</(?:div|span)>', body, re.S):
        value, label = text_of(m.group(1)), text_of(m.group(2))
        v, approx = number(value)
        if v is None or not label or not re.fullmatch(r"[~≈]?\d[\d,.]*\+?%?", value.replace(" ", "")):
            continue
        key = next((k for needle, k in FACT_KEYS if needle in label), None)
        if key is None or key in seen:
            continue
        year = None
        y = re.search(r"(20\d\d)(?:/\d\d)?", label)
        if y:
            year = int(y.group(1))
        if key == "founded" and not 1800 <= v <= 2030:
            continue
        seen.add(key)
        out.append((key, int(v) if float(v).is_integer() else v, approx, year, label))
    return out


def _split(body):
    """Students per faculty or school: a name next to 'N סטודנטים' and/or a
    percentage, inside one small element."""
    out, seen = [], set()
    for m in re.finditer(r'<div\b[^>]*class="[^"]*(?:faculty|school|unit)[^"]*"[^>]*>(.*?)</div>\s*</div>', body, re.S):
        inner = m.group(1)
        name = re.search(r'class="[^"]*\bname\b[^"]*"[^>]*>(.*?)</', inner, re.S) or \
            re.search(r"<h[3-5][^>]*>(.*?)</h[3-5]>", inner, re.S)
        text = text_of(inner)
        n = re.search(r"([~≈]?\d[\d,]*\+?)\s*(?:סטודנטים|students)", text, re.I)
        p = re.search(r"(\d{1,2}(?:\.\d)?)\s*%", text)
        if not name or not (n or p):
            continue
        nm = text_of(name.group(1))[:200]
        if not nm or nm in seen or len(nm) < 3:
            continue
        seen.add(nm)
        students, approx = number(n.group(1)) if n else (None, False)
        out.append((nm, int(students) if students else None, approx, float(p.group(1)) if p else None))
    return out


def _timeline(body):
    out, seen = [], set()
    for m in re.finditer(r'class="[^"]*timeline-item[^"]*"[^>]*>(.*?)(?=<div\b[^>]*class="[^"]*timeline-item|</(?:ol|ul|section)>|<h2)',
                         body, re.S):
        t = text_of(m.group(1))
        y = re.match(r"\D*((?:18|19|20)\d\d)(?:\s*[-–]\s*(?:18|19|20)?\d\d)?\s*[:\-–·]?\s*(.+)", t)
        if y and len(y.group(2)) > 8:
            year, text = int(y.group(1)), y.group(2).strip()[:300]
            if (year, text[:40]) not in seen:
                seen.add((year, text[:40]))
                out.append((year, text))
    if out:
        return out
    heads = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", body, re.S))
    for i, h in enumerate(heads):
        if not any(w in text_of(h.group(1)) for w in ("ציוני דרך", "היסטוריה", "אבני דרך")):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        for li in re.finditer(r"<(li|p|div)\b[^>]*>(.*?)</\1>", body[h.end():end], re.S):
            t = text_of(li.group(2))
            y = re.match(r"\D*((?:18|19|20)\d\d)\s*[:\-–·]?\s*(.{9,})", t)
            if y and len(t) < 320 and (int(y.group(1)), y.group(2)[:40]) not in seen:
                seen.add((int(y.group(1)), y.group(2)[:40]))
                out.append((int(y.group(1)), y.group(2).strip()[:300]))
    return out


def _sections(body):
    out = []
    heads = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", body, re.S))
    for i, m in enumerate(heads):
        title = re.sub(r"[^\w\s֐-׿,.:'\"()\-]", "", text_of(m.group(1))).strip()
        if not title or any(skip in title for skip in SKIP_SECTIONS):
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        text = paragraphs(body[m.end():end])
        if len(text) < 80:
            continue
        kind = next((k for needle, k in SECTION_KINDS if needle in title), "other")
        out.append((title[:200], kind, text[:6000]))
    return out


def paragraphs(chunk):
    """Block text out of a page fragment, one paragraph per block element,
    duplicates dropped (the first import's `_paragraphs`, kept in one place)."""
    chunk = re.sub(r"<(p|li|h3|h4|div)[^>]*>", " ¶ ", chunk)
    text = text_of(chunk)
    parts = [p.strip() for p in text.split("¶")]
    out, seen = [], set()
    for p in parts:
        if len(p) > 25 and p not in seen:
            seen.add(p)
            out.append(p)
    return "\n\n".join(out)


def _winners(body):
    """A prize-winners box: a name with the prize's field and year."""
    out = []
    for m in re.finditer(r'<div\b[^>]*class="[^"]*(?:nobel-winner|prize-winner|winner)\b[^"]*"[^>]*>(.*?)</div>\s*</div>', body, re.S):
        inner = m.group(1)
        name = re.search(r'class="[^"]*\bname\b[^"]*"[^>]*>(.*?)</', inner, re.S)
        if not name:
            continue
        t = text_of(inner)
        y = YEAR_RE.search(t)
        field = re.search(r'class="[^"]*\bfield\b[^"]*"[^>]*>(.*?)</', inner, re.S)
        out.append((text_of(name.group(1))[:160], text_of(field.group(1))[:200] if field else "", int(y.group(1)) if y else None))
    return out
