from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.engine import FinancialEngine
from buy_or_wait.loaders import Dataset, repo_root_from_code
from buy_or_wait.money import dec


def main() -> int:
    root = repo_root_from_code()
    ds = Dataset(root)
    engine = FinancialEngine(ds)
    recs = engine.run_requests(ds.sample_requests)
    rows = [engine.output_row(r) for r in recs]
    actual_by_id = {r["request_id"]: r for r in ds.sample_requests}
    amount_errors = []
    status_ok = method_ok = plan_ok = date_ok = changes_ok = 0
    details = []
    for row in rows:
        actual = actual_by_id[row["request_id"]]
        err = abs(dec(row["amount_safe_to_pay"]) - dec(actual["amount_safe_to_pay"]))
        amount_errors.append(err)
        status_ok += row["affordability_status"] == actual["affordability_status"]
        method_ok += row["recommended_payment_method"] == actual["recommended_payment_method"]
        plan_ok += row["payment_plan"] == actual["payment_plan"]
        date_ok += row["earliest_date_for_full_payment"] == actual["earliest_date_for_full_payment"]
        changes_ok += row["spending_changes_needed"] == actual["spending_changes_needed"]
        if (
            err > dec("1")
            or row["affordability_status"] != actual["affordability_status"]
            or row["recommended_payment_method"] != actual["recommended_payment_method"]
            or row["payment_plan"] != actual["payment_plan"]
            or row["earliest_date_for_full_payment"] != actual["earliest_date_for_full_payment"]
            or row["spending_changes_needed"] != actual["spending_changes_needed"]
        ):
            details.append({"request_id": row["request_id"], "predicted": row, "actual": {k: actual[k] for k in row.keys()}, "amount_abs_error": str(err)})
    n = len(rows)
    mae = sum(amount_errors, dec("0")) / dec(n)
    overall_categorical_accuracy = (status_ok + method_ok + plan_ok + date_ok + changes_ok) / (n * 5)
    report = {
        "samples": n,
        "amount_mae": str(mae),
        "amount_exact_within_1": sum(e <= dec("1") for e in amount_errors),
        "status_accuracy": status_ok / n,
        "method_accuracy": method_ok / n,
        "payment_plan_exact": plan_ok / n,
        "earliest_date_accuracy": date_ok / n,
        "spending_changes_exact": changes_ok / n,
        "overall_categorical_accuracy": overall_categorical_accuracy,
        "mismatches": details,
    }
    outdir = root / "evaluation"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "sample_evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Sample Evaluation",
        "",
        f"Samples: {n}",
        f"Amount MAE: {mae}",
        f"Amount exact within 1: {report['amount_exact_within_1']}/{n}",
        f"Status accuracy: {status_ok}/{n}",
        f"Method accuracy: {method_ok}/{n}",
        f"Payment plan exact: {plan_ok}/{n}",
        f"Earliest date accuracy: {date_ok}/{n}",
        f"Spending changes exact: {changes_ok}/{n}",
        f"Overall categorical accuracy: {overall_categorical_accuracy:.4f}",
        "",
        "## Mismatches",
    ]
    for item in details[:25]:
        lines.append(f"- {item['request_id']}: amount error {item['amount_abs_error']}; predicted {item['predicted']['affordability_status']}/{item['predicted']['recommended_payment_method']} vs actual {item['actual']['affordability_status']}/{item['actual']['recommended_payment_method']}")
    (outdir / "sample_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "mismatches"}, indent=2))
    print(f"mismatches: {len(details)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
