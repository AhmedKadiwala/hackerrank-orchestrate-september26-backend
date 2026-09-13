from __future__ import annotations

import os

from django.http import HttpResponse


class CorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.origins = {
            origin.strip()
            for origin in os.getenv("BACKEND_CORS_ORIGINS", "").split(",")
            if origin.strip()
        }

    def __call__(self, request):
        origin = request.headers.get("Origin")
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if origin and origin in self.origins:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        return response
