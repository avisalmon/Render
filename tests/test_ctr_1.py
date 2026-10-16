"""SPR-N.1: counter counts. The public hit/stats API, the owner API's refusals,
the dashboard gate and the snippet (docs/counter/spec.md)."""

import html
import json
import re

import pytest
from django.contrib.auth import get_user_model

from counter.models import Event, Page, Promo, PromoPlacement, Site

pytestmark = [pytest.mark.ctr1, pytest.mark.django_db]
User = get_user_model()


@pytest.fixture
def avi(db):
    return User.objects.create_user("avi", "avi@example.com", "pw", is_superuser=True, is_staff=True)


@pytest.fixture
def other(db):
    return User.objects.create_user("other", "o@example.com", "pw", is_superuser=True)


@pytest.fixture
def site(avi):
    return Site.objects.create(owner=avi, name="notes")


def hit(client, key, path="/a/", visitor="v1", **extra):
    body = {"key": key, "path": path, "visitor": visitor, **extra}
    # Exactly how the snippet sends it: text/plain, no preflight.
    return client.post("/counter/api/hit/", data=json.dumps(body), content_type="text/plain")


# ---- public: counting ------------------------------------------------------

def test_a_hit_is_counted_and_returned(client, site):
    r = hit(client, site.key)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "path": "/a/", "views": 1, "uniques": 1}
    assert Event.objects.filter(site=site, kind="view").count() == 1


def test_views_count_every_load_uniques_count_each_visitor_once(client, site):
    hit(client, site.key, visitor="v1")
    hit(client, site.key, visitor="v1")
    r = hit(client, site.key, visitor="v2")
    assert (r.json()["views"], r.json()["uniques"]) == (3, 2)


def test_a_hit_with_no_visitor_counts_a_view_but_not_a_unique(client, site):
    r = hit(client, site.key, visitor="")
    assert (r.json()["views"], r.json()["uniques"]) == (1, 0)


def test_paths_are_tidied_so_one_page_is_one_page(client, site):
    hit(client, site.key, path="/a/index.html?utm=x#top")
    hit(client, site.key, path="/a/")
    assert list(Page.objects.filter(site=site).values_list("path", flat=True)) == ["/a/"]


def test_counts_are_per_page_and_per_site(client, site):
    hit(client, site.key, path="/a/")
    hit(client, site.key, path="/b/")
    hit(client, site.key, path="/b/")
    assert client.get(f"/counter/api/stats/{site.key}/?path=/b/").json()["views"] == 2
    assert client.get(f"/counter/api/stats/{site.key}/").json()["views"] == 3


def test_clicks_are_events_but_not_views(client, site):
    hit(client, site.key, kind="click", name="download")
    assert Event.objects.get(site=site).kind == "click"
    assert client.get(f"/counter/api/stats/{site.key}/").json()["views"] == 0


def test_a_junk_kind_becomes_a_view_not_an_error(client, site):
    assert hit(client, site.key, kind="drop table").status_code == 200
    assert Event.objects.get(site=site).kind == "view"


def test_one_sites_counts_never_leak_into_another(client, site, avi):
    b = Site.objects.create(owner=avi, name="b")
    hit(client, site.key)
    assert client.get(f"/counter/api/stats/{b.key}/").json()["views"] == 0


def test_an_unknown_or_inactive_key_is_404_and_records_nothing(client, site):
    assert hit(client, "nope").status_code == 404
    site.is_active = False
    site.save()
    assert hit(client, site.key).status_code == 404
    assert client.get(f"/counter/api/stats/{site.key}/").status_code == 404
    assert Event.objects.count() == 0


def test_garbage_bodies_do_not_500(client, site):
    for body in ("", "not json", "[1,2]", "null"):
        r = client.post("/counter/api/hit/", data=body, content_type="text/plain")
        assert r.status_code == 404


def test_the_raw_ip_is_never_stored(client, site):
    client.post("/counter/api/hit/", data=json.dumps({"key": site.key, "path": "/", "visitor": "v"}),
                content_type="text/plain", REMOTE_ADDR="203.0.113.9")
    ev = Event.objects.get()
    assert "203.0.113.9" not in (ev.ip_hash + ev.referrer + ev.user_agent)
    assert re.fullmatch(r"[0-9a-f]{64}", ev.ip_hash)


@pytest.mark.parametrize("method,path", [("post", "/counter/api/hit/"), ("get", "/counter/api/stats/x/"),
                                         ("get", "/counter/api/promo/x/"), ("get", "/counter/c.js")])
def test_public_endpoints_allow_any_origin(client, method, path):
    r = getattr(client, method)(path)
    assert r["Access-Control-Allow-Origin"] == "*"


def test_options_preflight_is_answered(client):
    r = client.options("/counter/api/hit/")
    assert r.status_code == 200 and r["Access-Control-Allow-Origin"] == "*"


# ---- public: promos --------------------------------------------------------

def test_promo_matches_by_path_prefix_and_ignores_inactive(client, site, avi):
    p = Promo.objects.create(owner=avi, title="Try improv", url="https://x/improv/")
    off = Promo.objects.create(owner=avi, title="Off", url="https://x/off/", is_active=False)
    PromoPlacement.objects.create(promo=p, site=site, path_prefix="/blog/")
    PromoPlacement.objects.create(promo=off, site=site, path_prefix="")
    got = client.get(f"/counter/api/promo/{site.key}/?path=/blog/post/").json()
    assert got["promo"]["title"] == "Try improv"
    assert client.get(f"/counter/api/promo/{site.key}/?path=/other/").json()["promo"] is None


def test_a_promo_click_is_tied_to_the_promo(client, site, avi):
    p = Promo.objects.create(owner=avi, title="P", url="https://x/")
    hit(client, site.key, kind="promo_click", promo=p.pk)
    assert Event.objects.get().promo_id == p.pk


def test_another_owners_promo_id_is_ignored(client, site, other):
    p = Promo.objects.create(owner=other, title="P", url="https://x/")
    hit(client, site.key, kind="promo_click", promo=p.pk)
    assert Event.objects.get().promo_id is None


# ---- owner API: the refusals -----------------------------------------------

OWNER_URLS = ["sites", "pages", "events", "promos", "placements"]


@pytest.mark.parametrize("name", OWNER_URLS)
def test_anonymous_gets_nothing_from_the_owner_api(client, name):
    assert client.get(f"/counter/api/{name}/").status_code in (401, 403)
    assert client.post(f"/counter/api/{name}/", data={}, content_type="application/json").status_code in (401, 403)


@pytest.mark.parametrize("name", OWNER_URLS)
def test_a_signed_in_non_superuser_gets_nothing(client, db, name):
    User.objects.create_user("pleb", "p@example.com", "pw")
    client.login(username="pleb", password="pw")
    assert client.get(f"/counter/api/{name}/").status_code == 403


def test_full_crud_on_a_site(client, avi):
    client.force_login(avi)
    r = client.post("/counter/api/sites/", {"name": "n", "base_url": "https://x/"}, content_type="application/json")
    assert r.status_code == 201
    sid, key = r.json()["id"], r.json()["key"]
    assert Site.objects.get(pk=sid).owner == avi
    assert client.patch(f"/counter/api/sites/{sid}/", {"name": "m"}, content_type="application/json").json()["name"] == "m"
    assert client.get(f"/counter/api/sites/{sid}/").json()["key"] == key
    assert client.delete(f"/counter/api/sites/{sid}/").status_code == 204
    assert not Site.objects.filter(pk=sid).exists()


def test_the_key_cannot_be_chosen_or_changed_through_the_api(client, avi, site):
    client.force_login(avi)
    r = client.post("/counter/api/sites/", {"name": "n", "key": "mine"}, content_type="application/json")
    assert r.json()["key"] != "mine"
    client.patch(f"/counter/api/sites/{site.pk}/", {"key": "mine"}, content_type="application/json")
    site.refresh_from_db()
    assert site.key != "mine"


def test_the_owner_cannot_be_chosen_through_the_api(client, avi, other):
    client.force_login(avi)
    r = client.post("/counter/api/sites/", {"name": "n", "owner": other.pk}, content_type="application/json")
    assert Site.objects.get(pk=r.json()["id"]).owner == avi


def test_another_owners_site_is_invisible_everywhere(client, avi, other):
    theirs = Site.objects.create(owner=other, name="theirs")
    page = Page.objects.create(site=theirs, path="/")
    client.force_login(avi)
    assert client.get("/counter/api/sites/").json() == [] or client.get("/counter/api/sites/").json()["results"] == []
    for url in (f"/counter/api/sites/{theirs.pk}/", f"/counter/api/pages/{page.pk}/"):
        assert client.get(url).status_code == 404
        assert client.delete(url).status_code == 404
    assert client.get(f"/counter/sites/{theirs.pk}/").status_code == 404


def test_cannot_attach_a_page_event_or_placement_to_someone_elses_site(client, avi, other):
    theirs = Site.objects.create(owner=other, name="theirs")
    mine_promo = Promo.objects.create(owner=avi, title="P", url="u")
    client.force_login(avi)
    for url, body in (("pages", {"site": theirs.pk, "path": "/x/"}),
                      ("events", {"site": theirs.pk, "kind": "view"}),
                      ("placements", {"site": theirs.pk, "promo": mine_promo.pk})):
        r = client.post(f"/counter/api/{url}/", body, content_type="application/json")
        assert r.status_code == 400, url
    assert Page.objects.filter(site=theirs).count() == 0


def test_cannot_place_someone_elses_promo(client, avi, other, site):
    theirs = Promo.objects.create(owner=other, title="P", url="u")
    client.force_login(avi)
    r = client.post("/counter/api/placements/", {"site": site.pk, "promo": theirs.pk}, content_type="application/json")
    assert r.status_code == 400


def test_stats_action_returns_the_summary(client, avi, site):
    hit(client, site.key)
    client.force_login(avi)
    data = client.get(f"/counter/api/sites/{site.pk}/stats/?days=7").json()
    assert data["all"]["views"] == 1 and data["days"] == 7
    assert client.get(f"/counter/api/sites/{site.pk}/stats/?days=abc").json()["days"] == 30


# ---- the pages -------------------------------------------------------------

def test_dashboard_sends_anonymous_to_counters_own_login(client):
    r = client.get("/counter/")
    assert r.status_code == 302 and r["Location"].startswith("/counter/login/")


def test_dashboard_refuses_a_non_superuser_in_counters_own_chrome(client, db):
    User.objects.create_user("pleb", "p@example.com", "pw")
    client.login(username="pleb", password="pw")
    r = client.get("/counter/")
    assert r.status_code == 403 and "Not for you" in r.content.decode()


def test_dashboard_and_site_page_show_the_numbers(client, avi, site):
    hit(client, site.key, visitor="a")
    hit(client, site.key, visitor="b")
    client.force_login(avi)
    row = re.search(r'<li class="counter-card counter-site.*?</li>', client.get("/counter/").content.decode(), re.S).group(0)
    assert "<b>2</b> views" in row and "<b>2</b> unique" in row
    page = client.get(f"/counter/sites/{site.pk}/").content.decode()
    snippet = html.unescape(re.search(r'<pre class="counter-code" data-snippet>(.*?)</pre>', page, re.S).group(1))
    assert f'data-site="{site.key}"' in snippet and "https://babook.co.il/counter/c.js" in snippet


def test_the_snippet_is_served_as_javascript(client):
    r = client.get("/counter/c.js")
    assert r.status_code == 200 and r["Content-Type"].startswith("application/javascript")
    assert "/api/hit/" in r.content.decode()


def test_counter_pages_carry_no_babook_chrome_and_no_link_out(client, avi, site):
    client.force_login(avi)
    for url in ("/counter/", f"/counter/sites/{site.pk}/", "/counter/nope/"):
        page = client.get(url).content.decode()
        # The snippet the owner copies names the live host on purpose; that is
        # the one place the word may appear.
        chrome = re.sub(r"<pre.*?</pre>", "", page, flags=re.S)
        assert "babook" not in chrome.lower()
        hrefs = re.findall(r'href="([^"]+)"', page)
        assert all(h.startswith("/counter/") or h.startswith("/static/") or h.startswith("/accounts/google/")
                   for h in hrefs), hrefs


def test_a_404_inside_counter_uses_counters_own_page(client):
    r = client.get("/counter/nope/")
    assert r.status_code == 404 and "Nothing here" in r.content.decode()
