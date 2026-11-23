# Jevlytics: getting started

This guide takes you from an empty computer to a running Jevlytics assistant. You will type commands into a terminal and copy each one exactly. The first run takes about 45 minutes, most of it spent installing tools.

**What you will have at the end:**

- A database filled with fictional payment data.
- A backend API that answers questions about that data.
- A web dashboard, with an assistant panel, in your browser.

> **Windows users:** run every command below inside WSL (Windows Subsystem for Linux). Install it from the Microsoft Store, open the Ubuntu app, and follow the steps there.

> **Mac users:** open the Terminal app. Each command below goes in one line, and you press Return to run it.

## Checklist

Tick each item as you finish it.

- [ ] Step 1: Four tools installed (about 15 minutes)
- [ ] Step 2: Terminal open in the project folder (about 1 minute)
- [ ] Step 3: Python environment and backend installed (about 5 minutes)
- [ ] Step 4: `.env` file created and edited (about 5 minutes)
- [ ] Step 5: PostgreSQL running and database created (about 3 minutes)
- [ ] Step 6: Database passwords set (about 2 minutes)
- [ ] Step 7: Database built (about 2 minutes)
- [ ] Step 8: Backend running and health check passed (about 2 minutes)
- [ ] Step 9: Question sent to the assistant (optional, about 2 minutes)
- [ ] Step 10: Dashboard running (about 5 minutes)
- [ ] Step 11: Main features tried (about 5 minutes)

---

## Step 1: Install four tools

*About 15 minutes if you need to install everything.*

Check whether each tool is already installed by running its version command.

| Tool | Version command | Needed version | If you need to install it |
|---|---|---|---|
| Python | `python3 --version` | 3.11 or later | python.org/downloads |
| PostgreSQL | `psql --version` | 16 | `brew install postgresql@16` on a Mac, or postgresql.org/download |
| Node.js | `node --version` | 20 or later | nodejs.org |
| Git (optional) | `git --version` | any | git-scm.com |

On a Mac with Homebrew, you can install PostgreSQL and start it with:

```bash
brew install postgresql@16
brew services start postgresql@16
```

**Done when:** each version command prints a version number, for example `Python 3.12.4` or `v20.11.1`.

---

## Step 2: Open a terminal in the project folder

*About 1 minute.*

Move into the folder that contains `README.md` and `app/`:

```bash
cd path/to/merchant-payment-analytics
```

Replace `path/to/` with the real location. On a Mac, you can drag the folder onto the Terminal window to paste its path.

**Done when:** `ls` shows `app`, `frontend`, `scripts` and `data`.

---

## Step 3: Create a Python environment and install the backend

*About 5 minutes.*

A Python environment keeps the project's packages separate from the rest of your computer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Your prompt now starts with `(.venv)`. That means the environment is active. Each time you open a new terminal, run `source .venv/bin/activate` again before starting the backend.

**Done when:** the install ends with a line that starts with `Successfully installed`.

---

## Step 4: Create your settings file

*About 5 minutes.*

```bash
cp .env.example .env
```

Open `.env` in any text editor and make these three changes. The database passwords must match the ones you choose in Step 6.

1. Replace the `JWT_SECRET=` value with a long random string (see the command below).
2. Set the password in `DATABASE_URL` to your `APP_DB_PASSWORD` from Step 6. The user name stays `merchant_app`.
3. Set the password in `ANALYTICS_DATABASE_URL` to your `ANALYTICS_RO_PASSWORD` from Step 6. The user name stays `analytics_ro`.

Also set `MIGRATION_DATABASE_URL` to use your `OWNER_DB_PASSWORD`. The user name stays `merchant_owner`.

For example, with the Step 6 values, the lines would look like this:

```
DATABASE_URL=postgresql+psycopg://merchant_app:AppPass123@localhost:5432/merchant_analytics
ANALYTICS_DATABASE_URL=postgresql+psycopg://analytics_ro:ReadOnlyPass123@localhost:5432/merchant_analytics
MIGRATION_DATABASE_URL=postgresql+psycopg://merchant_owner:OwnerPass123@localhost:5432/merchant_analytics
```

To generate the random string, run this in the terminal and paste the output into `JWT_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

You can leave the API key lines empty for now. The assistant needs them only for live answers. The dashboard in demo mode works without them.

> **Keep `.env` private.** Never share it, and never commit it to GitHub. The project's `.gitignore` already excludes it.

**Done when:** `.env` exists and `JWT_SECRET` is set to a value of at least 32 characters.

---

## Step 5: Start PostgreSQL and create the database

*About 3 minutes.*

Create a database called `merchant_analytics`:

```bash
createdb -h localhost -U postgres merchant_analytics
```

If PostgreSQL asks for a password for `postgres`, use the one you set when you installed it.

**Done when:** the command finishes with no output. A quiet success is normal here.

---

## Step 6: Set the database passwords

*About 2 minutes.*

The project uses three database accounts, each with its own password. Choose a password for each and export them in your terminal. Use any values you like, but do not reuse one of these passwords elsewhere.

```bash
export ADMIN_DATABASE_URL=postgresql://postgres@localhost:5432/merchant_analytics
export OWNER_DATABASE_URL=postgresql+psycopg://merchant_owner:OwnerPass123@localhost:5432/merchant_analytics
export APP_DB_PASSWORD=AppPass123
export ANALYTICS_RO_PASSWORD=ReadOnlyPass123
export OWNER_DB_PASSWORD=OwnerPass123
```

The values above are examples. Replace them with your own before running the commands.

> These `export` lines last only for the current terminal window. If you open a new window, run them again.

**Done when:** the commands finish with no output.

---

## Step 7: Build the database

*About 2 minutes.*

This step creates the tables, the database accounts, and the fictional data.

```bash
bash docker/migrate.sh
```

You will see these lines, in this order, among some log lines from Alembic:

```
[migrate] alembic upgrade head
[migrate] database roles
[migrate] seed synthetic demo data (owner role)
[migrate] done
```

**Done when:** the last line is `[migrate] done` and there is no red error text. Each of the three other lines is a step in progress. Log lines that start with `INFO` are normal.

---

## Step 8: Start the backend

*About 2 minutes.*

```bash
uvicorn app.main:app --reload
```

Leave this terminal open. The backend runs here until you press Control and C. You will see a line that says `Uvicorn running on http://127.0.0.1:8000`.

Open a **new** terminal window for the next steps. Activate the environment there too:

```bash
cd path/to/merchant-payment-analytics
source .venv/bin/activate
```

Check that the backend is up:

```bash
curl -s http://localhost:8000/health
```

The response is JSON. Look for `"status": "ok"` and `"database": "ok"`. A development setup may also include a `configured` block, which shows whether each key is set.

You can also open `http://localhost:8000/docs` in your browser. It shows every endpoint and lets you try them.

**Done when:** the health check shows `"status": "ok"` and `"database": "ok"`, and the `/docs` page opens.

---

## Step 9: Ask the assistant a question (optional)

*About 2 minutes. This step uses the backend directly, without the dashboard.*

In the new terminal, create a sign-in token for a demo user. The script prints a long string of letters and numbers. You don't need to read it.

```bash
export TOKEN=$(python scripts/issue_dev_token.py demo-analyst-001 --minutes 30)
```

Send a question:

```bash
curl -s -X POST localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "content-type: application/json" \
  -d '{"message": "What was my decline rate last month?"}'
```

The response is JSON with a `status` field. It says `answered` if the keys are set, and `temporarily_unavailable` if they are not. Both results mean the backend is working.

**Done when:** the response contains a `status` field.

---

## Step 10: Start the dashboard

*About 5 minutes, most of it the first `npm install`.*

Open a third terminal window:

```bash
cd path/to/merchant-payment-analytics/frontend
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000` in your browser.

The dashboard starts in **demo mode**. It shows fictional data and does not need the backend. Demo mode is labelled as fictional on the page.

**Done when:** the page loads and shows the transaction table.

---

## Step 11: Try the main features

*About 5 minutes.*

1. **Look at the assistant.** It is the chat button in the bottom-right corner. Click it to open the panel.
2. **Ask a question.** Try "Show the decline rate for October."
3. **Switch users.** Use the switcher in the bottom-left corner to change to another demo analyst.
4. **Try the cross-merchant rule.** Signed in as Demo Analyst 001 (merchant 1), ask "Show the decline rate for merchant two." The assistant refuses it. Switch to Demo Analyst 002 (merchant 2) and ask the same question. The assistant answers, because it is that merchant's own data.
5. **Change the dates.** On the transaction page, edit the start and end dates to change the range shown in the table.

---

## Questions to try

Use these with the backend from Step 9 or the assistant panel. The results below apply to the live backend. Demo mode gives fixed example answers, so its results may differ.

| Status you should see | Signed in as | Question to ask | Why it gets that status |
|---|---|---|---|
| `answered` | Demo Analyst 001 | "What was my decline rate in October 2026, and how is it defined?" | The question names a metric and a period, and asks about the signed-in merchant. |
| `unsupported` | Demo Analyst 001 | "What is the weather in Paris today?" | It is outside payment analytics, so no tool applies. |
| `clarification_required` | Demo Analyst 001 | "Show me the decline rate." | It names a metric but no period, so the assistant asks for one. |
| `temporarily_unavailable` | Demo Analyst 001 | "What was my decline rate in October 2026, and how is it defined?" (with the keys unset) | The same question as the first row, but the Jev and Anthropic keys are missing, so the assistant stops rather than guess. |

The last row uses the same question as the first. It shows that the status depends on configuration, not on the wording.

---

## Stopping and restarting

To stop something, click its terminal window and press **Control and C**.

To start everything again later:

1. Start PostgreSQL. On a Mac with Homebrew: `brew services start postgresql@16`.
2. In a terminal, go to the project folder and run `source .venv/bin/activate`, then `uvicorn app.main:app --reload`.
3. In another terminal, go to `frontend` and run `npm run dev`.
4. Run the `export` lines from Step 6 again, if you are not using a saved shell profile.

You do not need to repeat Steps 1 to 7. The database keeps its data.

---

## When something goes wrong

| What you see | What to do |
|---|---|
| `command not found: python3`, `npm` or `psql` | The tool is not installed or not on your path. Go back to Step 1. |
| `connection refused` when running `migrate.sh` or `createdb` | PostgreSQL is not running. Start it, then try again. |
| `role "merchant_owner" does not exist` or a password error | Run the `export` lines from Step 6 in the same terminal, then run `migrate.sh` again. |
| `JWT_SECRET` error when starting the backend | Set `JWT_SECRET` in `.env` to a value of at least 32 characters. |
| The health check shows `"database": "unavailable"` | The passwords in `.env` do not match Step 6. Fix them, then restart the backend. |
| `GET /` returns 404 in the browser | This is expected. Open `/health` or `/docs` instead. |
| Assistant says `temporarily_unavailable` | The API keys are not set. This is expected in demo mode. To get live answers, add the keys to `.env` and restart the backend. |
| The dashboard still shows old content after a change | Stop `npm run dev` and start it again. |
| Port 8000 or 3000 is already in use | Another program is using it. Stop that program, or stop the earlier server with Control and C. |

---

## Frequently asked questions

**Why does the assistant say `temporarily_unavailable`?**
The assistant needs the Jev and Anthropic keys to answer live questions. Without them, it stops rather than guessing. Add the keys to `.env` and restart the backend.

**Why do the demo answers look the same every time?**
Demo mode uses fixed example answers and keyword matching. It is there to show the interface. For real answers, use the live backend.

**Why can't Demo Analyst 001 see merchant 2's data?**
That is the rule the project is built around. A user can see only their own merchant's data. The assistant refuses any request that names another merchant, however it is worded.

**Can I load my own payment data?**
No. The project uses only fictional data and has no upload feature. To change the fictional data, see [docs/DATA.md](docs/DATA.md).

**Will the API keys cost money?**
Yes, if they are live keys. Usage of the TypeSafe and Anthropic services is billed by those providers. Check their pricing before you run many questions.

**Can I stop PostgreSQL when I'm done?**
Yes. On a Mac with Homebrew, run `brew services stop postgresql@16`. Your data stays in place, and you can start it again later.

---

## Where to go next

- [README.md](README.md): what the project does and what it does not do.
- [docs/CROSS_MERCHANT_ACCESS.md](docs/CROSS_MERCHANT_ACCESS.md): how the rule about other merchants' data is enforced.
- [docs/RUNNING.md](docs/RUNNING.md): configuration reference and the full test commands.
