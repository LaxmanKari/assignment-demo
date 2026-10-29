from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, RegisterView, health

urlpatterns = [
    path("health", health),
    path("register", RegisterView.as_view()),
    path("login", LoginView.as_view()),
    path("logout", LogoutView.as_view()),
    path("token/refresh", TokenRefreshView.as_view()),
]