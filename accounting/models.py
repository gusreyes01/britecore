from accounting import db


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    policy_number = db.Column(db.String(128), unique=True, nullable=False, index=True)
    effective_date = db.Column(db.Date, nullable=False)
    status = db.Column(
        db.Enum("Active", "Canceled", "Expired", name="policy_status"),
        default="Active",
        nullable=False,
    )
    billing_schedule = db.Column(
        db.Enum("Annual", "Two-Pay", "Quarterly", "Monthly", name="billing_schedule"),
        default="Annual",
        nullable=False,
    )
    annual_premium = db.Column(db.Integer, nullable=False)
    named_insured = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    agent = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    cancel_description = db.Column(db.String(128))
    cancel_date = db.Column(db.Date)

    invoices = db.relationship(
        "Invoice",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="Invoice.bill_date",
    )
    payments = db.relationship(
        "Payment",
        back_populates="policy",
        cascade="all, delete-orphan",
    )

    def __init__(self, policy_number, effective_date, annual_premium):
        self.policy_number = policy_number
        self.effective_date = effective_date
        self.annual_premium = annual_premium

    @property
    def invoices_dict(self):
        return [
            {
                "amount_due": invoice.amount_due,
                "bill_date": invoice.bill_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
            }
            for invoice in self.invoices
            if not invoice.deleted
        ]


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    role = db.Column(
        db.Enum("Named Insured", "Agent", name="contact_role"),
        nullable=False,
    )

    def __init__(self, name, role):
        self.name = name
        self.role = role


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False, index=True)
    bill_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    cancel_date = db.Column(db.Date, nullable=False)
    amount_due = db.Column(db.Integer, nullable=False)
    deleted = db.Column(db.Boolean, default=False, server_default="0", nullable=False)

    policy = db.relationship("Policy", back_populates="invoices")

    def __init__(self, policy_id, bill_date, due_date, cancel_date, amount_due):
        self.policy_id = policy_id
        self.bill_date = bill_date
        self.due_date = due_date
        self.cancel_date = cancel_date
        self.amount_due = amount_due


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    amount_paid = db.Column(db.Integer, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)

    policy = db.relationship("Policy", back_populates="payments")

    def __init__(self, policy_id, contact_id, amount_paid, transaction_date):
        self.policy_id = policy_id
        self.contact_id = contact_id
        self.amount_paid = amount_paid
        self.transaction_date = transaction_date
