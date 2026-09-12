from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations
from statistics import median
import csv
import json
import re

from .dates import add_months, date_range, parse_date
from .evidence import confirmed_message_cashflows, image_amount_for_event
from .loaders import Dataset, OUTPUT_COLUMNS
from .models import Candidate, CashFlow, Recommendation, Recurrence
from .money import dec, fmt_money, pretty, q2


ALLOWED_STATUSES = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
ALLOWED_METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
ESSENTIAL_DEFAULTS = {"rent", "housing", "utilities", "groceries", "transport", "insurance", "healthcare", "debt_repayment", "education", "family_support"}


def human_date(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


class FinancialEngine:
    def __init__(self, dataset: Dataset):
        self.ds = dataset
        self._recurrence_cache: dict[str, list[Recurrence]] = {}
        self._flow_cache: dict[tuple[str, str], list[CashFlow]] = {}

    def currency_amount(self, amount: Decimal, currency: str, home: str, settlement_date: date) -> Decimal:
        if currency == home:
            return q2(amount)
        key = (settlement_date.isoformat(), currency, home)
        rate = self.ds.rate.get(key)
        if rate is None:
            # Use the nearest prior supplied rate in the stated direction. The data has sparse fixed rates.
            candidates = [(k[0], v) for k, v in self.ds.rate.items() if k[1] == currency and k[2] == home and k[0] <= settlement_date.isoformat()]
            if not candidates:
                candidates = [(k[0], v) for k, v in self.ds.rate.items() if k[1] == currency and k[2] == home]
            if not candidates:
                return q2(amount)
            rate = sorted(candidates)[-1][1]
        return q2(amount * dec(rate))

    def event_amount(self, row: dict, home: str) -> Decimal:
        amount = dec(row.get("amount"))
        if str(row.get("amount", "")).strip() == "":
            extracted = image_amount_for_event(self.ds, row["event_id"])
            amount = extracted if extracted is not None else Decimal("0")
        return self.currency_amount(amount, row.get("currency", home), home, parse_date(row["settlement_date"] or row["event_date"]))

    def base_cashflows(self, user_id: str, request_date: date, horizon: date) -> list[CashFlow]:
        key = (user_id, request_date.isoformat())
        if key in self._flow_cache:
            return self._flow_cache[key]
        profile = self.ds.profile_by_user[user_id]
        home = profile["home_currency"]
        flows: list[CashFlow] = []
        seen_future_keys = set()
        for row in self.ds.events_by_user[user_id]:
            status = row.get("status", "")
            direction = row.get("direction", "")
            if status in {"failed", "cancelled", "unrealized"} or direction == "non_cash":
                continue
            settle = parse_date(row["settlement_date"] or row["event_date"])
            if not (request_date <= settle <= horizon):
                continue
            if status == "pending" and direction == "credit":
                continue
            flow_date = request_date if status == "pending" and direction == "debit" else settle
            amount = self.event_amount(row, home)
            if amount <= 0:
                continue
            key2 = (row["event_id"], flow_date, direction)
            seen_future_keys.add((row["category"], row["description"], flow_date, direction))
            flows.append(CashFlow(flow_date, amount, direction, row["category"], row["event_id"], row["description"], status, row.get("flexibility") or "fixed", dec(row.get("minimum_allowed_amount")), "explicit"))
        for fact in confirmed_message_cashflows(self.ds.messages_by_user[user_id]):
            if request_date <= fact["date"] <= horizon:
                amount = self.currency_amount(fact["amount"], fact["currency"], home, fact["date"])
                flows.append(CashFlow(fact["date"], amount, fact["direction"], fact["category"], fact["message_id"], "confirmed message cashflow", "scheduled", "fixed", Decimal("0"), "message"))
        for rec in self.recurrences(user_id, request_date):
            next_date = self._next_recurrence_date(rec, request_date)
            while next_date <= horizon:
                dup = (rec.category, rec.description, next_date, rec.direction)
                if dup not in seen_future_keys:
                    flows.append(CashFlow(next_date, rec.amount, rec.direction, rec.category, rec.event_id, rec.description, "forecast", rec.flexibility, rec.minimum_allowed_amount, "recurrence"))
                next_date = self._advance(rec, next_date)
        flows.sort(key=lambda f: (f.flow_date, 0 if f.direction == "debit" else 1, f.event_id))
        self._flow_cache[key] = flows
        return flows

    def recurrences(self, user_id: str, request_date: date) -> list[Recurrence]:
        if user_id in self._recurrence_cache:
            return self._recurrence_cache[user_id]
        profile = self.ds.profile_by_user[user_id]
        home = profile["home_currency"]
        messages_text = "\n".join(m.get("message_text", "").lower() for m in self.ds.messages_by_user[user_id])
        suppress_salary = any(term in messages_text for term in ["employment has ended", "kontrak musiman saat ini telah berakhir", "current seasonal contract has ended", "no regular salary payments"])
        salary_rows_for_lifecycle = [
            row for row in self.ds.events_by_user[user_id]
            if row.get("category") == "salary" and row.get("direction") == "credit" and parse_date(row["settlement_date"] or row["event_date"]) <= request_date
        ]
        if salary_rows_for_lifecycle:
            last_salary = sorted(salary_rows_for_lifecycle, key=lambda r: parse_date(r["settlement_date"] or r["event_date"]))[-1]
            if "final" in last_salary.get("description", "").lower():
                suppress_salary = True
        rows = []
        for row in self.ds.events_by_user[user_id]:
            if row.get("status") in {"failed", "cancelled", "unrealized"} or row.get("direction") == "non_cash":
                continue
            settle = parse_date(row["settlement_date"] or row["event_date"])
            if settle >= request_date:
                continue
            if row.get("status") == "pending" and row.get("direction") == "credit":
                continue
            amount = self.event_amount(row, home)
            if amount <= 0:
                continue
            rows.append((row, settle, amount))
        recurrences: list[Recurrence] = []

        def add_group(group_rows, cadence_days: int, grouped_description: bool):
            group_rows = sorted(group_rows, key=lambda x: x[1])
            if len(group_rows) < 3:
                return
            last_row, last_date, _ = group_rows[-1]
            amounts = [x[2] for x in group_rows[-4:]]
            category = last_row["category"]
            if not grouped_description:
                amount = sum(amounts, Decimal("0")) / Decimal(len(amounts))
            elif category in ESSENTIAL_DEFAULTS or category in set(profile.get("expense_categories_to_protect", "").split("|")):
                amount = max(amounts)
            else:
                amount = sum(amounts, Decimal("0")) / Decimal(len(amounts))
            if last_row["direction"] == "credit":
                amount = amounts[-1]
            if suppress_salary and category == "salary":
                return
            recurrences.append(Recurrence(
                user_id=user_id,
                direction=last_row["direction"],
                category=category,
                description=last_row["description"] if grouped_description else category,
                cadence_days=cadence_days,
                anchor_date=last_date,
                amount=q2(amount),
                event_id=last_row["event_id"],
                flexibility=last_row.get("flexibility") or "fixed",
                minimum_allowed_amount=dec(last_row.get("minimum_allowed_amount")),
            ))

        monthly_groups = defaultdict(list)
        category_groups = defaultdict(list)
        for item in rows:
            row = item[0]
            protected_cats = set(profile.get("expense_categories_to_protect", "").split("|"))
            if row["direction"] == "debit" and row["category"] in {"groceries", "transport"} and row["category"] in protected_cats:
                category_groups[(row["direction"], row["category"])].append(item)
            else:
                monthly_groups[(row["direction"], row["category"], row["description"])].append(item)
        for group in monthly_groups.values():
            dates = [x[1] for x in sorted(group, key=lambda x: x[1])]
            if len(dates) >= 3:
                gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
                med = median(gaps)
                if 26 <= med <= 35:
                    add_group(group, 30, True)
        for group in category_groups.values():
            dates = [x[1] for x in sorted(group, key=lambda x: x[1])]
            if len(dates) >= 6:
                gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
                med = int(round(median(gaps)))
                if 5 <= med <= 16:
                    add_group(group, med, False)
        if not suppress_salary:
            future_salary = []
            for row in self.ds.events_by_user[user_id]:
                if row.get("category") == "salary" and row.get("direction") == "credit" and row.get("status") in {"scheduled", "settled"}:
                    settle = parse_date(row["settlement_date"] or row["event_date"])
                    if settle >= request_date:
                        future_salary.append((settle, row, self.event_amount(row, home)))
            if future_salary:
                settle, row, amount = sorted(future_salary, key=lambda x: x[0])[0]
                recurrences = [r for r in recurrences if not (r.direction == "credit" and r.category == "salary")]
                recurrences.append(Recurrence(user_id, "credit", "salary", row["description"], 30, settle, q2(amount), row["event_id"], "fixed"))
        # Message facts can define the next payroll/invoice more accurately than older history.
        for fact in confirmed_message_cashflows(self.ds.messages_by_user[user_id]):
            if fact["category"] == "salary" and fact["date"] >= request_date:
                amount = self.currency_amount(fact["amount"], fact["currency"], home, fact["date"])
                recurrences = [r for r in recurrences if not (r.direction == "credit" and r.category == "salary")]
                recurrences.append(Recurrence(user_id, "credit", "salary", "salary", 30, fact["date"] - timedelta(days=30), q2(amount), fact["message_id"], "fixed"))
        for msg in self.ds.messages_by_user[user_id]:
            text = msg.get("message_text", "")
            lower = text.lower()
            if msg.get("source_type") != "employer":
                continue
            if not any(term in lower for term in ["next salary", "next payroll", "payroll", "gaji berikutnya"]):
                continue
            if not any(term in lower for term in ["reduced to", "naik menjadi", "increased to", "temporary monthly pay"]):
                continue
            if re.search(r"\b20[0-9]{2}-[0-9]{2}-[0-9]{2}\b", text):
                continue
            amount_match = re.search(r"\b(INR|IDR|ZAR|EUR|USD)\s+([0-9][0-9,]*(?:\.[0-9]+)?)", text, re.I)
            if not amount_match:
                continue
            salary_rows = [
                (settle, row)
                for row in self.ds.events_by_user[user_id]
                if row.get("category") == "salary"
                and row.get("direction") == "credit"
                and (settle := parse_date(row["settlement_date"] or row["event_date"])) <= request_date
            ]
            if not salary_rows:
                continue
            last_salary_date, _ = sorted(salary_rows, key=lambda x: x[0])[-1]
            amount = self.currency_amount(dec(amount_match.group(2)), amount_match.group(1).upper(), home, request_date)
            recurrences = [r for r in recurrences if not (r.direction == "credit" and r.category == "salary")]
            recurrences.append(Recurrence(user_id, "credit", "salary", "salary", 30, last_salary_date, q2(amount), msg["message_id"], "fixed"))
        self._recurrence_cache[user_id] = recurrences
        return recurrences

    def _advance(self, rec: Recurrence, current: date) -> date:
        if rec.cadence_days == 30:
            return add_months(current, 1)
        return current + timedelta(days=rec.cadence_days)

    def _next_recurrence_date(self, rec: Recurrence, request_date: date) -> date:
        d = self._advance(rec, rec.anchor_date)
        while d < request_date:
            d = self._advance(rec, d)
        return d

    def simulate(self, request: dict, payments: list[tuple[date, Decimal]], changes: list[str] | None = None) -> tuple[bool, dict]:
        changes = changes or []
        profile = self.ds.profile_by_user[request["user_id"]]
        start = parse_date(request["request_date"])
        horizon = start + timedelta(days=90)
        balance = dec(profile["current_available_balance"])
        minimum = dec(profile["minimum_balance_to_keep"])
        stop_ids = {c.split(":")[1] for c in changes if c.startswith("stop:")}
        reduce_to = {parts[1]: dec(parts[2]) for c in changes if c.startswith("reduce_to:") for parts in [c.split(":")]}
        by_date = defaultdict(list)
        for flow in self.base_cashflows(request["user_id"], start, horizon):
            if flow.source == "recurrence" and flow.event_id in stop_ids:
                continue
            if flow.source == "recurrence" and flow.event_id in reduce_to and flow.direction == "debit":
                flow = CashFlow(flow.flow_date, reduce_to[flow.event_id], flow.direction, flow.category, flow.event_id, flow.description, flow.status, flow.flexibility, flow.minimum_allowed_amount, flow.source)
            by_date[flow.flow_date].append(flow)
        for idx, (pdate, amount) in enumerate(payments):
            if start <= pdate <= horizon:
                by_date[pdate].append(CashFlow(pdate, q2(amount), "debit", "request", f"request_payment_{idx}", "recommended payment", "planned", "fixed", Decimal("0"), "payment"))
        min_balance = balance
        trace = []
        for d in date_range(start, horizon):
            flows = by_date.get(d, [])
            flows.sort(key=lambda f: (
                0 if f.direction == "credit" else 1 if f.source == "payment" else 2,
                f.event_id,
            ))
            for flow in flows:
                before = balance
                balance += flow.signed
                min_balance = min(min_balance, balance)
                trace.append({"date": d.isoformat(), "event_id": flow.event_id, "category": flow.category, "amount": fmt_money(flow.signed), "balance": fmt_money(balance)})
                if balance < minimum:
                    return False, {"min_balance": fmt_money(min_balance), "failed_on": d.isoformat(), "failed_event": flow.event_id, "ending_balance": fmt_money(balance), "trace": trace[-12:]}
        return True, {"min_balance": fmt_money(min_balance), "ending_balance": fmt_money(balance), "trace": trace[-12:]}

    def amount_safe_today(self, request: dict) -> Decimal:
        requested = dec(request["requested_amount"])
        lo, hi = Decimal("0"), requested
        for _ in range(48):
            mid = q2((lo + hi) / 2)
            ok, _ = self.simulate(request, [(parse_date(request["request_date"]), mid)])
            if ok:
                lo = mid
            else:
                hi = mid
            if hi - lo <= Decimal("0.01"):
                break
        return min(requested, q2(lo))

    def earliest_full_date(self, request: dict) -> str:
        amount = dec(request["requested_amount"])
        start = parse_date(request["request_date"])
        deadline = parse_date(request["desired_completion_date"])
        horizon = min(start + timedelta(days=90), deadline)
        for d in date_range(start, horizon):
            ok, _ = self.simulate(request, [(d, amount)])
            if ok:
                return d.isoformat()
        return ""

    def serialize_plan(self, payments: list[tuple[date, Decimal]]) -> str:
        if not payments:
            return "none"
        return "|".join(f"{d.isoformat()}:{self.fmt_plan_amount(a)}" for d, a in sorted(payments, key=lambda x: x[0]))

    def fmt_plan_amount(self, amount: Decimal) -> str:
        amount = q2(amount)
        if amount == amount.to_integral_value():
            return fmt_money(amount)
        return format(amount, "f")

    def installment_payments(self, opt: dict) -> list[tuple[date, Decimal]]:
        n = int(opt["number_of_payments"])
        first = parse_date(opt["first_payment_date"])
        freq = int(opt.get("payment_frequency_days") or 0)
        total = dec(opt["total_payable_amount"])
        amount = dec(opt["payment_amount"])
        payments = []
        paid = Decimal("0")
        for i in range(n):
            d = first + timedelta(days=freq * i)
            part = amount if i < n - 1 else q2(total - paid)
            payments.append((d, part))
            paid += part
        return payments

    def legal_changes(self, request: dict) -> list[str]:
        profile = self.ds.profile_by_user[request["user_id"]]
        reduce_cats = {x for x in profile.get("expense_categories_user_is_willing_to_reduce", "").split("|") if x}
        stop_cats = {x for x in profile.get("expense_categories_user_is_willing_to_stop", "").split("|") if x}
        protected = {x for x in profile.get("expense_categories_to_protect", "").split("|") if x}
        changes = []
        for rec in self.recurrences(request["user_id"], parse_date(request["request_date"])):
            if rec.direction != "debit" or rec.category in protected:
                continue
            if rec.category in stop_cats and rec.flexibility in {"stoppable", "reducible_or_stoppable"}:
                changes.append((rec.amount, f"stop:{rec.event_id}"))
            if rec.category in reduce_cats and rec.flexibility in {"reducible", "reducible_or_stoppable"} and rec.minimum_allowed_amount >= 0 and rec.minimum_allowed_amount < rec.amount:
                changes.append((rec.amount - rec.minimum_allowed_amount, f"reduce_to:{rec.event_id}:{fmt_money(rec.minimum_allowed_amount)}"))
        dedup = {}
        for savings, change in changes:
            event_id = change.split(":")[1]
            if event_id not in dedup or savings > dedup[event_id][0]:
                dedup[event_id] = (savings, change)
        return [c for _, c in sorted(dedup.values(), key=lambda x: (-x[0], x[1]))]

    def safe_with_optional_changes(self, request: dict, payments: list[tuple[date, Decimal]]) -> tuple[bool, list[str], dict]:
        ok, summary = self.simulate(request, payments)
        if ok:
            return True, [], summary
        legal = self.legal_changes(request)
        for size in range(1, min(3, len(legal)) + 1):
            for combo in combinations(legal, size):
                ids = [c.split(":")[1] for c in combo]
                if len(ids) != len(set(ids)):
                    continue
                ok, summary = self.simulate(request, payments, list(combo))
                if ok:
                    return True, list(combo), summary
        return False, [], summary

    def accepted_methods(self, profile: dict) -> set[str]:
        return {x for x in profile.get("payment_methods_user_will_consider", "").split("|") if x}

    def candidates(self, request: dict, amount_safe: Decimal, earliest: str) -> list[Candidate]:
        profile = self.ds.profile_by_user[request["user_id"]]
        accepted = self.accepted_methods(profile)
        requested = dec(request["requested_amount"])
        request_date = parse_date(request["request_date"])
        deadline = parse_date(request["desired_completion_date"])
        cands: list[Candidate] = []
        if "full_payment" in accepted:
            payments = [(request_date, requested)]
            changes = []
            ok = False
            direct_ok, direct_summary = self.simulate(request, payments)
            if direct_ok:
                margin = dec(direct_summary["min_balance"]) - dec(profile["minimum_balance_to_keep"])
                if requested == 0 or margin / requested >= Decimal("0.15"):
                    ok = True
            if not ok and amount_safe < requested:
                legal = self.legal_changes(request)
                for size in range(1, min(3, len(legal)) + 1):
                    for combo in combinations(legal, size):
                        ids = [c.split(":")[1] for c in combo]
                        if len(ids) != len(set(ids)):
                            continue
                        ok_try, _ = self.simulate(request, payments, list(combo))
                        if ok_try:
                            ok = True
                            changes = list(combo)
                            break
                    if ok:
                        break
            if not ok:
                ok, changes, _ = self.safe_with_optional_changes(request, payments)
            if ok:
                cands.append(Candidate("full_payment", "affordable_now" if not changes else "affordable_with_plan", payments, requested, "", changes, True, request_date <= deadline))
            if earliest and parse_date(earliest) > request_date:
                payments = [(parse_date(earliest), requested)]
                ok, summary = self.simulate(request, payments)
                if ok:
                    cands.append(Candidate("wait", "affordable_later", payments, requested, "", [], True, parse_date(earliest) <= deadline))
        if "partial_payment" in accepted and request.get("allows_partial_payment", "").lower() == "true" and earliest:
            e_date = parse_date(earliest)
            if Decimal("0") < amount_safe < requested and e_date <= deadline:
                payments = [(request_date, amount_safe), (e_date, q2(requested - amount_safe))]
                ok, summary = self.simulate(request, payments)
                if ok:
                    cands.append(Candidate("partial_payment", "affordable_with_plan", payments, requested, "", [], True, True))
        if "installments" in accepted:
            max_months = dec(profile.get("max_installment_months"))
            for opt in self.ds.options_by_request[request["request_id"]]:
                if opt["payment_method"] != "installments":
                    continue
                payments = self.installment_payments(opt)
                if payments[-1][0] > deadline:
                    continue
                if max_months and (payments[-1][0] - payments[0][0]).days > int(max_months * 31):
                    continue
                ok, changes, _ = self.safe_with_optional_changes(request, payments)
                if ok:
                    cands.append(Candidate("installments", "affordable_with_plan", payments, dec(opt["total_payable_amount"]), opt["payment_option_id"], changes, True, True))
        return cands

    def rank_candidate(self, cand: Candidate):
        option_num = int(re.sub(r"\D", "", cand.option_id) or "999999")
        return (
            0 if cand.completes_by_deadline else 1,
            0 if not cand.changes else 1,
            cand.total,
            cand.payments[0][0] if cand.payments else date.max,
            len(cand.payments),
            option_num,
        )

    def recommend(self, request: dict) -> Recommendation:
        profile = self.ds.profile_by_user[request["user_id"]]
        currency = profile["home_currency"]
        requested = dec(request["requested_amount"])
        request_date = parse_date(request["request_date"])
        amount_safe = self.amount_safe_today(request)
        earliest = self.earliest_full_date(request)
        cands = self.candidates(request, amount_safe, earliest)
        if cands:
            best = sorted(cands, key=self.rank_candidate)[0]
            plan = self.serialize_plan(best.payments)
            changes = "|".join(best.changes) if best.changes else "none"
            explanation = self.explain(request, best, amount_safe, earliest)
            ok, summary = self.simulate(request, best.payments, best.changes)
            return Recommendation(request["request_id"], amount_safe, best.status, best.method, plan, earliest, changes, explanation, summary, self.evidence_summary(request))
        explanation = self.not_recommended_explanation(request, amount_safe)
        return Recommendation(request["request_id"], amount_safe, "not_affordable", "not_recommended", "none", earliest, "none", explanation, {}, self.evidence_summary(request))

    def explain(self, request: dict, cand: Candidate, amount_safe: Decimal, earliest: str) -> str:
        profile = self.ds.profile_by_user[request["user_id"]]
        cur = profile["home_currency"]
        minimum = dec(profile["minimum_balance_to_keep"])
        requested = dec(request["requested_amount"])
        if cand.method == "full_payment" and cand.changes:
            actions = []
            for ch in cand.changes:
                parts = ch.split(":")
                row = self.ds.events_by_id.get(parts[1], {})
                if parts[0] == "stop":
                    actions.append(f"stop {row.get('description', row.get('category', 'a flexible expense')).lower()}")
                else:
                    actions.append(f"reduce {row.get('description', row.get('category', 'a flexible expense')).lower()} to {pretty(dec(parts[2]), cur)}")
            return f"{' and '.join(actions).capitalize()}, then pay {pretty(requested, cur)} today. This keeps the {pretty(minimum, cur)} minimum protected."
        if cand.method == "full_payment":
            return f"Pay {pretty(requested, cur)} today. This leaves at least {pretty(minimum, cur)} available over the next 90 days."
        if cand.method == "installments":
            first = cand.payments[0]
            return f"Use {len(cand.payments)} installments of {pretty(first[1], cur)}, starting {human_date(first[0])}. This leaves at least {pretty(minimum, cur)} available."
        if cand.method == "partial_payment":
            return f"Pay {pretty(cand.payments[0][1], cur)} today and the remaining {pretty(cand.payments[1][1], cur)} on {human_date(cand.payments[1][0])}. This completes the full request and keeps the {pretty(minimum, cur)} minimum protected."
        if cand.method == "wait":
            d = cand.payments[0][0]
            return f"Pay {pretty(requested, cur)} in full on {human_date(d)}. Paying earlier would take the balance below the {pretty(minimum, cur)} minimum."
        return self.not_recommended_explanation(request, amount_safe)

    def not_recommended_explanation(self, request: dict, amount_safe: Decimal) -> str:
        profile = self.ds.profile_by_user[request["user_id"]]
        cur = profile["home_currency"]
        requested = dec(request["requested_amount"])
        minimum = dec(profile["minimum_balance_to_keep"])
        deadline = human_date(parse_date(request["desired_completion_date"]))
        if amount_safe > 0:
            return f"Do not proceed with the {pretty(requested, cur)} request. Although {pretty(amount_safe, cur)} is available today, the full amount cannot be completed safely within 90 days."
        return f"Do not make this payment by {deadline}. None of the available options keeps the {pretty(minimum, cur)} minimum protected."

    def evidence_summary(self, request: dict) -> list[dict]:
        out = []
        for msg in self.ds.messages_by_user[request["user_id"]]:
            if msg.get("request_id") in {"", request["request_id"]}:
                out.append({"type": "message", "id": msg["message_id"], "source": msg["source_type"]})
        for row in self.ds.events_by_user[request["user_id"]]:
            if str(row.get("amount", "")).strip() == "" and self.ds.images_by_event.get(row["event_id"]):
                out.append({"type": "image", "event_id": row["event_id"], "amount": fmt_money(image_amount_for_event(self.ds, row["event_id"]) or Decimal("0"))})
        return out[:10]

    def output_row(self, rec: Recommendation) -> dict:
        return {
            "request_id": rec.request_id,
            "amount_safe_to_pay": fmt_money(rec.amount_safe_to_pay),
            "affordability_status": rec.affordability_status,
            "recommended_payment_method": rec.recommended_payment_method,
            "payment_plan": rec.payment_plan,
            "earliest_date_for_full_payment": rec.earliest_date_for_full_payment,
            "spending_changes_needed": rec.spending_changes_needed,
            "decision_explanation": rec.decision_explanation,
        }

    def run_requests(self, requests: list[dict]) -> list[Recommendation]:
        return [self.recommend(r) for r in requests]

    def write_output(self, rows: list[dict], path):
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
