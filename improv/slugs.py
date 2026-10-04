from django.utils.text import slugify

MAX = 60


def unique_slug(model, text, fallback="untitled"):
    """A slug from `text` that no row of `model` has yet: my-groove, my-groove-2, ..."""
    base = slugify(text)[: MAX - 6].strip("-") or fallback
    candidate, n = base, 1
    while model.objects.filter(slug=candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate
