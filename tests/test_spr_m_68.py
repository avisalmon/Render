"""SPR-M.68 - no request system: everything by mail (Avi, 2026-10-15).

"I want to delete all this mechanism and do everything by mails." Naomi or Lital
write to Avi's Gmail with מטצים or matatzim in the subject, the build reads those
mails, does the work and writes back. The lamp stays so nobody has to learn that
it moved, and what it opens is one sentence and a button that starts that mail.
"""

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

pytestmark = pytest.mark.sprm68

PASSWORD = "sprm68-pass-4417"


def _pm():
    from matazim.models import Institution

    user = User.objects.create_user(username="pm@example.com", email="pm@example.com", password=PASSWORD)
    Institution.objects.create(name="רשת עתיד").managers.add(user)
    return user


def test_the_lamp_opens_a_dialog_with_one_button_that_starts_the_mail(client, db):
    client.force_login(_pm())
    html = client.get("/matazim/").content.decode()

    assert 'id="mzLamp"' in html and "<dialog" in html
    start = html.index("data-mz-mail")
    button = html[start:html.index("</button>", start)]
    assert 'data-subject="מטצים matatzim: בקשה"' in button       # both words, so it is found
    assert "הבקשה שלי" in button
    assert "avi.salmon@gmail.com" in html                          # where the mail goes
    assert "מעכשיו כל בקשה נשלחת במייל" in html


def test_the_lamp_is_a_button_and_not_a_link_into_any_system(client, db):
    client.force_login(_pm())
    html = client.get("/matazim/").content.decode()
    lamp = html[html.index('id="mzLamp"') - 40:html.index('id="mzLamp"') + 80]
    assert "<button" in lamp and "href=" not in lamp


def test_only_the_people_who_had_the_lamp_still_have_it(client, db):
    from matazim.models import MemberProfile, Student
    from tests.matazim_helpers import attach

    kid = User.objects.create_user(username="kid@example.com", email="kid@example.com", password=PASSWORD)
    MemberProfile.objects.update_or_create(user=kid, defaults={
        "entrance_test_passed_at": timezone.now(), "welcome_accepted_at": timezone.now(),
        "birth_year": timezone.now().year - 14, "guardian_consent_at": timezone.now()})
    attach(kid)
    client.force_login(kid)
    assert 'id="mzLamp"' not in client.get("/matazim/").content.decode()


@pytest.mark.parametrize("path", [
    "/matazim/requests/", "/matazim/requests/new/", "/matazim/requests/queue/",
    "/matazim/api/requests/", "/matazim/api/request-messages/", "/matazim/internal/requests/",
])
def test_the_request_system_is_gone(client, db, path):
    client.force_login(_pm())
    assert client.get(path).status_code == 404, path


def test_no_request_model_or_module_is_left():
    import importlib
    import pathlib

    from matazim import models

    assert not hasattr(models, "Request") and not hasattr(models, "RequestMessage")
    for module in ("request_views", "requests_api", "request_mail", "conversation_views", "assess"):
        with pytest.raises(ImportError):
            importlib.import_module(f"matazim.{module}")
    assert not (pathlib.Path("matazim/management/commands/matazim_requests.py")).exists()


def test_the_managers_menu_has_no_requests_entry(client, db):
    client.force_login(_pm())
    html = client.get("/matazim/").content.decode()
    nav = html[html.index('id="mzNav"'):html.index("</nav>", html.index('id="mzNav"'))]
    assert "הבקשות שלי" not in nav and ">בקשות" not in nav
