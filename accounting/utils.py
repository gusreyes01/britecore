import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from accounting import db
from accounting.models import Contact, Invoice, Payment, Policy

BILLING_SCHEDULES = {
    "Annual": (1, 12),
    "Two-Pay": (2, 6),
    "Quarterly": (4, 3),
    "Monthly": (12, 1),
}
audit_logger = logging.getLogger("accounting.audit")


def _installment_amounts(total, count):
    if total <= 0:
        raise ValueError("premium must be positive")
    base, remainder = divmod(total, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


class PolicyAccounting:
    """Accounting operations for a single insurance policy."""

    def __init__(self, policy_id):
        self.policy = db.session.get(Policy, policy_id)
        if self.policy is None:
            raise LookupError(f"policy {policy_id} was not found")

    def ensure_invoices(self):
        """Create an initial invoice schedule explicitly when one does not exist."""
        if not self.policy.invoices:
            self.make_invoices()
        return self.policy.invoices

    def return_account_balance(self, date_cursor=None):
        cursor = date_cursor or date.today()
        invoiced = sum(
            invoice.amount_due
            for invoice in self.policy.invoices
            if not invoice.deleted and invoice.bill_date <= cursor
        )
        paid = sum(
            payment.amount_paid
            for payment in self.policy.payments
            if payment.transaction_date <= cursor
        )
        return invoiced - paid

    def change_policy_billing_schedule(self, new_schedule, effective_date=None):
        if new_schedule not in BILLING_SCHEDULES:
            raise ValueError("unsupported billing schedule")
        if self.policy.status != "Active":
            raise ValueError("only active policies can change schedule")
        if self.policy.billing_schedule == new_schedule:
            raise ValueError("new billing schedule must be different")

        cursor = effective_date or date.today()
        future_invoices = [
            invoice
            for invoice in self.policy.invoices
            if invoice.bill_date >= cursor and not invoice.deleted
        ]
        remaining_premium = sum(invoice.amount_due for invoice in future_invoices)
        if remaining_premium <= 0:
            raise ValueError("policy has no future premium to reschedule")

        for invoice in future_invoices:
                invoice.deleted = True

        self.policy.billing_schedule = new_schedule
        self.make_invoices(
            replace=False,
            start_date=cursor,
            premium=remaining_premium,
        )
        db.session.commit()
        audit_logger.info(
            "billing_schedule_changed policy_id=%s schedule=%s effective_date=%s",
            self.policy.id,
            new_schedule,
            cursor.isoformat(),
        )

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        cursor = date_cursor or date.today()
        if amount <= 0:
            raise ValueError("payment amount must be positive")

        payer_id = contact_id or self.policy.named_insured
        contact = db.session.get(Contact, payer_id)
        if contact is None or payer_id not in {self.policy.named_insured, self.policy.agent}:
            raise ValueError("payer must be the named insured or policy agent")
        if self.evaluate_cancellation_pending_due_to_non_pay(cursor) and contact.role != "Agent":
            raise PermissionError("only the policy agent may pay during cancellation pending")

        payment = Payment(self.policy.id, payer_id, amount, cursor)
        db.session.add(payment)
        db.session.commit()
        audit_logger.info(
            "payment_created policy_id=%s contact_id=%s amount=%s date=%s",
            self.policy.id,
            payer_id,
            amount,
            cursor.isoformat(),
        )
        return payment

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        cursor = date_cursor or date.today()
        return any(
            invoice.due_date < cursor <= invoice.cancel_date
            and self.return_account_balance(invoice.due_date) > 0
            for invoice in self.policy.invoices
            if not invoice.deleted
        )

    def evaluate_cancel(self, date_cursor=None, cancel_description=None):
        cursor = date_cursor or date.today()
        should_cancel = any(
            invoice.cancel_date <= cursor
            and self.return_account_balance(invoice.cancel_date) > 0
            for invoice in self.policy.invoices
            if not invoice.deleted
        )
        if not should_cancel:
            return False

        self.policy.status = "Canceled"
        self.policy.cancel_date = cursor
        self.policy.cancel_description = (
            cancel_description or "Canceled due to non-payment."
        )[:128]
        db.session.commit()
        audit_logger.info(
            "policy_cancelled policy_id=%s date=%s reason=%s",
            self.policy.id,
            cursor.isoformat(),
            self.policy.cancel_description,
        )
        return True

    def make_invoices(self, replace=True, start_date=None, premium=None):
        try:
            count, month_step = BILLING_SCHEDULES[self.policy.billing_schedule]
        except KeyError as exc:
            raise ValueError("unsupported billing schedule") from exc

        if replace:
            for invoice in list(self.policy.invoices):
                db.session.delete(invoice)
            db.session.flush()

        effective = start_date or self.policy.effective_date
        amounts = _installment_amounts(
            premium if premium is not None else self.policy.annual_premium,
            count,
        )
        for index, amount in enumerate(amounts):
            bill_date = effective + relativedelta(months=index * month_step)
            db.session.add(
                Invoice(
                    self.policy.id,
                    bill_date,
                    bill_date + relativedelta(months=1),
                    bill_date + relativedelta(months=1, days=14),
                    amount,
                )
            )
        db.session.commit()


def build_or_refresh_db():
    db.session.remove()
    db.drop_all()
    db.create_all()
    insert_data()


def insert_data():
    contacts = [
        Contact("John Doe", "Agent"),
        Contact("John Doe", "Named Insured"),
        Contact("Bob Smith", "Agent"),
        Contact("Anna White", "Named Insured"),
        Contact("Joe Lee", "Agent"),
        Contact("Ryan Bucket", "Named Insured"),
    ]
    db.session.add_all(contacts)
    db.session.flush()

    policies = [
        _seed_policy("Policy One", date(2015, 1, 1), 365, "Annual", contacts[1], contacts[2]),
        _seed_policy(
            "Policy Two", date(2015, 2, 1), 1600, "Quarterly", contacts[3], contacts[4]
        ),
        _seed_policy(
            "Policy Three", date(2015, 1, 1), 1200, "Monthly", contacts[5], contacts[0]
        ),
        _seed_policy(
            "Policy Four", date(2015, 2, 1), 500, "Two-Pay", contacts[5], contacts[0]
        ),
    ]
    db.session.add_all(policies)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id).ensure_invoices()
    db.session.add(Payment(policies[1].id, contacts[3].id, 400, date(2015, 2, 1)))
    db.session.commit()


def _seed_policy(number, effective, premium, schedule, insured, agent):
    policy = Policy(number, effective, premium)
    policy.billing_schedule = schedule
    policy.named_insured = insured.id
    policy.agent = agent.id
    return policy
