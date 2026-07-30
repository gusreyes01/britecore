from datetime import date

from flask import jsonify, render_template, request
from sqlalchemy.exc import MultipleResultsFound

from accounting import app
from accounting.models import Policy
from accounting.utils import PolicyAccounting


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/policies")
def policies():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("A JSON request body is required.", 400)

    policy_number = payload.get("policy_number")
    if not isinstance(policy_number, str) or not policy_number.strip():
        return _error("Policy number is required.", 400)
    if len(policy_number) > 128:
        return _error("Policy number is too long.", 400)

    try:
        cursor = _parse_date(payload.get("date"))
    except ValueError:
        return _error("Date must use YYYY-MM-DD format.", 400)

    try:
        policy = Policy.query.filter_by(policy_number=policy_number.strip()).one_or_none()
    except MultipleResultsFound:
        app.logger.exception("duplicate policy number")
        return _error("Policy data is inconsistent.", 500)
    if policy is None:
        return _error("Policy not found.", 404)

    accounting = PolicyAccounting(policy.id)
    accounting.ensure_invoices()
    account_balance = accounting.return_account_balance(cursor)
    return jsonify(
        status=200,
        message=["Policy found"],
        policies=[
            {
                "policy_number": policy.policy_number,
                "effective_date": policy.effective_date.isoformat(),
            }
        ],
        invoices=policy.invoices_dict,
        account_balances=[{"account_balance": f"Account balance: ${account_balance:,.2f}"}],
    )


def _parse_date(value):
    if value in (None, ""):
        return date.today()
    if not isinstance(value, str):
        raise ValueError
    return date.fromisoformat(value)


def _error(message, status):
    return jsonify(status=status, message=[message]), status
