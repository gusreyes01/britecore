# Policy Accounting Sample

A small Flask application for exploring insurance-policy invoices, payments,
billing schedules, balances, and cancellation rules. It began as a BriteCore
engineering exercise and has been modernized for Python 3.12 and maintained
Flask/SQLAlchemy releases.

This repository is educational software with synthetic seed data. It does
not include authentication and must not be used for real policy records
without a separate security design.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --requirement requirements-dev.txt
```

Initialize the sample database:

```bash
flask --app accounting shell
>>> from accounting.utils import build_or_refresh_db
>>> build_or_refresh_db()
```

Run the application on localhost:

```bash
python runserver.py
```

Open <http://127.0.0.1:5000> and search for `Policy One` through
`Policy Four`. Set `DATABASE_URL` to use a database other than the default
project-local SQLite file.

## Quality checks

```bash
ruff check .
pytest
pip check
```

The pytest suite covers billing schedules, exact installment totals, dated
balances, payer authorization, cancellation behavior, and API validation.
Coverage must remain at or above 90%. GitHub Actions runs all checks on every
push and pull request, and Dependabot monitors Python and Actions dependencies.

## Architecture

- `accounting/models.py` defines policies, contacts, invoices, and payments.
- `accounting/utils.py` contains the tested accounting domain service and
  deterministic seed-data helpers.
- `accounting/views.py` validates the read-only policy-search API.
- `accounting/templates/` and `static/` provide the sample search interface.
- `runserver.py` starts a development server bound to localhost by default.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before
making changes.

## License

Copyright 2016 Zendesk, Inc. Licensed under Apache License 2.0; see
[LICENSE.md](LICENSE.md).
