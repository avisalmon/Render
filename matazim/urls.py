"""מט״צים URL space.

Namespaced, so every name in this product is `matazim:*` and can never collide
with a babook name. RULE-1 is enforced against this: a template under
templates/matazim/ may only reverse names in this namespace.
"""

from django.urls import path

from . import views

app_name = "matazim"

urlpatterns = [
    path("", views.home, name="home"),
    # מבחן הכניסה is public: the link gets pasted around, and signing up
    # happens around the test rather than before it (REQ-M.5d).
    path("test/", views.entrance_test, name="entrance_test"),
    # The threshold. Our screens, babook's accounts (REQ-M.6, REQ-M.7).
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("register/", views.register, name="register"),
    # First contact (REQ-M.39 to M.41).
    path("welcome/accept/", views.welcome_accept, name="welcome_accept"),
    path("profile/", views.profile, name="profile"),
    path("profile/replay-welcome/", views.profile_reset_welcome, name="profile_reset_welcome"),
]
