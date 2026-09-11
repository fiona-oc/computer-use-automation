from django.urls import path
from . import views


urlpatterns = [
    path("", views.search_member, name="search_member"),

    path(
        "member/<str:member_id>/",
        views.member_detail,
        name="member_detail"
    ),

    path(
        "member/<str:member_id>/open-account/",
        views.open_account,
        name="open_account"
    ),
]