"""Cheap AI-powered semantic search over the course catalog.

Given a free-text query, ask a tiny OpenAI model which published courses are
relevant — matching by *meaning* (topic, synonym, tool, abbreviation), not by
coincidental substrings. Results are cached so repeat queries cost nothing, and
the call always degrades gracefully to substring matching when the API key is
absent or the request fails, so search never breaks.

This is the first instance of a site-wide pattern: build a compact metadata
catalog of some content, hand it + the query to a small model, get back the
relevant items ranked. The same `_ask_model` shape can later back community /
showcase / global search.
"""
import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 6   # 6h — the catalog changes rarely; saves repeat spend
_MAX_QUERY = 120


def _search_model():
    return getattr(settings, "OPENAI_SEARCH_MODEL", "") or settings.OPENAI_DEFAULT_MODEL


def course_search_doc(course):
    """The compact metadata for one course — exactly what the model 'sees'."""
    return {
        "slug": course.slug,
        "title": course.title,
        "title_en": course.title_en,
        "domain": course.get_domain_display(),
        "level": course.get_difficulty_display(),
        "about": (course.description or "")[:240],
    }


def _substring_rank(query, docs):
    """Offline fallback: keep any course whose metadata contains the query."""
    q = query.lower()
    return [d["slug"] for d in docs
            if q in " ".join(str(v) for v in d.values()).lower()]


_SYSTEM_PROMPT = (
    "You are the search engine for an online course catalog. The site is in "
    "Hebrew; queries may be Hebrew or English. You receive a JSON array of "
    "courses and a user query. Return the slugs of the courses that are genuinely "
    "relevant to the query, ordered most-relevant first. Match by MEANING — topic, "
    "synonyms, tools, abbreviations (e.g. 'ESP'/'ESP32' -> microcontroller/Arduino "
    "courses; '3D'/'הדפסת תלת מימד' -> 3D-printing courses; 'בינה' -> AI courses). "
    "Never match on a coincidental substring. If nothing is genuinely relevant, "
    'return an empty list. Respond ONLY as JSON: {"slugs": ["slug-a", "slug-b"]}.'
)


def search_courses(query):
    """Return {'slugs': [...ranked...], 'mode': 'ai'|'fallback'|'empty'}.

    `slugs` is the relevant subset, most-relevant first. An empty query yields an
    'empty' result (the caller shows the full catalog). Never raises.
    """
    query = (query or "").strip()[:_MAX_QUERY]
    if not query:
        return {"slugs": [], "mode": "empty"}

    from .models import Course
    courses = list(Course.objects.filter(is_published=True).order_by("title"))
    docs = [course_search_doc(c) for c in courses]
    valid = {d["slug"] for d in docs}

    from .ai_chat import _is_stub_mode
    if _is_stub_mode():
        return {"slugs": _substring_rank(query, docs), "mode": "fallback"}

    # Cache key folds in the model + a fingerprint of the catalog, so adding or
    # editing a course transparently invalidates stale results.
    fp = hashlib.sha1(
        (json.dumps(docs, ensure_ascii=False, sort_keys=True)
         + "\n" + query.lower()).encode("utf-8")
    ).hexdigest()   # folds catalog + query into an ASCII, memcached-safe key
    ckey = f"coursesearch:{_search_model()}:{fp}"
    cached = cache.get(ckey)
    if cached is not None:
        return {"slugs": cached, "mode": "ai"}

    try:
        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=_search_model(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(
                    {"query": query, "courses": docs}, ensure_ascii=False)},
            ],
            temperature=0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        slugs = [s for s in data.get("slugs", []) if s in valid]
        cache.set(ckey, slugs, _CACHE_TTL)
        return {"slugs": slugs, "mode": "ai"}
    except Exception as e:
        logger.warning("AI course search failed (%s); using substring fallback", e)
        return {"slugs": _substring_rank(query, docs), "mode": "fallback"}
