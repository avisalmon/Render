"""The museum: news from the future (spec §7.2).

Public, no login to browse. The only subtlety is that **visibility is a
query, not a job**: a timed release simply stops matching once its moment
passes, so nothing has to run on a schedule and nothing can fail quietly while
nobody is watching.
"""


from urllib.parse import quote

from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import PressRelease, PressReleaseLike

SESSION_VIEWED = "exo_viewed"


def publicly_visible(now=None):
    """Every release on the wall right now.

    `public` forever, or `timed` still inside its window — and never anything
    an admin has hidden. One queryset, used by the list, the API and the
    counts, so the three cannot disagree.
    """
    now = now or timezone.now()
    return (
        PressRelease.objects
        .filter(hidden_by_admin=False)
        .filter(
            Q(visibility=PressRelease.Visibility.PUBLIC)
            | Q(visibility=PressRelease.Visibility.TIMED, public_until__gt=now)
        )
        .exclude(headline="")
        .select_related("concept", "concept__owner", "newspaper_style")
        .annotate(likes=Count("like_rows", distinct=True))
    )


def cohort_visible(user, now=None):
    """The workshop wall: everything from this person's workshops that they
    may see (spec K6).

    Wider than the public wall in one direction and narrower in another. It
    includes pieces marked for the group, which are on no public wall at all,
    and it is limited to the workshops this person actually attended. A person
    in no workshop has no group wall, which is why the switch only appears for
    somebody who has one.

    Built on `publicly_visible`'s rules rather than beside them: hidden stays
    hidden, and an expired timed release is as gone here as it is there.
    """
    from .models import CohortMember

    now = now or timezone.now()
    if not getattr(user, "is_authenticated", False):
        return PressRelease.objects.none()

    mine = list(CohortMember.objects.filter(user=user)
                .values_list("cohort_id", flat=True))
    if not mine:
        return PressRelease.objects.none()

    return (
        PressRelease.objects
        .filter(hidden_by_admin=False, concept__cohort_id__in=mine)
        .filter(
            Q(visibility=PressRelease.Visibility.PUBLIC)
            | Q(visibility=PressRelease.Visibility.COHORT)
            | Q(visibility=PressRelease.Visibility.TIMED, public_until__gt=now)
        )
        .exclude(headline="")
        .select_related("concept", "concept__owner", "newspaper_style")
        .annotate(likes=Count("like_rows", distinct=True))
    )


def my_cohorts(user):
    from .models import CohortMember

    if not getattr(user, "is_authenticated", False):
        return []
    return list(
        CohortMember.objects.filter(user=user)
        .select_related("cohort").order_by("-joined_at")
    )


def museum(request):
    sort = request.GET.get("sort") or "new"
    joined = my_cohorts(request.user)

    # The group wall is only offered to somebody who has one, and "everyone"
    # stays the default: the museum's job is still to show what this place has
    # made.
    wall = request.GET.get("wall")
    if wall == "group" and joined:
        releases = cohort_visible(request.user)
    else:
        wall = "all"
        releases = publicly_visible()
    if sort == "liked":
        releases = releases.order_by("-likes", "-created_at")
    elif sort == "score":
        releases = releases.order_by("-exponential_score", "-created_at")
    else:
        releases = releases.order_by("-created_at")

    language = request.GET.get("lang")
    if language in ("he", "en"):
        releases = releases.filter(language=language)

    return render(request, "exo/museum.html", {
        "releases": releases[:60],
        "sort": sort,
        "lang_filter": language,
        "wall": wall,
        "cohorts": [j.cohort for j in joined],
        "nav": "museum",
    })


def museum_item(request, pk):
    """One release. Visibility is checked here, not assumed by the list."""
    release = get_object_or_404(
        PressRelease.objects.select_related(
            "concept", "concept__owner", "newspaper_style",
        ),
        pk=pk,
    )
    if not release.visible_to(request.user):
        # A private or expired release is genuinely not there for this person.
        raise Http404

    # Count a view once per session, so a refresh is not a view.
    viewed = request.session.get(SESSION_VIEWED) or []
    if release.pk not in viewed:
        PressRelease.objects.filter(pk=release.pk).update(
            view_count=release.view_count + 1
        )
        release.view_count += 1
        request.session[SESSION_VIEWED] = viewed + [release.pk]

    liked = False
    if request.user.is_authenticated:
        liked = release.like_rows.filter(user=request.user).exists()

    return render(request, "exo/museum_item.html", {
        "release": release,
        "liked": liked,
        "likes": release.like_rows.count(),
        "expired": (release.visibility == PressRelease.Visibility.TIMED
                    and not release.is_public_now()),
        "is_owner": release.concept.owner_id == getattr(request.user, "id", None),
        "nav": "museum",
    })


@require_POST
def like(request, pk):
    """Toggle a like. One per person per release, enforced by the database."""
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "sign in"}, status=403)
    release = get_object_or_404(PressRelease, pk=pk)
    if not release.visible_to(request.user):
        raise Http404
    existing = release.like_rows.filter(user=request.user).first()
    if existing:
        existing.delete()
        liked = False
    else:
        PressReleaseLike.objects.get_or_create(release=release, user=request.user)
        liked = True
    return JsonResponse({"liked": liked, "likes": release.like_rows.count()})


@require_GET
def download(request, pk, fmt):
    """The feature as a file (spec §5.4). Downloads only; sharing is not here.

    Mounted on the release rather than the concept so one view serves both
    places the article appears: the owner's output screen and the museum. The
    check is `visible_to`, which the owner always passes and which keeps a
    private piece private even if somebody guesses the number.
    """
    from . import documents

    builder = documents.BUILDERS.get(fmt)
    if builder is None:
        raise Http404

    release = get_object_or_404(
        PressRelease.objects.select_related("concept", "concept__owner",
                                            "newspaper_style"),
        pk=pk,
    )
    if not release.visible_to(request.user):
        raise Http404

    build, content_type = builder
    try:
        payload = build(release)
    except ImportError:
        # The PDF library is the one thing here that is not standard. If a
        # deployment is missing it, say so plainly rather than throwing a 500
        # at somebody who only wanted a download.
        return JsonResponse({"detail": "pdf_unavailable"}, status=503)

    filename = documents.filename_for(release, fmt)
    response = HttpResponse(payload, content_type=content_type)
    # A Hebrew filename cannot travel in a plain `filename=`; RFC 5987's
    # `filename*` is what carries it, with an ASCII fallback for anything old
    # enough not to understand that.
    ascii_name = quote(filename)
    response["Content-Disposition"] = (
        f"attachment; filename=\"{fmt}\"; filename*=UTF-8''{ascii_name}"
    )
    response["Content-Length"] = str(len(payload))
    return response
