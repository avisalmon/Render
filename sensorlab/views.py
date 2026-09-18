"""SensorLab's views.

The landing page is open — it is the front door, and it says what this is.
Everything past it needs an account (spec §9.1 A.2: the app is closed), and
the gate is SensorLab's own login page rather than the site's, which is why
`login_url` is passed explicitly instead of leaning on the project-wide
`LOGIN_URL` that belongs to babook.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy

from .profiles import profile_for

sensorlab_login_required = login_required(login_url=reverse_lazy("sensorlab:login"))


def home(request):
    return render(request, "sensorlab/home.html")


@sensorlab_login_required
def lab(request):
    """The first page behind the gate. A shell until Epic D's runner."""
    profile = profile_for(request.user)
    return render(request, "sensorlab/lab.html", {"profile": profile})
