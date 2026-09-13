from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date, parse_datetime

from api.models import (
    EvidenceImage,
    ExchangeRate,
    FinancialEvent,
    FinancialProfile,
    Message,
    PaymentOption,
    PurchaseRequest,
)
from buy_or_wait.loaders import repo_root_from_code


def dec(value: str) -> Decimal | None:
    value = (value or "").strip()
    return Decimal(value) if value else None


def boolish(value: str) -> bool:
    return str(value).strip().lower() == "true"


def read_csv(dataset_dir: Path, name: str) -> list[dict]:
    with (dataset_dir / name).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "Import bundled CSV data into Django database tables."

    def handle(self, *args, **options):
        dataset_dir = repo_root_from_code() / "dataset"

        for row in read_csv(dataset_dir, "financial_profiles.csv"):
            FinancialProfile.objects.update_or_create(
                user_id=row["user_id"],
                defaults={
                    "home_currency": row["home_currency"],
                    "current_available_balance": dec(row["current_available_balance"]) or Decimal("0"),
                    "minimum_balance_to_keep": dec(row["minimum_balance_to_keep"]) or Decimal("0"),
                    "financial_priorities": row["financial_priorities"],
                    "expense_categories_to_protect": row["expense_categories_to_protect"],
                    "expense_categories_user_is_willing_to_reduce": row["expense_categories_user_is_willing_to_reduce"],
                    "expense_categories_user_is_willing_to_stop": row["expense_categories_user_is_willing_to_stop"],
                    "payment_methods_user_will_consider": row["payment_methods_user_will_consider"],
                    "max_installment_months": dec(row["max_installment_months"]),
                },
            )

        for row in read_csv(dataset_dir, "financial_events.csv"):
            FinancialEvent.objects.update_or_create(
                event_id=row["event_id"],
                defaults={
                    "user_id": row["user_id"],
                    "event_type": row["event_type"],
                    "description": row["description"],
                    "category": row["category"],
                    "direction": row["direction"],
                    "amount": dec(row["amount"]),
                    "currency": row["currency"],
                    "event_date": parse_date(row["event_date"]),
                    "settlement_date": parse_date(row["settlement_date"]) if row["settlement_date"] else None,
                    "status": row["status"],
                    "linked_event_id": row["linked_event_id"],
                    "flexibility": row["flexibility"],
                    "minimum_allowed_amount": dec(row["minimum_allowed_amount"]),
                },
            )

        for filename, is_sample in [("requests.csv", False), ("sample_requests.csv", True)]:
            for row in read_csv(dataset_dir, filename):
                PurchaseRequest.objects.update_or_create(
                    request_id=row["request_id"],
                    defaults={
                        "user_id": row["user_id"],
                        "request_date": parse_date(row["request_date"]),
                        "request_type": row["request_type"],
                        "requested_amount": dec(row["requested_amount"]) or Decimal("0"),
                        "desired_completion_date": parse_date(row["desired_completion_date"]),
                        "allows_partial_payment": boolish(row["allows_partial_payment"]),
                        "request_text": row["request_text"],
                        "is_sample": is_sample,
                        "expected_amount_safe_to_pay": dec(row.get("amount_safe_to_pay", "")),
                        "expected_affordability_status": row.get("affordability_status", ""),
                        "expected_recommended_payment_method": row.get("recommended_payment_method", ""),
                        "expected_payment_plan": row.get("payment_plan", ""),
                        "expected_earliest_date_for_full_payment": parse_date(row.get("earliest_date_for_full_payment", "")) if row.get("earliest_date_for_full_payment", "") else None,
                        "expected_spending_changes_needed": row.get("spending_changes_needed", ""),
                        "expected_decision_explanation": row.get("decision_explanation", ""),
                    },
                )

        for row in read_csv(dataset_dir, "request_payment_options.csv"):
            PaymentOption.objects.update_or_create(
                payment_option_id=row["payment_option_id"],
                defaults={
                    "request_id": row["request_id"],
                    "payment_method": row["payment_method"],
                    "payment_amount": dec(row["payment_amount"]) or Decimal("0"),
                    "number_of_payments": int(row["number_of_payments"] or 0),
                    "first_payment_date": parse_date(row["first_payment_date"]),
                    "payment_frequency_days": int(row["payment_frequency_days"]) if row["payment_frequency_days"] else None,
                    "financing_fee": dec(row["financing_fee"]) or Decimal("0"),
                    "total_payable_amount": dec(row["total_payable_amount"]) or Decimal("0"),
                },
            )

        for row in read_csv(dataset_dir, "messages.csv"):
            Message.objects.update_or_create(
                message_id=row["message_id"],
                defaults={
                    "user_id": row["user_id"],
                    "request_id": row["request_id"] or None,
                    "related_event_id": row["related_event_id"] or None,
                    "sent_at": parse_datetime(row["sent_at"]),
                    "source_type": row["source_type"],
                    "message_text": row["message_text"],
                },
            )

        for row in read_csv(dataset_dir, "images.csv"):
            EvidenceImage.objects.update_or_create(
                image_id=row["image_id"],
                defaults={
                    "user_id": row["user_id"],
                    "request_id": row["request_id"] or None,
                    "related_event_id": row["related_event_id"] or None,
                },
            )

        for row in read_csv(dataset_dir, "exchange_rates.csv"):
            ExchangeRate.objects.update_or_create(
                rate_date=parse_date(row["rate_date"]),
                from_currency=row["from_currency"],
                to_currency=row["to_currency"],
                defaults={"rate": dec(row["rate"]) or Decimal("0")},
            )

        self.stdout.write(self.style.SUCCESS("Imported dataset into database tables."))
