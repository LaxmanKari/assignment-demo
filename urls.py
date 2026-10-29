from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    DocumentDetailView,
    DocumentListCreateView,
    LoginView,
    LogoutView,
    QueryHistoryView,
    QueryView,
    RegisterView,
    health,
)

urlpatterns = [
    path("health", health),
    path("register", RegisterView.as_view()),
    path("login", LoginView.as_view()),
    path("logout", LogoutView.as_view()),
    path("token/refresh", TokenRefreshView.as_view()),
    path("documents", DocumentListCreateView.as_view()),
    path("documents/<int:pk>", DocumentDetailView.as_view()),
    path("query", QueryView.as_view()),
    path("queries", QueryHistoryView.as_view()),
]
