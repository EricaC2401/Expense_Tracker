# Expense Tracker

Personal expense tracker for one user, built with Python 3.11+, Streamlit, and Supabase PostgreSQL.

The current stage is expense-only. Income handling is intentionally deferred until a later milestone if needed.

## V1 goals

- Work in a browser on MacBook and iPhone
- Store live data in Supabase PostgreSQL
- Support CSV export as a backup method
- Stay within free-tier services where practical
- Start with expense tracking before adding income support

## Local setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example secrets file and fill in your own local values:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

4. Run tests:

```bash
pytest
```

5. Start the Streamlit app:

```bash
streamlit run src/app.py
```

## Supabase setup

1. Create a Supabase project.
2. Run the initial schema in [sql/001_initial_schema.sql](/Users/ericachung_1/Desktop/Erica/Vibe%20Codeing/Expense%20Marker/sql/001_initial_schema.sql) in the Supabase SQL editor.
3. Copy [.streamlit/secrets.toml.example](/Users/ericachung_1/Desktop/Erica/Vibe%20Codeing/Expense%20Marker/.streamlit/secrets.toml.example) to `.streamlit/secrets.toml`.
4. Fill in the `supabase` values with your own database credentials.

Notes:

- Use the direct database host or the Supabase pooler host, depending on which connection details you want for V1.
- Keep `sslmode = "require"`.
- The database schema is expense-only for the current stage and does not include `transaction_type`.
- Row Level Security is enabled on `public.transactions`, with no public policies added by default.

## Notes

- Do not commit `.streamlit/secrets.toml` or any real credentials.
- Keep `.streamlit/secrets.toml.example` as placeholders only.
- Supabase setup and schema creation are handled in later milestones.
- CSV export is planned as the V1 backup method.
- The current sample input file is `sample_data/sample_expense.csv`.
