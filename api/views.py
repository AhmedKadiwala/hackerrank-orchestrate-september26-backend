from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.models import FinancialProfile, PurchaseRequest, Recommendation
from buy_or_wait.engine import FinancialEngine
from buy_or_wait.loaders import Dataset, repo_root_from_code


ds = Dataset(repo_root_from_code())
engine = FinancialEngine(ds)


def row_from_request(obj: PurchaseRequest) -> dict:
    return {
        "request_id": obj.request_id,
        "user_id": obj.user_id,
        "request_date": obj.request_date.isoformat(),
        "request_type": obj.request_type,
        "requested_amount": str(obj.requested_amount).rstrip("0").rstrip("."),
        "desired_completion_date": obj.desired_completion_date.isoformat(),
        "allows_partial_payment": "true" if obj.allows_partial_payment else "false",
        "request_text": obj.request_text,
    }


def persist_recommendation(row: dict, out: dict) -> None:
    try:
        request_obj = PurchaseRequest.objects.get(request_id=row["request_id"])
        Recommendation.objects.update_or_create(
            request=request_obj,
            defaults={
                "amount_safe_to_pay": out["amount_safe_to_pay"],
                "affordability_status": out["affordability_status"],
                "recommended_payment_method": out["recommended_payment_method"],
                "payment_plan": out["payment_plan"],
                "earliest_date_for_full_payment": out["earliest_date_for_full_payment"] or None,
                "spending_changes_needed": out["spending_changes_needed"],
                "decision_explanation": out["decision_explanation"],
            },
        )
    except Exception:
        return


def response_for(row: dict) -> dict:
    if row["user_id"] not in ds.profile_by_user:
        return {"error": "Unknown user_id", "status": 404}
    rec = engine.recommend(row)
    out = engine.output_row(rec)
    out["forecast_summary"] = rec.forecast_summary
    out["evidence_summary"] = rec.evidence_summary
    persist_recommendation(row, out)
    return out


def health(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    db_counts = {}
    try:
        db_counts = {
            "financial_profiles": FinancialProfile.objects.count(),
            "purchase_requests": PurchaseRequest.objects.count(),
        }
    except Exception:
        db_counts = {"available": False}
    return JsonResponse({"ok": True, "requests": len(ds.requests), "db": db_counts})


def list_requests(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    try:
        rows = [row_from_request(obj) for obj in PurchaseRequest.objects.filter(is_sample=False).order_by("request_id")]
        if rows:
            return JsonResponse(rows, safe=False)
    except Exception:
        pass
    return JsonResponse(ds.requests, safe=False)


def get_request(request: HttpRequest, request_id: str):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    try:
        return JsonResponse(row_from_request(PurchaseRequest.objects.get(request_id=request_id)))
    except PurchaseRequest.DoesNotExist:
        pass
    except Exception:
        pass
    for row in ds.requests + ds.sample_requests:
        if row["request_id"] == request_id:
            return JsonResponse(row)
    return JsonResponse({"detail": "Unknown request_id"}, status=404)


@csrf_exempt
def analyze_request(request: HttpRequest, request_id: str):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        row = row_from_request(PurchaseRequest.objects.get(request_id=request_id))
        out = response_for(row)
        status = out.pop("status", 200)
        return JsonResponse(out, status=status)
    except PurchaseRequest.DoesNotExist:
        pass
    except Exception:
        pass
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
