from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]


class Dataset:
    def __init__(self, root: Path):
        self.root = root
        self.dataset_dir = root / "dataset"
        self.profiles = self._read("financial_profiles.csv")
        self.events = self._read("financial_events.csv")
        self.exchange_rates = self._read("exchange_rates.csv")
        self.requests = self._read("requests.csv")
        self.sample_requests = self._read("sample_requests.csv")
        self.payment_options = self._read("request_payment_options.csv")
        self.messages = self._read("messages.csv")
        self.images = self._read("images.csv")
        self.profile_by_user = {r["user_id"]: r for r in self.profiles}
        self.events_by_user = defaultdict(list)
        self.events_by_id = {}
        for row in self.events:
            self.events_by_user[row["user_id"]].append(row)
            self.events_by_id[row["event_id"]] = row
        self.options_by_request = defaultdict(list)
        for row in self.payment_options:
            self.options_by_request[row["request_id"]].append(row)
        self.messages_by_user = defaultdict(list)
        self.messages_by_request = defaultdict(list)
        self.messages_by_event = defaultdict(list)
        for row in self.messages:
            self.messages_by_user[row["user_id"]].append(row)
            if row.get("request_id"):
                self.messages_by_request[row["request_id"]].append(row)
            if row.get("related_event_id"):
                self.messages_by_event[row["related_event_id"]].append(row)
        self.images_by_event = defaultdict(list)
        for row in self.images:
            self.images_by_event[row.get("related_event_id", "")].append(row)
        self.rate = {(r["rate_date"], r["from_currency"], r["to_currency"]): r["rate"] for r in self.exchange_rates}

    def _read(self, name: str) -> list[dict]:
        with (self.dataset_dir / name).open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))


def repo_root_from_code() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "dataset").exists():
            return parent
    return Path(__file__).resolve().parents[1]
