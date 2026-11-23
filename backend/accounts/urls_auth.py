from django.urls import path

from . import views

urlpatterns = [
    path("csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("register", views.RegisterView.as_view(), name="auth-register"),
    path("login", views.LoginView.as_view(), name="auth-login"),
    path("logout", views.LogoutView.as_view(), name="auth-logout"),
    path("refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("me", views.MeView.as_view(), name="auth-me"),
    path("demo-login", views.DemoLoginView.as_view(), name="auth-demo-login"),
    path("password-reset", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "password-reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
]
