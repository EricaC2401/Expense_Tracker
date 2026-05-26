# Expense Tracker Development Plan

## Objective

Build a personal expense tracker for one user.
The app should be accessible from both MacBook and iPhone through a browser.
The app should store data in Supabase PostgreSQL and provide CSV export for backup.

## How to use this plan

This plan is a roadmap, not a single implementation task.

Work through the milestones in order unless instructed otherwise.
Each Codex task should normally cover one milestone only.
Do not implement future milestones early, because future milestones may change as the project develops.

Update this file only when:

- a milestone is completed
- milestone order changes
- scope changes
- acceptance criteria change
- a major technical decision changes

Do not add detailed implementation notes, full SQL schemas, or low-level code details here.
Detailed SQL should live in SQL migration files.
Detailed setup and usage instructions should live in `README.md`.

## Current status

Current milestone: M0 Project setup

- M0 Project setup: Not started
- M1 Supabase database setup: Not started
- M2 Data validation and models: Not started
- M3 Basic categories: Not started
- M4 Database functions: Not started
- M5 Manual transaction entry: Not started
- M6 Transaction table view: Not started
- M7 CSV export backup: Not started
- M8 Edit and delete transactions: Not started
- M9 CSV import: Not started
- M10 Reports: Not started
- M11 Keyword-based category rules: Not started
- M12 Mobile-friendly quick-add page: Not started
- M13 Deployment: Not started
- M14 README and usage documentation: Not started

## V1 scope

### Included

- Manual transaction entry
- Basic category selection
- CSV export backup
- CSV import with duplicate warning
- Transaction view and filtering
- Basic reports
- Simple app-level password protection before deployment
- Deployment to Streamlit Community Cloud if suitable

### Excluded

- Multi-user login
- Bank API or Open Banking integration
- OCR or receipt scanning
- AI categorisation
- Native mobile app
- Paid hosting or paid database features
- Advanced duplicate detection
- SQLite or local PostgreSQL version

## V1 technical direction

Use:

- Python 3.11+
- Streamlit
- Supabase PostgreSQL
- pandas
- psycopg2-binary
- pytest

Preferred hosting:

- Streamlit Community Cloud free tier

Preferred secrets method:

- Streamlit secrets locally and in deployment

Architecture:

```text
MacBook browser
        ↓
Streamlit app
        ↓
Supabase PostgreSQL
        ↑
iPhone browser
```

Supabase PostgreSQL is the single source of truth.
CSV export is the V1 backup method.

## Data model direction

The main table is `transactions`.

Required transaction fields:

- `id`
- `transaction_date`
- `description`
- `amount`
- `transaction_type`
- `category`
- `payment_method`
- `notes`
- `created_at`
- `updated_at`

Rules:

- Store amounts as positive numbers.
- Use `transaction_type` to distinguish `income` from `expense`.
- Default missing or blank categories to `Uncategorised`.
- Income increases balance.
- Expense decreases balance.
- `updated_at` should be maintained by a PostgreSQL trigger or explicit application logic. Prefer a trigger for V1.

The exact PostgreSQL schema should be implemented in SQL migration files under `sql/`, not directly in this plan.

## Target project structure

This is the intended starting structure for V1 and may evolve slightly during implementation.

```text
expense-tracker/
├── AGENTS.md
├── PLAN.md
├── README.md
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example
├── sql/
│   └── 001_initial_schema.sql
├── src/
│   ├── app.py
│   ├── db.py
│   ├── models.py
│   ├── import_csv.py
│   ├── export_csv.py
│   ├── categorisation.py
│   └── reports.py
├── tests/
│   ├── test_models.py
│   ├── test_import_csv.py
│   ├── test_export_csv.py
│   └── test_reports.py
└── sample_data/
    └── sample_transactions.csv
```

---

## M0 — Project setup

### Goal

Create the basic project structure.

### Codex tasks

- Create the target project folders and placeholder files.
- Create `README.md`.
- Create `requirements.txt` with the core packages.
- Create `.gitignore` covering secrets and local cache files.
- Create `.streamlit/secrets.toml.example`.
- Add `sample_data/sample_transactions.csv` with 5–10 example rows.

The sample CSV should use these columns:

`transaction_date`, `description`, `amount`, `transaction_type`, `category`, `payment_method`, `notes`

### Done when

- Project structure matches the target layout.
- `requirements.txt` includes required packages.
- `.gitignore` excludes secrets and local files.
- `README.md` explains basic local setup.
- `pytest` runs without errors.

---

## M1 — Supabase database setup

### Goal

Prepare the Supabase PostgreSQL database and connect the app to it.

### Human tasks

- Create a Supabase account if needed.
- Create a Supabase project.
- Run the initial SQL migration in the Supabase SQL editor.
- Confirm database connection details are available.

### Codex tasks

- Create `sql/001_initial_schema.sql` for the initial schema.
- Add database connection logic in `src/db.py`.
- Use `@st.cache_resource` on the connection function.
- Add a simple connection test function.
- Add clear error handling if the connection fails.
- Update README with Supabase connection notes.
- Confirm real credentials are not committed to Git.

### Notes

Prefer the Supabase connection pooler, if appropriate, to reduce the risk of hitting free-tier connection limits.

### Done when

- Human tasks are confirmed complete by the user.
- The app can connect to Supabase PostgreSQL.
- Database credentials are not committed to Git.
- A connection test function exists, and a real connection is confirmed after the user completes the required human setup tasks.
- Initial SQL lives in `sql/001_initial_schema.sql`.
- `src/db.py` contains the connection logic with `@st.cache_resource`.

---

## M2 — Data validation and models

### Goal

Create basic validation for transaction data.

### Codex tasks

- Add transaction validation logic in `src/models.py`.
- Validate required fields.
- Reject negative amounts.
- Reject transaction types other than `income` or `expense`.
- Use `Uncategorised` if no category is provided.
- Normalise text fields where useful.
- Add tests in `tests/test_models.py`.

### Done when

- Valid data passes validation.
- Invalid data returns clear error messages.
- Negative amounts are rejected.
- Invalid transaction types are rejected.
- Missing categories default to `Uncategorised`.
- Tests pass.

---

## M3 — Basic categories

### Goal

Create a simple category structure before manual entry, CSV import, and reports.

### Codex tasks

- Define a default category list in `src/categorisation.py`.
- Use `Uncategorised` when no category is provided.
- Add a helper function to return the category list.
- Do not implement keyword-based auto-categorisation yet.

Suggested default categories:

- Housing
- Groceries
- Car Related
- Transport
- Eating out
- Shopping
- Bills
- Subscriptions
- Healthcare
- Travel
- Income
- Other
- Uncategorised

For V1, the category list is defined in code. A UI for managing categories is not in scope.

### Done when

- Manual entries can use the default category list.
- Imported data can fall back to `Uncategorised`.
- Reports can group uncategorised transactions clearly.
- Category logic is available before CSV import and reports are built.

---

## M4 — Database functions

### Goal

Create basic database operations.

### Codex tasks

- Add functions to insert, fetch, fetch by ID, update, and delete transactions.
- Keep all SQL inside `src/db.py`.
- Use parameterised SQL only.
- Add simple handling for dropped connections.
- Show clear errors if Supabase is unavailable.
- Add tests where practical for database-facing logic, using mocks or isolated tests if a live database is not available.

### Done when

- Transactions can be inserted, fetched, updated, and deleted.
- `updated_at` updates correctly after edits.
- All database logic is inside `src/db.py`.
- No queries are placed directly inside `src/app.py`.
- Connection failures show useful errors.

---

## M5 — Manual transaction entry

### Goal

Allow the user to add transactions manually.

### Codex tasks

- Create a Streamlit form in `src/app.py`.
- Use the category list from `src/categorisation.py`.
- Validate required fields using `src/models.py`.
- Save valid transactions using `src/db.py`.
- Show clear success and error messages.
- Keep the form simple and mobile-friendly.

### Done when

- User can add an expense and income manually.
- User can select from the default category list.
- Invalid input shows a helpful error message.
- Saved transactions appear in the database.

---

## M6 — Transaction table view

### Goal

Allow the user to view saved transactions.

### Codex tasks

- Display recent transactions sorted by date, newest first.
- Add basic filters: date range, category, transaction type.
- Make the table readable on MacBook and usable on iPhone.
- Keep display logic in `src/app.py` and data fetching in `src/db.py`.

### Done when

- User can view and filter transactions.
- Uncategorised transactions are clearly visible.
- Table is readable on both devices.

---

## M7 — CSV export backup

### Goal

Allow the user to back up data as CSV before edit/delete is added.

### Codex tasks

- Add export function in `src/export_csv.py`.
- Add tests in `tests/test_export_csv.py`.
- Add a Streamlit download button.
- Export all transactions with all key fields.
- Use a filename with the local current date: `expense_tracker_backup_YYYY-MM-DD.csv`.

### Done when

- User can download all transaction data as CSV.
- CSV contains all key fields and can be opened in spreadsheet software.
- Export is working before edit and delete features are added.

---

## M8 — Edit and delete transactions

### Goal

Allow the user to correct mistakes.

### Codex tasks

- Add edit and delete functionality.
- Require confirmation before deleting.
- Show a clear warning before destructive actions.
- Ensure delete is not easily triggered by accident on mobile.

### Done when

- User can edit a transaction.
- User can delete a transaction only after confirmation.
- CSV export already exists before this milestone is implemented.
- `updated_at` updates correctly after edits.

---

## M9 — CSV import

### Goal

Allow the user to import transactions from CSV.

### Expected CSV columns

`transaction_date`, `description`, `amount`, `transaction_type`, `category`, `payment_method`, `notes`

### Codex tasks

- Add CSV upload in Streamlit.
- Add CSV cleaning logic in `src/import_csv.py`.
- Validate required columns, dates, amounts, and transaction types.
- Use `Uncategorised` if category is missing or blank.
- Before inserting, show a clear warning that V1 does not perform full duplicate detection.
- Ask the user to confirm before inserting imported rows.
- Insert valid rows into Supabase.
- Show useful errors for invalid files.
- Add tests in `tests/test_import_csv.py`.

### Done when

- User can import a valid CSV file.
- Invalid files show useful error messages.
- User sees a duplicate warning and confirms before import proceeds.
- Missing categories fall back to `Uncategorised`.
- Tests pass.

---

## M10 — Reports

### Goal

Add basic financial summaries.

### Reports

- Monthly income
- Monthly expenses
- Net balance
- Spending by category
- Largest transactions
- Monthly trend

### Codex tasks

- Add report functions in `src/reports.py`.
- Add tests in `tests/test_reports.py`.
- Add charts and summary tables in Streamlit.
- Allow the user to select a date range or month.
- Keep report calculations outside `src/app.py`.
- Apply sign logic correctly.

### Done when

- User can view monthly spending, category breakdowns, and net balance.
- Uncategorised transactions are grouped clearly.
- Net balance is calculated correctly.
- Report calculations are tested.

---

## M11 — Keyword-based category rules

### Goal

Make categorisation faster without using AI.

### Codex tasks

- Add keyword-based rules in `src/categorisation.py`.
- Allow the user to override categories manually.
- Keep rules simple and editable in code.
- Do not use AI categorisation.

Example rules:

- Tesco, Aldi, Lidl → Groceries
- Trainline, Uber → Transport
- Netflix, Spotify → Subscriptions
- Amazon → Shopping
- Council Tax → Bills
- Rent → Housing

### Done when

- Imported transactions can be categorised faster using keyword rules.
- User can manually override the suggested category.
- Categorisation logic is in `src/categorisation.py`, not `src/app.py`.
- Uncategorised transactions are still handled clearly.

---

## M12 — Mobile-friendly quick-add page

### Goal

Make the app faster to use on iPhone.

### Codex tasks

- Add a quick-add transaction section with dropdowns where possible.
- Reduce required typing.
- Keep layout narrow-screen friendly with easy-to-tap buttons.

### Done when

- User can comfortably add an expense from iPhone.
- The app remains usable on MacBook.
- The quick-add flow is faster than the full transaction form.

---

## M13 — Deployment

### Goal

Make the app accessible from both MacBook and iPhone.

### Human tasks

- Connect the GitHub repository to Streamlit Community Cloud.
- Add Supabase credentials through Streamlit Community Cloud secrets.
- Deploy the app through the Streamlit Community Cloud dashboard.
- Test the deployed URL from MacBook and iPhone.

### Codex tasks

- Add simple app-level password protection before deployment.
- Add deployment-specific notes to `README.md`.
- Add Streamlit Community Cloud secrets instructions.
- Document the chosen Supabase security and RLS approach for deployment.
- Add brief deployment troubleshooting notes for Supabase connection issues.

### Notes

Streamlit Community Cloud free tier commonly uses public GitHub repositories. If the user prefers a private repository or another provider, pause and confirm before changing the deployment approach.

### Done when

- Human tasks are confirmed complete by the user.
- The app is accessible from both MacBook and iPhone.
- Simple password protection is in place before the URL is shared.
- Both devices use the same Supabase data.
- No secrets are exposed in GitHub.
- The Supabase security approach is documented.

---

## M14 — README and usage documentation

### Goal

Make the project easy to run and maintain.

### Codex tasks

- Document local setup and Python 3.11+ requirement.
- Document how to configure `.streamlit/secrets.toml` locally.
- Document how to configure Streamlit Community Cloud secrets.
- Document how to run Streamlit locally.
- Document how to export CSV backups.
- Document the V1 architecture and what is not included.
- Document the Supabase connection approach.
- Document the Supabase Free inactivity limitation.
- Document the public/private repository consideration for deployment.
- Document the chosen Supabase security and RLS approach.
- Document the duplicate import limitation in V1.

### Done when

- User can understand how to run, back up, and deploy the project.
- User knows how to configure secrets in both local and deployed environments.
- User understands the main V1 limitations.
