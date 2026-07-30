"""Launch an optional IPython shell with the application context loaded."""

from accounting import app, db
from accounting.models import Contact, Invoice, Payment, Policy
from accounting.utils import PolicyAccounting, build_or_refresh_db


def main():
    try:
        from IPython import embed
    except ImportError as exc:
        raise SystemExit("Install IPython to use shell.py") from exc

    with app.app_context():
        embed(
            user_ns={
                "app": app,
                "db": db,
                "Contact": Contact,
                "Invoice": Invoice,
                "Payment": Payment,
                "Policy": Policy,
                "PolicyAccounting": PolicyAccounting,
                "build_or_refresh_db": build_or_refresh_db,
            }
        )


if __name__ == "__main__":
    main()
