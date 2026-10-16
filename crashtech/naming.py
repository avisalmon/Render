"""How a person is named to anybody who is not running the event.

**Never by their email address.** The first version of the museum, the
certificate and the published standings fell back to the email whenever a
person had no name, and CrashTech's own sign-up did not ask for one, so
every participant who signed up here would have had their address printed
on a page that is public and permanent by design (Rule 9.1, 9.2). A
review caught it before any real event was published.

Admins still see email addresses on their own screens, because matching a
person at the kit desk or deciding an application needs one. Everybody
else gets a name, or a description of the person that names nobody.
"""

FALLBACK = "A participant"


def display_name(user, fallback=FALLBACK):
    if user is None:
        return fallback
    full = (user.get_full_name() or "").strip()
    return full or fallback


def has_name(user):
    return bool(user is not None and (user.get_full_name() or "").strip())


def set_name(user, raw):
    """Split one typed name into Django's two fields.

    One field on the form, because people are not consistent about what a
    first and last name are, and the international audience (Rule 12.3)
    makes that worse. The split is only for storage.
    """
    raw = " ".join((raw or "").split())[:300]
    first, _, last = raw.partition(" ")
    user.first_name = first[:150]
    user.last_name = last[:150]
    user.save(update_fields=["first_name", "last_name"])
    return user
