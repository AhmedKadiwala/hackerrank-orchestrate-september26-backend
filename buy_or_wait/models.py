from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CashFlow:
    flow_date: date
    amount: Decimal
    direction: str
    category: str
    event_id: str
    description: str
    status: str
    flexibility: str = "fixed"
    minimum_allowed_amount: Decimal = Decimal("0")
    source: str = "event"

    @property
    def signed(self) -> Decimal:
        return self.amount if self.direction == "credit" else -self.amount


@dataclass
class Recurrence:
    user_id: str
    direction: str
    category: str
    description: str
    cadence_days: int
    anchor_date: date
    amount: Decimal
    event_id: str
    flexibility: str
    minimum_allowed_amount: Decimal = Decimal("0")


@dataclass
class Candidate:
    method: str
    status: str
    payments: list[tuple[date, Decimal]]
    total: Decimal
    option_id: str = ""
    changes: list[str] = field(default_factory=list)
    safe: bool = False
    completes_by_deadline: bool = True


@dataclass
class Recommendation:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str
    forecast_summary: dict = field(default_factory=dict)
    evidence_summary: list[dict] = field(default_factory=list)

