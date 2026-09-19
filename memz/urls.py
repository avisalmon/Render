from django.urls import include, path

from . import auth_views, views
from .api import router
from .api.game_views import (
    AdvanceView, AgainView, AttachAccountView, JoinView, LeaveView, RateView, ReleaseSessionView,
    RemovePlayerView, SessionCreateView, StartView, StateView, SubmitView, SwapCardView, SwapImageView,
    VoteView,
)
from .api.bank_views import BankImageView, BankUploadView
from .api.imgflip_views import ImgflipCaptionView, ImgflipTemplatesView
from .api.profile import ProfileView
from .api.report import ReportView
from .api.schema import SchemaView

app_name = "memz"

urlpatterns = [
    path("", views.home, name="home"),
    # The game (spec §4, §12.2).
    path("new/", views.new_session, name="new"),
    path("join/", views.join_session_page, name="join"),
    path("join/<str:code>/", views.join_session_page, name="join_with_code"),
    path("s/<str:code>/", views.game_page, name="game"),
    path("s/<str:code>/screen/", views.game_screen_page, name="game_screen"),
    path("s/<str:code>/qr.png", views.lobby_qr, name="lobby_qr"),
    # The solo creator (spec §7).
    path("create/", views.creator, name="create"),
    path("create/<str:slug>/", views.creator_result, name="creator_result"),
    # A meme's public page (spec §8.2).
    path("m/<str:slug>/", views.share, name="share"),
    # Profile (spec §10).
    path("me/", views.profile_page, name="profile"),
    path("images/", views.images_page, name="images"),

    # ACT-Z.17: the public bank's own uploader. Staff only, 404 for
    # everyone else, and linked from nowhere on purpose — Avi types it.
    path("bank/", views.bank_page, name="bank"),
    # Auth, in memz's own chrome (spec §3.3).
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", auth_views.signup, name="signup"),
    path("password/reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    # The REST API (building_an_app.md Rule 6; spec §12.3).
    path("api/profile/", ProfileView.as_view(), name="api_profile"),
    path("api/report/", ReportView.as_view(), name="api_report"),
    path("api/schema/", SchemaView.as_view(), name="api_schema"),
    path("api/sessions/", SessionCreateView.as_view(), name="api_session_create"),
    path("api/sessions/<str:code>/join/", JoinView.as_view(), name="api_session_join"),
    path("api/sessions/<str:code>/state/", StateView.as_view(), name="api_session_state"),
    path("api/sessions/<str:code>/start/", StartView.as_view(), name="api_session_start"),
    path("api/sessions/<str:code>/advance/", AdvanceView.as_view(), name="api_session_advance"),
    path("api/sessions/<str:code>/again/", AgainView.as_view(), name="api_session_again"),
    path("api/sessions/<str:code>/leave/", LeaveView.as_view(), name="api_session_leave"),
    path("api/sessions/<str:code>/attach/", AttachAccountView.as_view(), name="api_session_attach"),
    path("api/sessions/<str:code>/release/", ReleaseSessionView.as_view(), name="api_session_release"),
    path("api/sessions/<str:code>/players/<int:player_id>/remove/", RemovePlayerView.as_view(), name="api_session_remove_player"),
    path("api/sessions/<str:code>/rounds/<int:number>/submit/", SubmitView.as_view(), name="api_round_submit"),
    path("api/sessions/<str:code>/rounds/<int:number>/vote/", VoteView.as_view(), name="api_round_vote"),
    path("api/sessions/<str:code>/rounds/<int:number>/rate/", RateView.as_view(), name="api_round_rate"),
    path("api/sessions/<str:code>/rounds/<int:number>/swap-image/", SwapImageView.as_view(), name="api_round_swap_image"),
    path("api/sessions/<str:code>/cards/swap/", SwapCardView.as_view(), name="api_card_swap"),
    # Classic Imgflip templates in the solo creator (ACT-Z.5, spec §7.3).
    path("api/bank/images/", BankUploadView.as_view(), name="api_bank_upload"),
    path("api/bank/images/<int:pk>/", BankImageView.as_view(), name="api_bank_image"),
    path("api/imgflip/templates/", ImgflipTemplatesView.as_view(), name="api_imgflip_templates"),
    path("api/imgflip/memes/", ImgflipCaptionView.as_view(), name="api_imgflip_caption"),
    path("api/", include(router.urls)),
]
