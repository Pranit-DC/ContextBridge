"""Create a disposable local test database and run every required repository check."""

import os
import secrets
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from contextbridge.config import Settings


def main() -> int:
    try:
        settings = Settings()
        configured = make_url(settings.database_url.get_secret_value())
    except (ValueError, SQLAlchemyError):
        print("INVALID_CONFIGURATION: check .env; credentials are not displayed.")
        return 1
    if configured.drivername != "postgresql+psycopg":
        print("INVALID_CONFIGURATION: use the project's PostgreSQL psycopg URL format.")
        return 1
    if configured.host not in ("localhost", "127.0.0.1", "::1"):
        print("LOCAL_DATABASE_REQUIRED: this runner only creates test databases on localhost.")
        return 1
    if configured.host == "localhost":
        # Compose publishes IPv4 loopback; avoid Windows IPv6 fallback delays.
        configured = configured.set(host="127.0.0.1")
    database_name = f"contextbridge_om_{secrets.token_hex(6)}_test"
    maintenance = create_engine(
        configured.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    try:
        with maintenance.connect() as connection:
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
    except SQLAlchemyError:
        print("DATABASE_UNAVAILABLE: start local PostgreSQL and allow creation of a test database.")
        return 1
    finally:
        maintenance.dispose()
    # Only the freshly created _test database enters migrations or integration tests.
    test_url = configured.set(database=database_name).render_as_string(hide_password=False)
    environment = dict(os.environ)
    environment.update(
        CONTEXTBRIDGE_DATABASE_URL=test_url,
        CONTEXTBRIDGE_TEST_DATABASE_URL=test_url,
        CONTEXTBRIDGE_API_TOKEN=settings.api_token.get_secret_value(),
    )
    root = Path(__file__).resolve().parents[2]
    report = root / ".pytest_cache" / "formation" / "full-suite.xml"
    print(f"Dedicated database created: {database_name}", flush=True)
    checks = [
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "alembic", "upgrade", "head"],
        ["uv", "run", "alembic", "check"],
        [
            "uv",
            "run",
            "pytest",
            "--cov=contextbridge",
            "--cov-report=term-missing",
            f"--junitxml={report}",
        ],
    ]
    for command in checks:
        print(f"Running {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=root, env=environment, check=False)
        if result.returncode:
            return result.returncode
    suites = ElementTree.parse(report).getroot().iter("testsuite")
    if any(int(suite.get("skipped", "0")) for suite in suites):
        print("INCOMPLETE_CHECKS: skipped tests are not accepted by this runner.")
        return 1
    print("All required checks passed with zero skipped tests.")
    print(f"The disposable database {database_name} is retained for inspection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
