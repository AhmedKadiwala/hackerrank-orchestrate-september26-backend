from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from buy_or_wait.engine import FinancialEngine
from buy_or_wait.loaders import Dataset, repo_root_from_code


ds = Dataset(repo_root_from_code())
engine = FinancialEngine(ds)


def response_for(row: dict) -> dict:
    if row["user_id"] not in ds.profile_by_user:
        return {"error": "Unknown user_id", "status": 404}
    rec = engine.recommend(row)
    out = engine.output_row(rec)
    out["forecast_summary"] = rec.forecast_summary
    out["evidence_summary"] = rec.evidence_summary
    return out


def health(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return JsonResponse({"ok": True, "requests": len(ds.requests)})


def list_requests(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    return JsonResponse(ds.requests, safe=False)


def get_request(request: HttpRequest, request_id: str):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    for row in ds.requests + ds.sample_requests:
        if row["request_id"] == request_id:
            return JsonResponse(row)
    return JsonResponse({"detail": "Unknown request_id"}, status=404)


@csrf_exempt
def analyze_request(request: HttpRequest, request_id: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    for row in ds.requests + ds.sample_requests:
        if row["request_id"] == request_id:
            out = response_for(row)
            status = out.pop("status", 200)
            return JsonResponse(out, status=status)
    return JsonResponse({"detail": "Unknown request_id"}, status=404)


@csrf_exempt
def analyze_custom(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        row = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    row["request_id"] = row.get("request_id") or "custom_request"
    required = ["user_id", "request_date", "requested_amount", "desired_completion_date"]
    missing = [key for key in required if not row.get(key)]
    if missing:
        return JsonResponse({"detail": f"Missing required fields: {', '.join(missing)}"}, status=400)
    row.setdefault("request_type", "other")
    row.setdefault("allows_partial_payment", "false")
    row.setdefault("request_text", "")
    out = response_for(row)
    status = out.pop("status", 200)
    return JsonResponse(out, status=status)
