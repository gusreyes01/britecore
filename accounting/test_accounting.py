from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from accounting import app, db
from accounting.models import Contact, Policy
from accounting.utils import (
    PolicyAccounting,
    _installment_amounts,
    build_or_refresh_db,
)


@pytest.fixture
def policy_data():
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.drop_all()
        db.create_all()
        agent = Contact("Test Agent", "Agent")
        insured = Contact("Test Insured", "Named Insured")
        db.session.add_all([agent, insured])
        db.session.flush()
        policy = Policy("Test Policy", date(2025, 1, 1), 1200)
        policy.named_insured = insured.id
        policy.agent = agent.id
        db.session.add(policy)
        db.session.commit()
        PolicyAccounting(policy.id).ensure_invoices()
        yield {"policy": policy, "agent": agent, "insured": insured}
        db.session.remove()
        db.drop_all()


def test_installments_preserve_total_for_remainders():
    amounts = _installment_amounts(100, 12)
    assert len(amounts) == 12
    assert sum(amounts) == 100
    assert max(amounts) - min(amounts) == 1
    with pytest.raises(ValueError, match="positive"):
        _installment_amounts(0, 12)


@pytest.mark.parametrize(
    ("schedule", "count", "first_amount"),
    [
        ("Annual", 1, 1200),
        ("Two-Pay", 2, 600),
        ("Quarterly", 4, 300),
        ("Monthly", 12, 100),
    ],
)
def test_supported_billing_schedules(policy_data, schedule, count, first_amount):
    policy = policy_data["policy"]
    policy.billing_schedule = schedule
    accounting = PolicyAccounting(policy.id)
    accounting.make_invoices()
    assert len(policy.invoices) == count
    assert policy.invoices[0].amount_due == first_amount
    assert sum(invoice.amount_due for invoice in policy.invoices) == policy.annual_premium
    assert accounting.return_account_balance(policy.effective_date) == first_amount


def test_balance_accounts_for_payments_by_date(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)
    accounting.make_payment(policy.named_insured, date(2025, 1, 5), 200)
    assert accounting.return_account_balance(date(2025, 1, 4)) == 1200
    assert accounting.return_account_balance(date(2025, 1, 5)) == 1000


def test_payment_rejects_invalid_amount_and_unrelated_contact(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)
    stranger = Contact("Stranger", "Named Insured")
    db.session.add(stranger)
    db.session.commit()

    with pytest.raises(ValueError, match="positive"):
        accounting.make_payment(policy.named_insured, amount=0)
    with pytest.raises(ValueError, match="named insured"):
        accounting.make_payment(stranger.id, amount=10)


def test_unknown_policy_and_schedule_are_rejected(policy_data):
    with pytest.raises(LookupError):
        PolicyAccounting(9999)

    accounting = PolicyAccounting(policy_data["policy"].id)
    with pytest.raises(ValueError, match="unsupported"):
        accounting.change_policy_billing_schedule("Weekly")
    with pytest.raises(ValueError, match="different"):
        accounting.change_policy_billing_schedule("Annual")


def test_future_premium_can_be_rescheduled(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)
    future = date.today() + relativedelta(months=1)
    policy.effective_date = future
    accounting.make_invoices()

    accounting.change_policy_billing_schedule("Monthly", future)

    active = [invoice for invoice in policy.invoices if not invoice.deleted]
    assert len(active) == 12
    assert sum(invoice.amount_due for invoice in active) == 1200


def test_inactive_or_fully_billed_policy_cannot_be_rescheduled(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)
    policy.status = "Canceled"
    with pytest.raises(ValueError, match="active"):
        accounting.change_policy_billing_schedule("Monthly")

    policy.status = "Active"
    with pytest.raises(ValueError, match="future premium"):
        accounting.change_policy_billing_schedule("Monthly", date(2030, 1, 1))


def test_only_agent_can_pay_while_cancellation_is_pending(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)
    pending_date = date(2025, 2, 5)

    assert accounting.evaluate_cancellation_pending_due_to_non_pay(pending_date)
    with pytest.raises(PermissionError):
        accounting.make_payment(policy.named_insured, pending_date, 100)
    assert accounting.make_payment(policy.agent, pending_date, 100).amount_paid == 100


def test_overdue_policy_is_cancelled_with_reason(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)

    assert accounting.evaluate_cancel(date(2025, 2, 16), "Customer request")
    assert policy.status == "Canceled"
    assert policy.cancel_date == date(2025, 2, 16)
    assert policy.cancel_description == "Customer request"


def test_paid_policy_is_not_cancelled(policy_data):
    policy = policy_data["policy"]
    accounting = PolicyAccounting(policy.id)
    accounting.make_payment(policy.agent, date(2025, 1, 5), 1200)

    assert not accounting.evaluate_cancel(date(2025, 2, 16))
    assert policy.status == "Active"


def test_policy_search_api_returns_policy(policy_data):
    policy = policy_data["policy"]
    PolicyAccounting(policy.id)
    response = app.test_client().post(
        "/policies",
        json={"policy_number": policy.policy_number, "date": "2025-01-01"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["policies"][0]["policy_number"] == "Test Policy"
    assert payload["account_balances"][0]["account_balance"] == "Account balance: $1,200.00"


def test_index_and_default_search_date(policy_data):
    assert app.test_client().get("/").status_code == 200
    response = app.test_client().post(
        "/policies",
        json={"policy_number": policy_data["policy"].policy_number},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        (None, 400),
        ({}, 400),
        ({"policy_number": "Test Policy", "date": "not-a-date"}, 400),
        ({"policy_number": "Test Policy", "date": 42}, 400),
        ({"policy_number": "x" * 129}, 400),
        ({"policy_number": "Missing"}, 404),
    ],
)
def test_policy_search_api_validates_input(policy_data, payload, status):
    response = app.test_client().post("/policies", json=payload)
    assert response.status_code == status
    assert response.get_json()["status"] == status


def test_seed_builder_creates_complete_sample(policy_data):
    build_or_refresh_db()
    policies = Policy.query.order_by(Policy.policy_number).all()
    assert [policy.policy_number for policy in policies] == [
        "Policy Four",
        "Policy One",
        "Policy Three",
        "Policy Two",
    ]
    assert all(policy.invoices for policy in policies)
