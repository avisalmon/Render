"""The app's screens.

One screen so far: the front door. Sign-in is required because there is no
anonymous product (REQ-B.6.1), and a stranger is *sent to sign in* rather than
refused, because they are a future player.

The login URL points at babook's, which is the one thing this app shares: the
account. Rule 3 says no link back to the main site, and an auth redirect is not
a link in the menu, it is the shared front door the methodology explicitly
keeps shared ("Auth: reuse the User model, but a lighter front door is fine").
A blackjack-branded sign-in page of our own is SPR-B.1.2 work.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

LOGIN_URL = "/login/?next=/blackjack/"


@login_required(login_url=LOGIN_URL)
def home(request):
    """The front door. Three sections, two of them not built yet.

    It says what is coming rather than hiding it, because an app whose menu
    items do nothing feels broken, while an app that says "the drill is next"
    feels like it is being built.
    """
    return render(request, "blackjack/home.html", {})
