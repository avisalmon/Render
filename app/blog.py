"""Rendering for the personal blog (Avi Salmon Blog).

The post body is markdown, rendered with the same pipeline the lessons use, so
everything that already works in a lesson works in a post too:

  - fenced ```python-run cells -> <code class="language-python-run"> which
    static/js/py-runner.js upgrades into a live, runnable Python emulator;
  - raw HTML (iframes / <script> widgets) passes straight through, so any other
    JS emulator or embed can be dropped in verbatim;
  - `[[img:key]]` shortcodes are resolved to a <figure> from the post's gallery
    before markdown runs, so images can be referenced by handle instead of URL.

Raw HTML is intentionally NOT sanitised: the blog has a single trusted author.
"""
import re

import markdown as _markdown

_IMG_SHORTCODE = re.compile(r"\[\[img:([a-zA-Z0-9_-]+)\]\]")
_MD_EXTENSIONS = ["fenced_code", "tables", "nl2br"]


def _resolve_image_shortcodes(text, post):
    """Replace `[[img:key]]` with a <figure> built from the post's gallery."""
    if "[[img:" not in text:
        return text
    images = {im.key: im for im in post.images.all() if im.key}

    def _sub(match):
        im = images.get(match.group(1))
        if im is None:
            return match.group(0)  # unknown key: leave the shortcode visible
        caption = f"<figcaption>{im.caption}</figcaption>" if im.caption else ""
        alt = im.alt or im.caption or ""
        return (
            f'<figure class="blog-figure">'
            f'<img src="{im.image.url}" alt="{alt}" loading="lazy">'
            f"{caption}</figure>"
        )

    return _IMG_SHORTCODE.sub(_sub, text)


def render_body(post):
    """Render a BlogPost body to safe-to-output HTML (mark |safe in the template)."""
    text = _resolve_image_shortcodes(post.body or "", post)
    try:
        return _markdown.markdown(text, extensions=_MD_EXTENSIONS)
    except Exception:
        return "<p>" + (post.body or "").replace("\n", "<br>") + "</p>"
