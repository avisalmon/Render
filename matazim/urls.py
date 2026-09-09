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
]
