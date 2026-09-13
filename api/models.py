from __future__ import annotations

from django.db import models


class FinancialProfile(models.Model):
    user_id = models.CharField(max_length=64, primary_key=True)
    home_currency = models.CharField(max_length=8)
    current_available_balance = models.DecimalField(max_digits=18, decimal_places=2)
    minimum_balance_to_keep = models.DecimalField(max_digits=18, decimal_places=2)
    financial_priorities = models.TextField(blank=True)
    expense_categories_to_protect = models.TextField(blank=True)
    expense_categories_user_is_willing_to_reduce = models.TextField(blank=True)
    expense_categories_user_is_willing_to_stop = models.TextField(blank=True)
    payment_methods_user_will_consider = models.TextField(blank=True)
    max_installment_months = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "financial_profiles"

    def __str__(self) -> str:
        return self.user_id


class FinancialEvent(models.Model):
    event_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(FinancialProfile, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=64)
    direction = models.CharField(max_length=16)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8)
    event_date = models.DateField()
    settlement_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32)
    linked_event_id = models.CharField(max_length=64, blank=True)
    flexibility = models.CharField(max_length=64, blank=True)
    minimum_allowed_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "financial_events"
        indexes = [
            models.Index(fields=["user", "event_date"]),
            models.Index(fields=["category", "direction"]),
        ]

    def __str__(self) -> str:
        return self.event_id


class PurchaseRequest(models.Model):
    request_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(FinancialProfile, on_delete=models.CASCADE, related_name="requests")
    request_date = models.DateField()
    request_type = models.CharField(max_length=64)
    requested_amount = models.DecimalField(max_digits=18, decimal_places=2)
    desired_completion_date = models.DateField()
    allows_partial_payment = models.BooleanField(default=False)
    request_text = models.TextField(blank=True)
    is_sample = models.BooleanField(default=False)

    expected_amount_safe_to_pay = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    expected_affordability_status = models.CharField(max_length=64, blank=True)
    expected_recommended_payment_method = models.CharField(max_length=64, blank=True)
    expected_payment_plan = models.TextField(blank=True)
    expected_earliest_date_for_full_payment = models.DateField(null=True, blank=True)
    expected_spending_changes_needed = models.TextField(blank=True)
    expected_decision_explanation = models.TextField(blank=True)

    class Meta:
        db_table = "purchase_requests"
        indexes = [
            models.Index(fields=["user", "request_date"]),
            models.Index(fields=["is_sample"]),
        ]

    def __str__(self) -> str:
        return self.request_id


class PaymentOption(models.Model):
    payment_option_id = models.CharField(max_length=64, primary_key=True)
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="payment_options")
    payment_method = models.CharField(max_length=64)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2)
    number_of_payments = models.PositiveIntegerField()
    first_payment_date = models.DateField()
    payment_frequency_days = models.PositiveIntegerField(null=True, blank=True)
    financing_fee = models.DecimalField(max_digits=18, decimal_places=2)
    total_payable_amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        db_table = "payment_options"

    def __str__(self) -> str:
        return self.payment_option_id


class Message(models.Model):
    message_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(FinancialProfile, on_delete=models.CASCADE, related_name="messages")
    request = models.ForeignKey(PurchaseRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages")
    related_event = models.ForeignKey(FinancialEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages")
    sent_at = models.DateTimeField()
    source_type = models.CharField(max_length=64)
    message_text = models.TextField()

    class Meta:
        db_table = "messages"
        indexes = [models.Index(fields=["user", "sent_at"])]

    def __str__(self) -> str:
        return self.message_id


class EvidenceImage(models.Model):
    image_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(FinancialProfile, on_delete=models.CASCADE, related_name="images")
    request = models.ForeignKey(PurchaseRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="images")
    related_event = models.ForeignKey(FinancialEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="images")

    class Meta:
        db_table = "evidence_images"

    def __str__(self) -> str:
        return self.image_id


class ExchangeRate(models.Model):
    rate_date = models.DateField()
    from_currency = models.CharField(max_length=8)
    to_currency = models.CharField(max_length=8)
    rate = models.DecimalField(max_digits=18, decimal_places=8)

    class Meta:
        db_table = "exchange_rates"
        constraints = [
            models.UniqueConstraint(fields=["rate_date", "from_currency", "to_currency"], name="uniq_exchange_rate_pair_date")
        ]

    def __str__(self) -> str:
        return f"{self.rate_date}:{self.from_currency}->{self.to_currency}"


class Recommendation(models.Model):
    request = models.OneToOneField(PurchaseRequest, on_delete=models.CASCADE, primary_key=True, related_name="recommendation")
    amount_safe_to_pay = models.DecimalField(max_digits=18, decimal_places=2)
    affordability_status = models.CharField(max_length=64)
    recommended_payment_method = models.CharField(max_length=64)
    payment_plan = models.TextField()
    earliest_date_for_full_payment = models.DateField(null=True, blank=True)
    spending_changes_needed = models.TextField(blank=True)
    decision_explanation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recommendations"

    def __str__(self) -> str:
        return self.request_id
