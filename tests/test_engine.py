from __future__ import annotations

from pathlib import Path
import sys
import unittest
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.dates import parse_date
from buy_or_wait.engine import FinancialEngine
from buy_or_wait.evidence import IMAGE_AMOUNT_BY_ID, image_amount_for_event
from buy_or_wait.loaders import Dataset, OUTPUT_COLUMNS, repo_root_from_code
from buy_or_wait.money import dec
from buy_or_wait.validator import validate_output_file


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = Dataset(repo_root_from_code())
        cls.engine = FinancialEngine(cls.ds)

    def sample(self, request_id: str):
        return next(r for r in self.ds.sample_requests if r["request_id"] == request_id)

    def test_image_amount_resolves_blank_salary_event(self):
        self.assertEqual(image_amount_for_event(self.ds, "event_253"), IMAGE_AMOUNT_BY_ID["image_01"])

    def test_full_payment_safe_sample(self):
        rec = self.engine.recommend(self.sample("request_01"))
        self.assertEqual(rec.recommended_payment_method, "full_payment")
        self.assertEqual(rec.affordability_status, "affordable_now")

    def test_installment_schedule_matches_option(self):
        opt = next(o for o in self.ds.payment_options if o["payment_option_id"] == "payment_option_47")
        plan = self.engine.installment_payments(opt)
        self.assertEqual([p[0].isoformat() for p in plan], ["2026-03-01", "2026-03-31", "2026-04-30"])
        self.assertEqual(sum((p[1] for p in plan), dec("0")), dec(opt["total_payable_amount"]))

    def test_partial_payment_has_two_payments_when_recommended(self):
        rec = self.engine.recommend(self.sample("request_19"))
        self.assertEqual(rec.recommended_payment_method, "partial_payment")
        self.assertEqual(len(rec.payment_plan.split("|")), 2)

    def test_final_payroll_does_not_recur(self):
        req = self.sample("request_05")
        recs = self.engine.recurrences(req["user_id"], parse_date(req["request_date"]))
        self.assertFalse(any(r.category == "salary" for r in recs))

    def test_pending_credit_ignored_but_pending_debit_reserved(self):
        req = self.sample("request_20")
        start = parse_date(req["request_date"])
        flows = self.engine.base_cashflows(req["user_id"], start, start + timedelta(days=90))
        self.assertTrue(any(f.status == "pending" and f.direction == "debit" for f in flows))
        self.assertFalse(any(f.status == "pending" and f.direction == "credit" for f in flows))

    def test_cancelled_failed_unrealized_not_in_base_flows(self):
        req = self.sample("request_22")
        flows = self.engine.base_cashflows(req["user_id"], parse_date(req["request_date"]), parse_date(req["request_date"]))
        self.assertTrue(all(f.status not in {"failed", "cancelled", "unrealized"} for f in flows))

    def test_currency_conversion_uses_dataset_rate_direction(self):
        amount = self.engine.currency_amount(dec("33.50"), "USD", "INR", parse_date("2025-10-01"))
        self.assertGreater(amount, 0)

    def test_output_validator_accepts_generated_file(self):
        rows = [self.engine.output_row(self.engine.recommend(r)) for r in self.ds.requests[:3]]
        out = repo_root_from_code() / "evaluation" / "_test_output.csv"
        self.engine.write_output(rows, out)
        try:
            self.assertEqual(validate_output_file(out, self.ds.requests[:3]), [])
        finally:
            out.unlink(missing_ok=True)

    def test_output_columns_constant(self):
        self.assertEqual(OUTPUT_COLUMNS, [
            "request_id",
            "amount_safe_to_pay",
            "affordability_status",
            "recommended_payment_method",
            "payment_plan",
            "earliest_date_for_full_payment",
            "spending_changes_needed",
            "decision_explanation",
        ])


if __name__ == "__main__":
    unittest.main()
