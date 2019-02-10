# You will probably need more methods from flask but this one is a good start.

import json
import locale
locale.setlocale( locale.LC_ALL, '' )

from flask import render_template, jsonify, request
# Import our models
from models import Policy

# Import things from Flask that we need.
from accounting import app
# Routing for the server.
from accounting.utils import PolicyAccounting


@app.route("/")
def index():
    # You will need to serve something up here.
    return render_template('index.html')


@app.route('/policies', methods=['GET', 'POST'])
def policies():
    invoices_dict = []
    policies_dict = []
    policy = None
    date = None
    account_balance = 0

    if request.data:
        data = json.loads(request.data)
        if ('date' in data):
            date = data['date']

        print(data)
        if ('policy_number' in data):
            if data['policy_number']:
                try:
                    policy = Policy.query.filter_by(policy_number=data['policy_number']).one()
                    # Find Policy Accouning object & return account balance based on the provided date.
                    pa = PolicyAccounting(policy.id)
                    account_balance = pa.return_account_balance(date)
                except:
                    return jsonify(status=404, message=['Policy not found. \n Please try a different policy number.'])

    if policy:
        policies_dict = [dict(policy_number=policy.policy_number, effective_date=str(policy.effective_date))]
        invoices_dict = policy.invoices_dict

        return jsonify(status=200, message=['Policy found'], policies=policies_dict, invoices=invoices_dict,
                       account_balances=[{'account_balance': 'Account balance: {}'.format(
                           locale.currency(account_balance, grouping=True))}])
    else:
        return jsonify(status=404, message=['Policy not found. \n Please try a different policy number.'])

