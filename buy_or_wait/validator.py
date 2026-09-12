from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from .dates import parse_date
from .loaders import OUTPUT_COLUMNS
from .money import dec


STATUS = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
METHOD = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
PLAN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}:[0-9]+(?:\.[0-9]+)?(?:\|\d{4}-\d{2}-\d{2}:[0-9]+(?:\.[0-9]+)?)*$")
CHANGE_RE = re.compile(r"^(none|(?:stop:event_\d+|reduce_to:event_\d+:[0-9]+(?:\.[0-9]+)?)(?:\|(?:stop:event_\d+|reduce_to:event_\d+:[0-9]+(?:\.[0-9]+)?))*)$")


def validate_output_file(path: Path, request_rows: list[dict]) -> list[str]:
    errors = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if reader.fieldnames != OUTPUT_COLUMNS:
        errors.append(f"columns mismatch: {reader.fieldnames}")
    expected = [r["request_id"] for r in request_rows]
    got = [r.get("request_id", "") for r in rows]
    if len(rows) != len(expected):
        errors.append(f"row count {len(rows)} != {len(expected)}")
    if set(got) != set(expected):
        errors.append("request IDs do not match requests.csv")
    if len(got) != len(set(got)):
        errors.append("duplicate request IDs")
    req_by_id = {r["request_id"]: r for r in request_rows}
    for i, row in enumerate(rows, start=2):
        rid = row.get("request_id", "")
        if rid not in req_by_id:
            continue
        amount = dec(row.get("amount_safe_to_pay"))
        requested = dec(req_by_id[rid]["requested_amount"])
        if amount < 0 or amount > requested:
            errors.append(f"line {i}: amount_safe_to_pay out of bounds")
        if row.get("affordability_status") not in STATUS:
            errors.append(f"line {i}: bad status")
        if row.get("recommended_payment_method") not in METHOD:
            errors.append(f"line {i}: bad method")
        plan = row.get("payment_plan", "")
        if plan != "none" and not PLAN_RE.match(plan):
            errors.append(f"line {i}: malformed payment_plan")
        if row.get("spending_changes_needed", "") and not CHANGE_RE.match(row["spending_changes_needed"]):
            errors.append(f"line {i}: malformed spending_changes_needed")
        if row.get("earliest_date_for_full_payment"):
            try:
                parse_date(row["earliest_date_for_full_payment"])
            except Exception:
                errors.append(f"line {i}: malformed earliest date")
        for value in row.values():
            if str(value).lower() in {"nan", "infinity", "-infinity"}:
                errors.append(f"line {i}: illegal numeric token")
    return errors

