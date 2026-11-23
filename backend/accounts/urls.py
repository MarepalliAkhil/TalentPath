from django.urls import path

from . import views

urlpatterns = [
    path("profile", views.ProfileView.as_view(), name="profile"),
    path("demo/config", views.DemoConfigView.as_view(), name="demo-config"),
    path("users", views.UserListCreateView.as_view(), name="users"),
    path("hiring-managers", views.HiringManagerListView.as_view(), name="hiring-managers"),
    path("users/<uuid:pk>", views.UserDetailView.as_view(), name="user-detail"),
]
