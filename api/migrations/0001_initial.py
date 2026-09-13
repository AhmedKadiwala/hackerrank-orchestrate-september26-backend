from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FinancialProfile",
            fields=[
                ("user_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("home_currency", models.CharField(max_length=8)),
                ("current_available_balance", models.DecimalField(decimal_places=2, max_digits=18)),
                ("minimum_balance_to_keep", models.DecimalField(decimal_places=2, max_digits=18)),
                ("financial_priorities", models.TextField(blank=True)),
                ("expense_categories_to_protect", models.TextField(blank=True)),
                ("expense_categories_user_is_willing_to_reduce", models.TextField(blank=True)),
                ("expense_categories_user_is_willing_to_stop", models.TextField(blank=True)),
                ("payment_methods_user_will_consider", models.TextField(blank=True)),
                ("max_installment_months", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
            ],
            options={"db_table": "financial_profiles"},
        ),
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rate_date", models.DateField()),
                ("from_currency", models.CharField(max_length=8)),
                ("to_currency", models.CharField(max_length=8)),
                ("rate", models.DecimalField(decimal_places=8, max_digits=18)),
            ],
            options={"db_table": "exchange_rates"},
        ),
        migrations.CreateModel(
            name="FinancialEvent",
            fields=[
                ("event_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=64)),
                ("description", models.TextField(blank=True)),
                ("category", models.CharField(max_length=64)),
                ("direction", models.CharField(max_length=16)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("currency", models.CharField(max_length=8)),
                ("event_date", models.DateField()),
                ("settlement_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(max_length=32)),
                ("linked_event_id", models.CharField(blank=True, max_length=64)),
                ("flexibility", models.CharField(blank=True, max_length=64)),
                ("minimum_allowed_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="api.financialprofile")),
            ],
            options={
                "db_table": "financial_events",
                "indexes": [
                    models.Index(fields=["user", "event_date"], name="financial_e_user_id_dfc43f_idx"),
                    models.Index(fields=["category", "direction"], name="financial_e_categor_e3fe65_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PurchaseRequest",
            fields=[
                ("request_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("request_date", models.DateField()),
                ("request_type", models.CharField(max_length=64)),
                ("requested_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("desired_completion_date", models.DateField()),
                ("allows_partial_payment", models.BooleanField(default=False)),
                ("request_text", models.TextField(blank=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("expected_amount_safe_to_pay", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("expected_affordability_status", models.CharField(blank=True, max_length=64)),
                ("expected_recommended_payment_method", models.CharField(blank=True, max_length=64)),
                ("expected_payment_plan", models.TextField(blank=True)),
                ("expected_earliest_date_for_full_payment", models.DateField(blank=True, null=True)),
                ("expected_spending_changes_needed", models.TextField(blank=True)),
                ("expected_decision_explanation", models.TextField(blank=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requests", to="api.financialprofile")),
            ],
            options={
                "db_table": "purchase_requests",
                "indexes": [
                    models.Index(fields=["user", "request_date"], name="purchase_re_user_id_348670_idx"),
                    models.Index(fields=["is_sample"], name="purchase_re_is_samp_c9158c_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PaymentOption",
            fields=[
                ("payment_option_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("payment_method", models.CharField(max_length=64)),
                ("payment_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("number_of_payments", models.PositiveIntegerField()),
                ("first_payment_date", models.DateField()),
                ("payment_frequency_days", models.PositiveIntegerField(blank=True, null=True)),
                ("financing_fee", models.DecimalField(decimal_places=2, max_digits=18)),
                ("total_payable_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_options", to="api.purchaserequest")),
            ],
            options={"db_table": "payment_options"},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("message_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("sent_at", models.DateTimeField()),
                ("source_type", models.CharField(max_length=64)),
                ("message_text", models.TextField()),
                ("related_event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messages", to="api.financialevent")),
                ("request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messages", to="api.purchaserequest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="api.financialprofile")),
            ],
            options={
                "db_table": "messages",
                "indexes": [models.Index(fields=["user", "sent_at"], name="messages_user_id_8b2930_idx")],
            },
        ),
        migrations.CreateModel(
            name="EvidenceImage",
            fields=[
                ("image_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("related_event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="images", to="api.financialevent")),
                ("request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="images", to="api.purchaserequest")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="api.financialprofile")),
            ],
            options={"db_table": "evidence_images"},
        ),
        migrations.CreateModel(
            name="Recommendation",
            fields=[
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="recommendation", serialize=False, to="api.purchaserequest")),
                ("amount_safe_to_pay", models.DecimalField(decimal_places=2, max_digits=18)),
                ("affordability_status", models.CharField(max_length=64)),
                ("recommended_payment_method", models.CharField(max_length=64)),
                ("payment_plan", models.TextField()),
                ("earliest_date_for_full_payment", models.DateField(blank=True, null=True)),
                ("spending_changes_needed", models.TextField(blank=True)),
                ("decision_explanation", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "recommendations"},
        ),
        migrations.AddConstraint(
            model_name="exchangerate",
            constraint=models.UniqueConstraint(fields=("rate_date", "from_currency", "to_currency"), name="uniq_exchange_rate_pair_date"),
        ),
    ]
