"""Build docs/How_To_Run.pdf: step-by-step instructions to run the project locally.

Usage:  python scripts/build_run_guide.py

Each command in the guide was run during the build unless it is marked as not verified.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "How_To_Run.pdf"

_styles = getSampleStyleSheet()
TITLE = ParagraphStyle("T", parent=_styles["Title"], fontSize=20, spaceAfter=8)
H1 = ParagraphStyle("H1", parent=_styles["Heading1"], fontSize=14, spaceBefore=12, spaceAfter=5)
H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=11, spaceBefore=7, spaceAfter=3)
BODY = ParagraphStyle("B", parent=_styles["BodyText"], fontSize=9.5, leading=13)
BULLET = ParagraphStyle("BL", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CODE = ParagraphStyle("C", parent=BODY, fontName="Courier", fontSize=7.5, leading=9.5)
NOTE = ParagraphStyle("N", parent=BODY, backColor=colors.HexColor("#FFF6E0"), borderPadding=5, spaceBefore=4)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.5, leading=11)


def p(text: str) -> Paragraph:
    return Paragraph(escape(text), BODY)


def h1(text: str) -> Paragraph:
    return Paragraph(escape(text), H1)


def h2(text: str) -> Paragraph:
    return Paragraph(escape(text), H2)


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(escape(item), BULLET, bulletText="•") for item in items]


def code(block: str) -> Preformatted:
    return Preformatted(block.strip("\n"), CODE)


def note(text: str) -> Paragraph:
    return Paragraph(escape(text), NOTE)


def table(rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(escape(cell), CELL) for cell in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA5B1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def step(number: int, title: str, body: list[Flowable]) -> list[Flowable]:
    return [h2(f"Step {number}. {title}"), *body]


def story() -> list[Flowable]:
    s: list[Flowable] = []
    s.append(Paragraph("How to Run the Merchant Payment Analytics Assistant", TITLE))
    s.append(
        p(
            "Step-by-step instructions for running the API locally with a PostgreSQL database. "
            "All data is synthetic. Jev and the LLM are optional for starting the system, but "
            "analytics answers need a TypeSafe key (see the Jev Testing Guide)."
        )
    )

    s.append(h1("Before you start"))
    s.append(
        table(
            [
                ["You need", "Notes"],
                ["Python 3.11 or newer", "Check with: python3 --version"],
                ["PostgreSQL 16", "Running locally, with the psql and createdb command-line tools"],
                ["Node.js 18.18 or newer (optional)", "Only for the web interface in Step 11"],
                [
                    "bash",
                    "macOS and Linux have it. On Windows, use WSL or Git Bash, because the "
                    "database bootstrap script is a bash script.",
                ],
                ["The project folder", "The folder containing pyproject.toml"],
                ["A TypeSafe key (optional now)", "Needed only for live Jev classification"],
                ["An Anthropic key (optional)", "Without it the assistant does not call a model"],
            ],
            [55 * mm, 123 * mm],
        )
    )
    s.append(Spacer(1, 4))
    s.append(
        note(
            "Run every command from the project folder unless a step says otherwise. Commands use "
            "$ at the start of a line only to mark them; do not type the $."
        )
    )

    s += step(
        1,
        "Open a terminal in the project folder and create a virtual environment",
        [
            p("Create the environment once. It keeps the project's packages separate from your system."),
            code("""
cd merchant-payment-analytics
python3 -m venv .venv
source .venv/bin/activate        # Windows (WSL/Git Bash): source .venv/bin/activate
"""),
            p(
                "Your prompt should now start with (.venv). Every later step assumes this environment is "
                "active. If you open a new terminal, run the activate command again."
            ),
        ],
    )

    s += step(
        2,
        "Install the project and its development tools",
        [
            p(
                "This installs the application, the test tools, ruff, mypy and reportlab (used only to "
                "build the PDF guides). It takes a minute or two."
            ),
            code('pip install -e ".[dev]"'),
            p("Check that the main packages import:"),
            code("python -c \"import app.main, typesafe_sdk; print('ok')\""),
            p("Expected output: ok"),
        ],
    )

    s += step(
        3,
        "Create your local configuration file",
        [
            p("Copy the example file. The application reads .env from the project folder automatically."),
            code("cp .env.example .env"),
            p("Open .env in a text editor and make these changes:"),
            table(
                [
                    ["Setting", "What to do"],
                    [
                        "DATABASE_URL",
                        "Keep the merchant_app user. Replace change-me-app with the password "
                        "you choose for APP_DB_PASSWORD in Step 5.",
                    ],
                    [
                        "ANALYTICS_DATABASE_URL",
                        "Keep the analytics_ro user. Replace change-me-ro with the "
                        "password you choose for ANALYTICS_RO_PASSWORD.",
                    ],
                    [
                        "MIGRATION_DATABASE_URL",
                        "Keep the merchant_owner user. Replace change-me-owner with "
                        "the password you choose for OWNER_DB_PASSWORD.",
                    ],
                    [
                        "JWT_SECRET",
                        "Set a random value of at least 32 characters. Generate one with: "
                        'python -c "import secrets;print(secrets.token_urlsafe(48))"',
                    ],
                    [
                        "TYPESAFE_API_KEY",
                        "Leave empty until you have a key. Analytics answers stay "
                        "temporarily unavailable without it.",
                    ],
                    ["ANTHROPIC_API_KEY", "Leave empty unless you have a key."],
                ],
                [50 * mm, 128 * mm],
            ),
            Spacer(1, 4),
            note(
                "Never commit .env to version control. It is excluded by .gitignore. The values in "
                ".env.example are placeholders and are not real credentials."
            ),
        ],
    )

    s += step(
        4,
        "Start PostgreSQL and create the database",
        [
            p(
                "If PostgreSQL is not running, start it with your usual method (for example, the "
                "PostgreSQL app on macOS, or sudo service postgresql start on Linux)."
            ),
            p(
                "Find the superuser name your PostgreSQL installation uses. Homebrew on macOS creates a "
                "superuser named after your macOS account, not postgres. Linux packages usually use "
                "postgres. Set the variable once per terminal:"
            ),
            code("""
# macOS (Homebrew): your macOS username
export PG_SUPERUSER="$(whoami)"
# Linux (apt, dnf): uncomment the next line instead
# export PG_SUPERUSER=postgres
"""),
            p("Check that the superuser exists (it lists your database role):"),
            code('psql -h localhost -U "$PG_SUPERUSER" -d postgres -c "\\du"'),
            p("Create an empty database named merchant_analytics:"),
            code('createdb -h localhost -U "$PG_SUPERUSER" merchant_analytics'),
            p(
                "If you are asked for a password, enter the password of that superuser. Homebrew installs "
                "usually have no password for it. If the database already exists, you will see an error; "
                "that is harmless."
            ),
        ],
    )

    s += step(
        5,
        "Choose the database passwords and export them",
        [
            p(
                "The bootstrap script in Step 6 creates three database roles. It needs their passwords "
                "as environment variables. Choose three passwords and use the same values in .env (Step "
                "3). The passwords below are placeholders: pick your own."
            ),
            code("""
export OWNER_DB_PASSWORD=<owner-password>
export APP_DB_PASSWORD=<app-password>
export ANALYTICS_RO_PASSWORD=<ro-password>
export DB_HOST=localhost:5432/merchant_analytics
export OWNER_DATABASE_URL="postgresql+psycopg://merchant_owner:${OWNER_DB_PASSWORD}@${DB_HOST}"
export ADMIN_DATABASE_URL=postgresql://${PG_SUPERUSER}@${DB_HOST}
"""),
            note(
                "Environment variables set this way last only for this terminal session. Repeat this "
                "step in any new terminal. The bootstrap script does not read .env."
            ),
            p(
                "Set the same passwords in .env: DATABASE_URL uses <app-password>, "
                "ANALYTICS_DATABASE_URL uses <ro-password>, and MIGRATION_DATABASE_URL uses "
                "<owner-password>. If they do not match, the API cannot connect."
            ),
        ],
    )

    s += step(
        6,
        "Create the tables, roles and synthetic demo data",
        [
            p(
                "Run the bootstrap script. It applies the database migrations, creates the three roles, "
                "and loads the synthetic demo data. It is safe to run again."
            ),
            code("bash docker/migrate.sh"),
            p("Expected output ends with lines like these (the numbers are the demo dataset):"),
            code("""
[migrate] alembic upgrade head
[migrate] database roles
[migrate] seed synthetic demo data (owner role)
rows attempted: {"chargebacks": 90, "merchants": 3, "settlements": 706,
                 "transactions": 8200, ...}
[migrate] done
"""),
            p(
                "Running it a second time inserts nothing new and still ends with [migrate] done. This "
                "was verified on a local PostgreSQL 16 server."
            ),
        ],
    )

    s += step(
        7,
        "Start the API",
        [
            p("Start the web server. Leave this terminal open while you use the API."),
            code("uvicorn app.main:app --reload"),
            p(
                "Expected output includes a line such as: Uvicorn running on http://127.0.0.1:8000. "
                "--reload restarts the server when you change code. Stop the server with Ctrl+C."
            ),
        ],
    )

    s += step(
        8,
        "Check that the API is running",
        [
            p("In a second terminal (activate the environment there too), request the health endpoint:"),
            code("curl -s localhost:8000/health"),
            p("Expected output:"),
            code('{"status":"ok","database":"ok","configured":{"auth":true,"jev":false,"llm":false}}'),
            p(
                "database must say ok. jev and llm say false until you add their keys; that is expected. "
                "auth says true because JWT_SECRET is set."
            ),
            note(
                "Interactive API documentation is available at http://localhost:8000/docs in development "
                "mode, if the page loads in your browser."
            ),
        ],
    )

    s += step(
        9,
        "Get a development token",
        [
            p(
                "Requests to /chat need a token. The script creates one for a demo user from data/users.csv. "
                "The role and merchant come from the database, not from the script."
            ),
            code("python scripts/issue_dev_token.py demo-analyst-001 --minutes 30"),
            p("Copy the long token it prints. Store it in a shell variable in the second terminal:"),
            code('export TOKEN="<paste the token here>"'),
            p("Tokens expire after the number of minutes you set. Issue a new one when that happens."),
        ],
    )

    s += step(
        10,
        "Ask a question",
        [
            p("Send a question to /chat:"),
            code("""
curl -s -X POST localhost:8000/chat \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "content-type: application/json" \\
  -d '{"message": "What was my transaction volume last month?"}'
"""),
            p("What you see depends on your configuration:"),
            table(
                [
                    ["Configuration", "Expected status in the response"],
                    [
                        "No TYPESAFE_API_KEY (default)",
                        "temporarily_unavailable. This is correct: the system refuses to answer without Jev.",
                    ],
                    [
                        "Valid TYPESAFE_API_KEY and model",
                        "answered (for supported questions), with figures, filters and the metric definition",
                    ],
                    ["Question with no token", "HTTP 401, no body data. Use Step 9 to get a token."],
                ],
                [60 * mm, 118 * mm],
            ),
            Spacer(1, 4),
            p(
                "Other statuses you may see: clarification_required (the question is unclear), "
                "unsupported (for example, a request to move money), and blocked (for example, a "
                "request for another merchant's data or a prompt-injection attempt)."
            ),
        ],
    )

    s += step(
        11,
        "Optional: start the web interface (needs Node.js 18.18 or newer)",
        [
            p(
                "The frontend is a Next.js dashboard in the frontend folder. It has two modes. Mock mode "
                "shows fictional demo data and needs nothing else running. Live mode calls the API from "
                "Step 7 through a proxy. Open a third terminal for this step."
            ),
            p("Install the frontend packages once:"),
            code("""
cd frontend
npm install
cp .env.example .env.local
"""),
            p("Mock mode (the default in .env.local). Start it and open http://localhost:3000:"),
            code("npm run dev"),
            p(
                "A banner on every page says the data is fictional. Stop the server with Ctrl+C."
            ),
            p(
                "Live mode uses your running API. Edit frontend/.env.local so it contains these two lines, "
                "then restart npm run dev:"
            ),
            code("""
NEXT_PUBLIC_DATA_MODE=live
BACKEND_URL=http://127.0.0.1:8000
"""),
            p(
                "Open Settings in the browser and paste the token from Step 9 into the token box. The token "
                "is kept only in that browser tab and is removed when you sign out or close the tab. There "
                "is no login page, because the API has no login endpoint."
            ),
            note(
                "In live mode, the Overview page waits for the Refresh button. Each refresh asks the "
                "assistant six questions, so it can use Jev and the LLM. The frontend has no database or "
                "Jev access of its own. See frontend/README.md for the full list of gaps in the API."
            ),
        ],
    )

    s += step(
        12,
        "Run the tests",
        [
            p(
                "Run the tests without a database first. Integration tests are skipped in this mode, "
                "and the summary line will show the skipped count:"
            ),
            code("python -m pytest tests -q"),
            p(
                "Expected: no failures. Without a database, the integration tests are skipped (58 skipped "
                "on the reference run); the passed count grows as tests are added."
            ),
            p(
                "For the full run, create a separate test database (its name must contain the word "
                "test; the tests drop and rebuild it, so never use your demo database):"
            ),
            code("""
createdb -h localhost -U "$PG_SUPERUSER" merchant_test
export TEST_ADMIN_DATABASE_URL=postgresql://${PG_SUPERUSER}@localhost:5432/merchant_test
python -m pytest tests -q
"""),
            p("Expected result: no failures and no skipped integration tests. Also run the code checks:"),
            code("""
ruff check app scripts tests alembic
mypy app scripts
"""),
        ],
    )

    s += step(
        13,
        "Validate the Jev evaluation dataset (no network needed)",
        [
            p("This checks that the 70 labelled cases are well formed. It does not call Jev:"),
            code("python scripts/run_jev_eval.py"),
            p("Expected output starts with: dataset OK: 70 cases"),
        ],
    )

    s += step(
        14,
        "Run the live Jev evaluation (requires a TypeSafe key)",
        [
            p(
                "Only do this when you have a TypeSafe key. It sends each case to Jev, which can take "
                "several minutes and uses your key's quota:"
            ),
            code("""
export TYPESAFE_API_KEY=<your-key>
python scripts/run_jev_eval.py --live --report docs/jev_eval_report.md
"""),
            p(
                "Without the key, the script stops with a message and writes no report. A report file "
                "means a real run happened. Read the metrics as described in the Jev Testing Guide "
                "before you change the thresholds in .env. The thresholds are provisional until then."
            ),
        ],
    )

    s += step(
        15,
        "Stop the server and reset when you are finished",
        [
            p(
                "Stop uvicorn (and the frontend, if running) with Ctrl+C in its terminal. Leave PostgreSQL "
                "running if you will use it again."
            ),
            p(
                "To remove the demo database and start from scratch, drop it and repeat Steps 4 to 6. "
                "The database roles are created only when missing, so their existing passwords stay "
                "the same. To change a role password, drop the role in psql first, or use a new database "
                "setup with new passwords."
            ),
            code('dropdb -h localhost -U "$PG_SUPERUSER" merchant_analytics'),
        ],
    )

    s += [
        h1("Optional: run with Docker Compose"),
        note(
            "Not verified. The Docker daemon was not available when these files were written, so the "
            "compose stack has not been run. The migration script it calls was tested on its own."
        ),
    ]
    s.append(p("Requires Docker with Compose v2. Compose reads your .env file for its settings:"))
    s.append(
        code("""
# .env must also set POSTGRES_PASSWORD (for the database superuser)
docker compose up --build
curl -s localhost:8000/health
""")
    )
    s.append(
        p(
            "Compose starts PostgreSQL 16, runs the bootstrap script once, and starts the API on "
            "127.0.0.1:8000. Issue a token with: docker compose run --rm api python "
            "scripts/issue_dev_token.py demo-analyst-001 --minutes 30. Stop with Ctrl+C, then "
            "docker compose down. Add -v to also delete the database volume."
        )
    )

    s.append(h1("Troubleshooting"))
    s.append(
        table(
            [
                ["Problem", "What to check"],
                [
                    "command not found: python3 or pip",
                    "Install Python 3.11+ and create the virtual environment (Step 1). Activate it again "
                    "in every new terminal.",
                ],
                [
                    "createdb: command not found",
                    "Install the PostgreSQL client tools, or create the database "
                    "with any PostgreSQL client (for example, pgAdmin).",
                ],
                [
                    "bootstrap: APP_DB_PASSWORD is required (or similar)",
                    "The variables from Step 5 are not set in this terminal. Export them again.",
                ],
                [
                    "password authentication failed",
                    "The password in .env does not match the one you exported in Step 5. "
                    "Make them identical.",
                ],
                [
                    "401 from /chat",
                    "The token has expired, or JWT_SECRET changed after the token was "
                    "issued. Issue a new token (Step 9).",
                ],
                [
                    "temporarily_unavailable for every question",
                    "Expected when TYPESAFE_API_KEY is empty. Add a key to see answered responses.",
                ],
                [
                    "Could not import module app.main",
                    "Run uvicorn from the project folder, with the virtual environment active.",
                ],
                [
                    "Integration tests skipped",
                    "Set TEST_ADMIN_DATABASE_URL to a database whose name contains test (Step 12).",
                ],
                [
                    'role "postgres" does not exist',
                    "Your PostgreSQL superuser is not postgres (common with Homebrew on macOS). Set "
                    "PG_SUPERUSER to your macOS username (Step 4), and use it in every connection URL.",
                ],
                [
                    "npm: command not found, or Next.js will not start",
                    "Install Node.js 18.18 or newer, then run npm install inside the frontend folder "
                    "(Step 11).",
                ],
                [
                    "Frontend shows 'Not signed in' or temporarily unavailable in live mode",
                    "Paste the token from Step 9 in Settings. Check that the API from Step 7 is running "
                    "and that BACKEND_URL in frontend/.env.local points to it.",
                ],
                [
                    "Port 8000 or 5432 already in use",
                    "Another program is using the port. Stop it, or "
                    "run uvicorn with --port 8001 and use that port in the curl commands.",
                ],
            ],
            [58 * mm, 120 * mm],
        )
    )

    s.append(h1("Quick reference"))
    s.append(
        code("""
source .venv/bin/activate
pip install -e ".[dev]"                 # once
export PG_SUPERUSER="$(whoami)"        # macOS Homebrew; use postgres on Linux
createdb -h localhost -U "$PG_SUPERUSER" merchant_analytics   # once
# export the password variables (Step 5), then:
bash docker/migrate.sh                  # once, or safe to repeat
uvicorn app.main:app --reload
python scripts/issue_dev_token.py demo-analyst-001 --minutes 30
python -m pytest tests -q
cd frontend && npm run dev              # optional web interface, http://localhost:3000
""")
    )
    return s


def build(output: Path = OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="How to Run the Merchant Payment Analytics Assistant",
        author="Merchant Payment Analytics project",
    )
    doc.build(story())
    return output


if __name__ == "__main__":
    print(f"wrote {build().relative_to(ROOT)}")
