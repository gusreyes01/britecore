# Contributing

Create a focused branch, install `requirements-dev.txt`, and add tests for
behavior changes. Before opening a pull request, run:

```bash
ruff check .
pytest
pip check
```

Never commit a populated SQLite database, credentials, or customer records.
