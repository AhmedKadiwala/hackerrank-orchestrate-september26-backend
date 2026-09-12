from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.engine import FinancialEngine
from buy_or_wait.loaders import Dataset, repo_root_from_code


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Buy or Wait API", version="1.0.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv("BACKEND_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

ds = Dataset(repo_root_from_code())
engine = FinancialEngine(ds)


class CustomAnalyzeRequest(BaseModel):
    request_id: str | None = None
    user_id: str
    request_date: str
    request_type: str = "other"
    requested_amount: str
    desired_completion_date: str
    allows_partial_payment: str = "false"
    request_text: str = ""


def response_for(row: dict):
    if row["user_id"] not in ds.profile_by_user:
        raise HTTPException(status_code=404, detail="Unknown user_id")
    rec = engine.recommend(row)
    out = engine.output_row(rec)
    out["forecast_summary"] = rec.forecast_summary
    out["evidence_summary"] = rec.evidence_summary
    return out


@app.get("/api/health")
def health():
    return {"ok": True, "requests": len(ds.requests)}


@app.get("/api/requests")
def list_requests():
    return ds.requests


@app.get("/api/requests/{request_id}")
def get_request(request_id: str):
    for row in ds.requests + ds.sample_requests:
        if row["request_id"] == request_id:
            return row
    raise HTTPException(status_code=404, detail="Unknown request_id")


@app.post("/api/analyze/{request_id}")
def analyze_request(request_id: str):
    for row in ds.requests + ds.sample_requests:
        if row["request_id"] == request_id:
            return response_for(row)
    raise HTTPException(status_code=404, detail="Unknown request_id")


@app.post("/api/analyze")
def analyze_custom(payload: CustomAnalyzeRequest):
    row = payload.model_dump()
    row["request_id"] = row.get("request_id") or "custom_request"
    return response_for(row)
