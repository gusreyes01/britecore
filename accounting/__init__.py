from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    static_folder=str(PROJECT_ROOT / "static"),
    static_url_path="/static",
)
app.config.from_pyfile("config.py")
db = SQLAlchemy(app)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://stackpath.bootstrapcdn.com "
        "https://use.fontawesome.com; "
        "font-src 'self' https://use.fontawesome.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


from accounting import views  # noqa: E402, F401
