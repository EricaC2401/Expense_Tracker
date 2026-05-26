# AGENTS.md

## Project overview

This is a personal expense tracker for one user.
The app should be accessible from both MacBook and iPhone using a browser.
It will be built with Python 3.11+ and Streamlit, using Supabase PostgreSQL as the live database and CSV export as the backup method.

## Cost constraint

The project should aim to run on free tiers where possible.

Use:

- Supabase Free plan
- Streamlit Community Cloud free hosting

Do not use paid services, paid APIs, paid hosting, paid database features, or paid add-ons unless explicitly approved by the user.

If a feature may require payment, pause and explain the cost risk before implementing it.

The Supabase Free plan may pause inactive projects after a period of inactivity. Do not implement paid workarounds unless explicitly approved.

## Working method

Work on this project one milestone at a time.

The current milestone is the first milestone in `PLAN.md` that is not marked completed, unless the user explicitly chooses a different milestone.

Before making code changes:

1. Read `AGENTS.md`.
2. Read `PLAN.md`.
3. Identify the current milestone.
4. Summarise the intended changes before editing files.
5. Implement only the current milestone.
6. Do not begin work from a later milestone, even if it seems small or related, unless the user explicitly requests that milestone.
7. Keep changes small and reviewable.
8. Add or update tests where practical.
9. At the end, report:
   - files changed
   - what was implemented
   - how it was tested
   - whether `PLAN.md` needs updating

Do not implement the whole roadmap in one task.

Human tasks must be clearly identified. Do not claim that human-only tasks are complete unless the user confirms they have done them.

Examples of human tasks:

- creating a Supabase account or project
- running SQL in the Supabase SQL editor
- adding secrets to Streamlit Community Cloud
- deploying through a hosting dashboard

## How to update `PLAN.md`

Use `PLAN.md` as the project roadmap, not as a detailed implementation log.

Update `PLAN.md` only when:

- a milestone is completed
- milestone order changes
- project scope changes
- acceptance criteria change
- a major technical decision changes

Do not update `PLAN.md` for small implementation details, refactors, bug fixes, function names, UI tweaks, or minor SQL changes.

Keep `PLAN.md` concise. Detailed SQL should live in SQL migration files. Detailed setup and usage instructions should live in `README.md`.

## Code organisation

Keep the code modular and easy to understand.

File responsibilities:

- `src/app.py`: Streamlit interface only
- `src/db.py`: Supabase/PostgreSQL connection and database queries
- `src/models.py`: data validation and transaction data structures
- `src/import_csv.py`: CSV import and cleaning logic
- `src/export_csv.py`: CSV export logic
- `src/categorisation.py`: category list and keyword-based category rules
- `src/reports.py`: reporting and aggregation logic
- `tests/`: pytest tests
- `sql/`: PostgreSQL schema and migration files

Do not put database queries directly inside `src/app.py`.

Do not put reporting calculations directly inside `src/app.py`.

Put common logic into reusable functions.

Prefer readable code over clever code.

## Database rules

Supabase PostgreSQL is the only live database for V1. It is the single source of truth.

Use `psycopg2-binary` as the PostgreSQL connector.

Keep all database logic inside `src/db.py`.

Use parameterised SQL queries. Do not build SQL queries using string interpolation with user input.

Use `@st.cache_resource` on the database connection function in `src/db.py` to avoid opening a new connection on every Streamlit rerun.

Handle database connection failures gracefully. Show a clear error message if Supabase is unavailable.

Where practical, add a simple retry or reconnect helper in `src/db.py` for dropped connections.

Use a PostgreSQL trigger or explicit application logic to maintain `updated_at` on transaction updates. Prefer a database trigger for V1.

For V1, `payment_method` and `notes` may be optional unless a milestone explicitly requires otherwise.

Report logic must treat amounts consistently:

- income increases balance
- expense decreases balance
- stored amounts are positive numbers
- `transaction_type` determines the sign in calculations

## Secrets and credentials

Use Streamlit secrets as the primary secrets method.

Use `.streamlit/secrets.toml` locally and Streamlit Community Cloud secrets for deployment.

Never commit `.env`, `.streamlit/secrets.toml`, database URLs, passwords, Supabase keys, or API keys to Git.

Never hard-code credentials in source code.

Never print secrets in logs, Streamlit output, error messages, or README examples.

## Supabase security

Do not expose Supabase service role keys in frontend code, GitHub, logs, or README examples.

Store credentials only in Streamlit secrets.

Before deployment, document the chosen Supabase security approach.

For V1, either:

- enable appropriate Row Level Security policies, or
- document clearly why RLS is not being used and what alternative protection is in place.

For V1, add simple app-level password protection before making the app accessible online. Password protection must be in place before the deployment URL is shared.

For V1, this means a single shared password gate for the app, not a multi-user login system.

Do not deploy publicly without simple app-level password protection.

Do not implement a complex multi-user authentication system in V1.

## Data safety

Preserve user data as the highest priority.

Never delete transactions without user confirmation.

Avoid destructive database changes unless explicitly requested.

When changing the database schema, explain the risk and update the relevant SQL migration or documentation.

CSV export must be implemented before edit and delete features.

Before importing CSV files, warn the user that V1 does not perform full duplicate detection and ask for confirmation before inserting rows.

## User interface principles

The app should be usable on both MacBook and iPhone.

Design with mobile use in mind:

- simple layout
- clear buttons
- minimal typing
- dropdowns for categories
- quick-add transaction form
- readable transaction table
- clear success and error messages

Use `Uncategorised` as the default category when none is provided.

Reports and transaction views should handle uncategorised transactions clearly.

## Testing expectations

Use `pytest` for all tests.

Do not overcomplicate tests for the Streamlit UI in V1.

For each milestone, add or update tests where practical.

## Do not do in V1

Do not introduce:

- SQLite or local PostgreSQL
- database synchronisation
- paid APIs or paid hosting
- multi-user login or complex authentication
- AI categorisation or OCR
- automated keep-alive jobs
- advanced duplicate detection
- Open Banking or bank API integration

These may be considered later only if explicitly requested.
