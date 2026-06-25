"""In-lesson runnable Python cells: save the student's code, reload it on return.
(Execution runs in the browser via Pyodide and is verified separately.)"""
import json
import re

import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.models import Course, StudentCode, Video

pytestmark = pytest.mark.django_db


def _setup():
    c = Course.objects.create(title="Py", slug="pytest-course", is_published=True)
    v = Video.objects.create(course=c, lesson_order=1, title="L1",
                             notes_markdown="```python-run\nprint(1)\n```")
    u = User.objects.create_user("coder", password="pass12345")
    return c, v, u


def test_save_requires_login():
    c, _v, _u = _setup()
    r = Client().post(f"/courses/{c.slug}/lesson/1/code/save/",
                      {"cell_key": "py0", "code": "x=1"})
    assert r.status_code in (302, 403)
    assert not StudentCode.objects.exists()


def test_save_and_reload_prefills():
    c, v, u = _setup()
    cl = Client(); cl.force_login(u)
    r = cl.post(f"/courses/{c.slug}/lesson/1/code/save/",
                {"cell_key": "py0", "code": "print('hi saved')"})
    assert r.json()["ok"] is True
    assert StudentCode.objects.get(user=u, video=v, cell_key="py0").code == "print('hi saved')"

    body = cl.get(f"/courses/{c.slug}/lesson/1/").content.decode()
    assert "js/py-runner.js" in body                # runner loads
    assert "language-python-run" in body            # block became a runnable cell
    payload = json.loads(re.search(r'id="py-saved-code"[^>]*>(.*?)</script>', body, re.S).group(1))
    assert payload["py0"] == "print('hi saved')"    # saved code prefills on return


def test_save_is_upsert():
    c, v, u = _setup()
    cl = Client(); cl.force_login(u)
    cl.post(f"/courses/{c.slug}/lesson/1/code/save/", {"cell_key": "py0", "code": "a"})
    cl.post(f"/courses/{c.slug}/lesson/1/code/save/", {"cell_key": "py0", "code": "b"})
    assert StudentCode.objects.filter(user=u, video=v, cell_key="py0").count() == 1
    assert StudentCode.objects.get(user=u, video=v, cell_key="py0").code == "b"
