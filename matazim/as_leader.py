"""REQ-M.207 - a program manager looks at the site as one of her leaders sees it.

Naomi, 2026-10-29: "אני רוצה בבקשה שבאתר יהיה אפשרות של 'לראות את האתר כמוביל'
כמו שיש את האפשרות 'לראות את האתר כתלמיד'". She and Lital manage the programme,
the leaders are under them and the students under the leaders, and she wants to
see the site from every one of those places.

A leader's screens are about that leader's own students, so "as a leader" has to
mean as one leader in particular. She picks one of her own leaders and sees their
area, their students and their classes exactly as they do. Nothing new is shown to
her: every student there is already one she sees (`visible_students`), and the
leaders she may pick are `visible_leaders`, so another programme's leader is not
reachable.

Looking changes nothing. The session holds which leader is being looked at, no row
is made, and the leader's pages refuse every write while looking: a manager
pressing a leader's button would act in the leader's name, which is not looking.
"""

from django.core.exceptions import PermissionDenied

from .access import is_program_manager, leader_of, visible_leaders

KEY = "mz_as_leader"


def leaders_to_view(user):
    """The leaders this person may look through: her own, approved and active."""
    if not is_program_manager(user):
        return visible_leaders(user).none()
    return (
        visible_leaders(user)
        .filter(is_active=True, approved_at__isnull=False)
        .select_related("user", "user__profile")
        .order_by("user__profile__display_name", "user__email")
    )


def viewed_leader(request):
    """The leader being looked at, or None. Read again on every request, so a
    leader taken out of use, or a manager who lost the role, simply stops."""
    chosen = request.session.get(KEY)
    if not chosen:
        return None
    return leaders_to_view(request.user).filter(pk=chosen).first()


def acting_leader(request):
    """The leader whose screens these are: the one being looked at, else your own."""
    return viewed_leader(request) or leader_of(request.user)


def refuse_writes(request):
    """While looking, a leader's page is for reading."""
    if request.method == "POST" and viewed_leader(request) is not None:
        raise PermissionDenied
