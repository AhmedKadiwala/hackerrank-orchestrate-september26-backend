from __future__ import annotations

from django.urls import path

from api import views


urlpatterns = [
    path("api/health", views.health),
    path("api/requests", views.list_requests),
    path("api/requests/<str:request_id>", views.get_request),
    path("api/analyze", views.analyze_custom),
    path("api/analyze/<str:request_id>", views.analyze_request),
]
