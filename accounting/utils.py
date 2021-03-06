#!/user/bin/env python2.7

from datetime import date, datetime

from dateutil.relativedelta import relativedelta
from models import Contact, Invoice, Payment, Policy

from accounting import db

"""
#######################################################
This is the base code for the engineer project.
#######################################################
"""


class PolicyAccounting(object):
    """
     Each policy has its own instance of accounting.
    """

    def __init__(self, policy_id):
        self.policy = Policy.query.filter_by(id=policy_id).one()

        if not self.policy.invoices:
            self.make_invoices()

    def return_account_balance(self, date_cursor=None):
        """
         Returns the policy account balance by
         adding all the invoices amounts
         and substracting the amount paid.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        invoices = Invoice.query.filter_by(policy_id=self.policy.id, deleted=False) \
            .filter(Invoice.bill_date <= date_cursor) \
            .order_by(Invoice.bill_date) \
            .all()

        due_now = 0
        for invoice in invoices:
            due_now += invoice.amount_due

        payments = Payment.query.filter_by(policy_id=self.policy.id) \
            .filter(Payment.transaction_date <= date_cursor) \
            .all()
        for payment in payments:
            due_now -= payment.amount_paid

        return due_now

    def change_policy_billing_schedule(self, new_schedule):
        """
         Allows a ongoing policy to change it's billing schedule.
         This method will set all existing invoices as deleted and create new ones.
        """

        if self.policy.billing_schedule == new_schedule:
            print
            'Current and new billing schedules are the same. Please choose a different schedule.'
            return None

        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .order_by(Invoice.bill_date) \
            .all()

        if self.return_account_balance() > 0 and self.policy.status == 'Active':
            for invoice in invoices:
                invoice.deleted = True
            self.policy.billing_schedule = new_schedule
            print(self.return_account_balance())
            self.policy.annual_premium = self.return_account_balance()
            self.make_invoices(True)
            db.session.commit()

        else:
            print
            'This policy is inactive or its balance is 0 so its billing schedule cannot be modified.'

    def make_policy(self, policy_number, effective_date, annual_premium):
        """
        Create a new policy method.
        """

        policy = Policy(policy_number,
                        effective_date,
                        annual_premium)
        db.session.add(policy)
        db.session.commit()

        return policy

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        """
        Create a new payment method,
        this method will evaluate each policy
        if it's cancellation pending only agents
        will be able to make payments.
        """

        if not date_cursor:
            date_cursor = datetime.now().date()

        if self.evaluate_cancellation_pending_due_to_non_pay(date_cursor):
            contact = Contact.query.get(contact_id)
            if contact.role != 'Agent':
                print
                'You need to be an agent to pay this policy.'
                return False

        else:
            if not contact_id:
                try:
                    contact_id = self.policy.named_insured
                except:
                    pass

        payment = Payment(self.policy.id,
                          contact_id,
                          amount,
                          date_cursor)
        db.session.add(payment)
        db.session.commit()

        return payment

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        """
         If this function returns true, an invoice
         on a policy has passed the due date without
         being paid in full. However, it has not necessarily
         made it to the cancel_date yet.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .filter(Invoice.cancel_date <= date_cursor) \
            .order_by(Invoice.bill_date) \
            .all()

        for invoice in invoices:
            if not self.return_account_balance(invoice.due_date):
                continue
            else:
                return True

        return False

    def evaluate_cancel(self, date_cursor=None, cancel_description=None):
        """
         This function lets the user know an invoice
         on a policy has passed the cancel date without
         being paid in full & the policy should be cancelled.
        """

        if not date_cursor:
            date_cursor = datetime.now().date()

        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .filter(Invoice.cancel_date <= date_cursor) \
            .order_by(Invoice.bill_date) \
            .all()

        for invoice in invoices:
            if not self.return_account_balance(invoice.cancel_date):
                continue
            else:
                self.policy.status = 'Canceled'
                self.policy.cancel_date = date_cursor
                self.policy.cancel_description = cancel_description or 'Canceled due to non-payment.'
                db.session.commit()
                print
                "THIS POLICY HAS BEING CANCELED"
                break
        else:
            print
            "THIS POLICY SHOULD NOT CANCEL"

    def make_invoices(self, billing_schedule_change=False):
        """
        Create new invoices method,
        this function will be called when initializing
        a new PolicyAccounting instance.

        """

        for invoice in self.policy.invoices:
            if not billing_schedule_change:
                invoice.delete()

        billing_schedules = {'Annual': None, 'Two-Pay': 2, 'Quarterly': 4, 'Monthly': 12}

        invoices = []
        first_invoice = Invoice(self.policy.id,
                                self.policy.effective_date,  # bill_date
                                self.policy.effective_date + relativedelta(months=1),  # due
                                self.policy.effective_date + relativedelta(months=1, days=14),  # cancel
                                self.policy.annual_premium)
        invoices.append(first_invoice)

        if self.policy.billing_schedule == "Annual":
            pass
        elif self.policy.billing_schedule == "Two-Pay":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i * 6
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Quarterly":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i * 3
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Monthly":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i * 1
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        else:
            print
            "You have chosen a bad billing schedule."

        for invoice in invoices:
            db.session.add(invoice)
        db.session.commit()


################################
# The functions below are for the db and 
# shouldn't need to be edited.
################################
def build_or_refresh_db():
    db.drop_all()
    db.create_all()
    insert_data()
    print
    "DB Ready!"


def insert_data():
    # Contacts
    contacts = []
    john_doe_agent = Contact('John Doe', 'Agent')
    contacts.append(john_doe_agent)
    john_doe_insured = Contact('John Doe', 'Named Insured')
    contacts.append(john_doe_insured)
    bob_smith = Contact('Bob Smith', 'Agent')
    contacts.append(bob_smith)
    anna_white = Contact('Anna White', 'Named Insured')
    contacts.append(anna_white)
    joe_lee = Contact('Joe Lee', 'Agent')
    contacts.append(joe_lee)
    ryan_bucket = Contact('Ryan Bucket', 'Named Insured')
    contacts.append(ryan_bucket)

    for contact in contacts:
        db.session.add(contact)
    db.session.commit()

    policies = []
    p1 = Policy('Policy One', date(2015, 1, 1), 365)
    p1.billing_schedule = 'Annual'
    p1.named_insured = john_doe_insured.id
    p1.agent = bob_smith.id
    policies.append(p1)

    p2 = Policy('Policy Two', date(2015, 2, 1), 1600)
    p2.billing_schedule = 'Quarterly'
    p2.named_insured = anna_white.id
    p2.agent = joe_lee.id
    policies.append(p2)

    p3 = Policy('Policy Three', date(2015, 1, 1), 1200)
    p3.billing_schedule = 'Monthly'
    p3.named_insured = ryan_bucket.id
    p3.agent = john_doe_agent.id
    policies.append(p3)

    p4 = Policy('Policy Four', date(2015, 2, 1), 500)
    p4.billing_schedule = 'Two-Pay'
    p4.named_insured = ryan_bucket.id
    p4.agent = john_doe_agent.id
    policies.append(p4)

    for policy in policies:
        db.session.add(policy)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id)

    payment_for_p2 = Payment(p2.id, anna_white.id, 400, date(2015, 2, 1))
    db.session.add(payment_for_p2)
    db.session.commit()
