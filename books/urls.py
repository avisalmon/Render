from django.urls import include, path

from . import auth_views, catalog_views, internal, scan_views, views
from .api import router

app_name = "books"

urlpatterns = [
    path("", views.home, name="home"),
    path("welcome/", views.onboarding, name="onboarding"),
    path("settings/", views.settings_page, name="settings"),
    path("me/data/", views.my_data, name="my_data"),
    path("me/data/export.json", views.my_data_export, name="my_data_export"),
    path("lang/<str:code>/", views.set_language, name="set_language"),
    path("theme/<str:theme>/", views.set_theme, name="set_theme"),
    # Photographing a shelf and confirming its books (BK3).
    path("scan/", scan_views.new_scan, name="scan_new"),
    path("scan/<int:pk>/", scan_views.scan_page, name="scan"),
    path("scan/<int:pk>/status/", scan_views.scan_status, name="scan_status"),
    path("scan/<int:pk>/photo.jpg", scan_views.scan_photo, name="scan_photo"),
    path("scan/<int:pk>/item/<int:item_pk>/", scan_views.item_action, name="scan_item"),
    path("scan/<int:pk>/accept-confident/", scan_views.accept_confident, name="scan_accept_confident"),
    path("scan/<int:pk>/add/", scan_views.add_missed, name="scan_add"),
    path("shelf/reorder/", scan_views.reorder_shelf, name="shelf_reorder"),
    # The shared catalogue (BK2).
    path("catalog/", catalog_views.search, name="catalog"),
    path("catalog/new/", catalog_views.new_entry, name="catalog_new"),
    path("catalog/tag/<slug:key>/", catalog_views.by_tag, name="catalog_tag"),
    path("catalog/<int:pk>/", catalog_views.entry, name="catalog_entry"),
    path("catalog/<int:pk>/edit/", catalog_views.new_entry, name="catalog_edit"),
    path("curate/", catalog_views.curate, name="curate"),
    path("curate/act/", catalog_views.curate_action, name="curate_action"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    # Staff only, linked from nowhere: every component once (spec BK1 §1.1).
    path("design/", views.design_entry, name="design"),
    # Auth, in Books' own look (spec BK1 §1.5).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # A scheduler's door: re-run dropped background jobs (books/internal.py).
    path("internal/run-jobs/", internal.run_jobs, name="run_jobs"),
    # The API (Rule 6).
    path("api/", include(router.urls)),
]
