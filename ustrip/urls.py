from django.urls import path

from . import views

app_name = "ustrip"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.UstripLoginView.as_view(), name="login"),
    path("logout/", views.UstripLogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("itinerary/", views.itinerary_list, name="itinerary_list"),
    path("itinerary/<int:day_id>/", views.itinerary_day, name="itinerary_day"),
    path("itinerary/item/<int:item_id>/edit/", views.itinerary_item_edit, name="itinerary_item_edit"),
    path("packing/", views.packing, name="packing"),
    path("journal/", views.journal, name="journal"),
    # JSON API — every write these pages make (spec §0b).
    path("api/packing/groups/", views.api_packing_add_group, name="api_packing_add_group"),
    path("api/packing/items/", views.api_packing_add_item, name="api_packing_add_item"),
    path("api/packing/items/<int:item_id>/toggle/", views.api_packing_toggle_item, name="api_packing_toggle_item"),
    path("api/journal/posts/", views.api_journal_add_post, name="api_journal_add_post"),
    path("api/itinerary/<int:day_id>/items/", views.api_itinerary_add_item, name="api_itinerary_add_item"),
    path("api/itinerary/items/<int:item_id>/", views.api_itinerary_edit_item, name="api_itinerary_edit_item"),
]
