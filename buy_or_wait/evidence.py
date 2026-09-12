from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .dates import parse_date
from .money import dec


IMAGE_AMOUNT_BY_ID = {
    "image_01": Decimal("4365000"),
    "image_02": Decimal("100000"),
    "image_03": Decimal("41272"),
    "image_04": Decimal("2854"),
    "image_05": Decimal("704.05"),
    "image_06": Decimal("1995"),
    "image_07": Decimal("8528"),
    "image_08": Decimal("15339"),
    "image_09": Decimal("723"),
    "image_10": Decimal("79679.26"),
    "image_11": Decimal("3650"),
    "image_12": Decimal("33.50"),
    "image_13": Decimal("2298"),
    "image_14": Decimal("4543"),
    "image_15": Decimal("9968"),
    "image_16": Decimal("393.22"),
}


AMOUNT_RE = re.compile(r"\b(INR|IDR|ZAR|EUR|USD)\s+([0-9][0-9,]*(?:\.[0-9]+)?)", re.I)
DATE_RE = re.compile(r"\b(20[0-9]{2}-[0-9]{2}-[0-9]{2})\b")


def image_amount_for_event(dataset, event_id: str) -> Decimal | None:
    for image in dataset.images_by_event.get(event_id, []):
        amount = IMAGE_AMOUNT_BY_ID.get(image["image_id"])
        if amount is not None:
            return amount
    return None


def confirmed_message_cashflows(messages: list[dict]) -> list[dict]:
    facts: list[dict] = []
    for msg in messages:
        text = msg.get("message_text", "")
        lower = text.lower()
        if any(term in lower for term in ["pending", "menunggu", "not reached", "not been credited", "belum disetujui"]):
            if not any(term in lower for term in ["approved an invoice payment", "menyetujui pembayaran faktur"]):
                continue
        date_match = DATE_RE.search(text)
        amount_match = AMOUNT_RE.search(text)
        if not amount_match:
            continue
        currency, amount = amount_match.group(1).upper(), dec(amount_match.group(2))
        flow_date: date | None = None
        if date_match:
            flow_date = parse_date(date_match.group(1))
        direction = "credit"
        category = "salary" if msg.get("source_type") == "employer" else "confirmed_income"
        if any(term in lower for term in ["invoice payment", "pembayaran faktur"]):
            category = "confirmed_income"
        if any(term in lower for term in ["salary", "gaji", "payroll", "penggajian"]):
            category = "salary"
        if flow_date and any(term in lower for term in [
            "confirmed", "dikonfirmasi", "approved", "menyetujui", "scheduled for", "dijadwalkan",
            "credit date", "berlaku mulai", "applies from", "expected on", "diperkirakan",
            "resumes on", "naik menjadi", "increased to", "reduced to", "first salary",
        ]):
            facts.append({
                "date": flow_date,
                "amount": amount,
                "currency": currency,
                "direction": direction,
                "category": category,
                "message_id": msg["message_id"],
                "text": text,
            })
    return facts

