"""SPR-I.9.5 improv: a short menu with More and an account menu, and a front door with one next step.

Avi, 2026-10-09, after seeing sketches of four designs: build the short bar (Today, Play, Lessons,
Scales, Chords, then More, then the account menu) and the front door that leads with Sign up.

Traces: spec ch. 7 "The menu" and "The front door", backlog SPR-I.9.5.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.test import Client

pytestmark = [pytest.mark.spri95, pytest.mark.django_db]

PASSWORD = "spri95-pass-4471-x"

EVERY_SCREEN = {
    "/improv/": "Today",
    "/improv/play/": "Play",
    "/improv/lessons/": "Lessons",
    "/improv/scales/": "Scales",
    "/improv/chords/": "Chords",
    "/improv/challenges/": "Challenges",
    "/improv/library/": "Library",
    "/improv/takes/": "Takes",
    "/improv/reference/": "Reference",
    "/improv/progress/": "Progress",
    "/improv/practice/": "Practice",
    "/improv/setup/": "Setup",
}


def _client(name="menu95", **flags):
    user = User.objects.create_user(username=name, email=f"{name}@example.com", password=PASSWORD)
    for key, value in flags.items():
        setattr(user, key, value)
    user.save()
    client = Client()
    client.force_login(user)
    return client


def _header(html):
    return re.search(r"<header class=\"im-top\">.*?</header>", html, re.S).group(0)


def _block(header, opener):
    start = header.index(opener)
    return header[start : header.index("</details>", start)]


def _links(fragment):
    return re.findall(r'<a [^>]*href="([^"]+)"[^>]*>\s*([^<]*?)\s*</a>', fragment)


# ------------------------------------------------------------------ signed in


def test_the_bar_holds_the_everyday_screens():
    html = _client().get("/improv/play/").content.decode("utf-8")
    nav = re.search(r'<nav class="im-nav" aria-label="Main">(.*?)</nav>', _header(html), re.S).group(1)
    direct = re.sub(r"<details.*?</details>", "", nav, flags=re.S)
    assert [text for _, text in _links(direct)] == ["Today", "Play", "Lessons", "Scales", "Chords", "Reading"]


def test_more_holds_the_less_used_screens():
    header = _header(_client().get("/improv/play/").content.decode("utf-8"))
    more = _block(header, '<details class="im-menu" id="im-more"')
    assert re.search(r"<summary[^>]*>\s*More", more)
    assert [text for _, text in _links(more)] == ["Challenges", "Library", "Takes", "Reference"]


def test_the_account_menu_holds_me_and_log_out():
    client = _client("dana95")
    header = _header(client.get("/improv/play/").content.decode("utf-8"))
    account = _block(header, '<details class="im-menu im-menu-account" id="im-account"')
    assert re.search(r"<summary[^>]*>[^<]*dana95@example\.com", account)
    links = dict((text, href) for href, text in _links(account))
    assert links["Progress"] == "/improv/progress/"
    assert links["Practice log"] == "/improv/practice/"
    assert links["Setup"] == "/improv/setup/"
    form = re.search(r'<form[^>]*action="/improv/logout/"[^>]*>.*?</form>', account, re.S).group(0)
    assert 'method="post"' in form and "csrfmiddlewaretoken" in form
    assert re.search(r"<button[^>]*type=\"submit\"[^>]*>\s*Log out\s*</button>", form)


def test_feedback_stays_in_plain_sight_not_in_a_menu():
    header = _header(_client().get("/improv/play/").content.decode("utf-8"))
    outside = re.sub(r"<details.*?</details>", "", header, flags=re.S)
    assert re.search(r'<a class="im-nav-link im-nav-feedback" href="/improv/feedback/\?from=/improv/play/"', outside)
    for menu in re.findall(r"<details.*?</details>", header, flags=re.S):
        assert "/improv/feedback/" not in menu


def test_the_bar_marks_the_screen_you_are_on():
    client = _client()
    play = _header(client.get("/improv/play/").content.decode("utf-8"))
    assert re.search(r'href="/improv/play/" aria-current="page"', play)
    assert play.count('aria-current="page"') == 1
    assert "data-here" not in play

    lesson = _header(client.get("/improv/lessons/").content.decode("utf-8"))
    assert re.search(r'href="/improv/lessons/" aria-current="page"', lesson)

    challenges = _header(client.get("/improv/challenges/").content.decode("utf-8"))
    assert 'id="im-more" data-here="yes"' in challenges, "More shows it holds the current screen"
    assert re.search(r'href="/improv/challenges/" aria-current="page"', challenges)
    assert 'id="im-account" data-here' not in challenges

    setup = _header(client.get("/improv/setup/").content.decode("utf-8"))
    assert 'id="im-account" data-here="yes"' in setup
    assert re.search(r'href="/improv/setup/" aria-current="page"', setup)


def test_no_screen_was_lost_from_the_menus():
    client = _client()
    header = _header(client.get("/improv/").content.decode("utf-8"))
    hrefs = {href for href, _ in _links(header)}
    for path in EVERY_SCREEN:
        assert path in hrefs, f"{path} is not reachable from the menus"


def test_every_screen_is_listed_once():
    header = _header(_client().get("/improv/").content.decode("utf-8"))
    hrefs = [href for href, text in _links(header) if href in EVERY_SCREEN and text != "improv"]
    assert sorted(hrefs) == sorted(EVERY_SCREEN), "a screen appears twice or not at all"


def test_staff_still_get_the_spike_link_and_others_do_not():
    staff = _header(_client("staff95", is_staff=True).get("/improv/").content.decode("utf-8"))
    plain = _header(_client("plain95").get("/improv/").content.decode("utf-8"))
    assert "/improv/spike/" in staff
    assert "/improv/spike/" not in plain


def test_the_piano_key_hint_stays_in_the_bar():
    header = _header(_client().get("/improv/").content.decode("utf-8"))
    legend = re.search(r'class="im-keys"[^>]*>(.*?)</span>', header, re.S).group(1)
    for name in ("C8", "B7", "A#7"):
        assert f"<b>{name}</b>" in legend


def test_a_menu_never_takes_a_control_key_from_the_screen():
    header = _header(_client().get("/improv/").content.decode("utf-8"))
    assert "data-key-action" not in header and "data-key-in" not in header


def test_the_menu_script_is_loaded_on_every_signed_in_screen():
    client = _client()
    for path in EVERY_SCREEN:
        html = client.get(path).content.decode("utf-8")
        assert "improv/menu" in html, path


# ------------------------------------------------------------------- visitor


def test_a_visitor_sees_log_in_and_a_filled_sign_up():
    header = _header(Client().get("/improv/").content.decode("utf-8"))
    assert "<details" not in header
    assert re.search(r'<a class="im-nav-link"[^>]*href="/improv/login/[^"]*"[^>]*>\s*Log in\s*</a>', header)
    assert re.search(r'<a class="im-btn"[^>]*href="/improv/signup/[^"]*"[^>]*>\s*Sign up free\s*</a>', header)


def test_the_login_and_sign_up_pages_offer_the_other_way_in_not_themselves():
    login = _header(Client().get("/improv/login/").content.decode("utf-8"))
    assert "Sign up free" in login and ">Log in<" not in login
    signup = _header(Client().get("/improv/signup/").content.decode("utf-8"))
    assert ">Log in<" in signup and "Sign up free" not in signup


# ---------------------------------------------------------------- front door


def test_the_front_door_leads_with_one_sentence_and_one_step():
    html = Client().get("/improv/").content.decode("utf-8")
    assert re.search(r"<h1[^>]*>\s*Play over a real band and hear what to fix\.\s*</h1>", html)
    main = html[html.index('<main class="im-main">') :]
    assert len(re.findall(r'class="im-btn"[^>]*>\s*Sign up free', main)) == 1, "one primary button in the page"
    assert "Continue with Google" in main
    assert re.search(r'href="/improv/login/[^"]*"[^>]*>\s*Log in\s*<', main)
    assert 'type="password"' not in html, "the password form is on its own page"


def test_the_front_door_shows_a_chart_that_plays_by_itself():
    html = Client().get("/improv/").content.decode("utf-8")
    demo = re.search(r'id="demo-chart"[^>]*>(.*?)</div>', html, re.S)
    assert demo, "no looping demo chart"
    assert re.findall(r"<b>([^<]+)</b>", demo.group(1)) == ["C7", "F7", "C7", "G7"]
    css = open("static/improv/improv.css", encoding="utf-8").read()
    assert "@keyframes im-demo-step" in css and "prefers-reduced-motion" in css


def test_the_front_door_keeps_where_the_visitor_was_going():
    html = Client().get("/improv/?next=/improv/play/").content.decode("utf-8")
    main = html[html.index('<main class="im-main">') :]
    assert main.count("next=%2Fimprov%2Fplay%2F") >= 2, "sign up and log in both carry the destination"


def test_the_login_page_holds_the_form_and_the_password_help():
    html = Client().get("/improv/login/").content.decode("utf-8")
    assert 'action="/improv/login/"' in html and 'type="password"' in html
    assert "Continue with Google" in html
    assert "/accounts/password/reset/" in html
    assert "/improv/signup/" in html


def test_a_wrong_password_comes_back_to_the_login_page_with_the_message():
    user = User.objects.create_user(username="forgot95", email="forgot95@example.com", password=PASSWORD)
    html = Client().post("/improv/login/", {"email": user.email, "password": "nope-nope"}).content.decode("utf-8")
    assert 'id="login-error"' in html and 'type="password"' in html


def test_the_front_door_is_still_improv_and_never_babook():
    html = Client().get("/improv/").content.decode("utf-8")
    assert "babook" not in html.lower()
    for link in re.findall(r'href="([^"]*)"', html):
        assert link.startswith(("/improv/", "/static/", "/accounts/google/login/", "#")), link
