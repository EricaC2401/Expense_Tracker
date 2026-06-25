# AGENTS.md

## Purpose

This file defines how Codex should work in this repository.
Use it for execution rules, guardrails, and change-management expectations.
Use `PLAN.md` for roadmap content, milestone definitions, and scope tracking.

## Project summary

This project is a personal expense tracker for one user.
It should be usable from both MacBook and iPhone through a browser.
The stack for the current version is Python 3.11+, Streamlit, and Supabase PostgreSQL, with CSV export used as a backup path.

Unless the user explicitly requests otherwise, treat expense tracking as the primary scope and avoid broadening the product on your own.

## Cost and hosting constraints

Aim to stay within free tiers where practical.

Preferred services:

- Supabase Free plan
- Streamlit Community Cloud free hosting

Do not introduce paid services, paid APIs, paid hosting, paid database features, or paid add-ons unless the user explicitly approves them.

If a proposed feature may create cost risk, pause and explain the tradeoff before implementing it.

## Default working rules

Before making meaningful code changes:

1. Read `AGENTS.md`.
2. Read `PLAN.md`.
3. Identify the active milestone or explicitly approved task.
4. Summarise the intended change before editing files.
5. Keep the change focused and reviewable.
6. Add or update tests where practical.

Unless the user explicitly requests otherwise, do not implement the whole roadmap in one task.

When `PLAN.md` lists work that is out of milestone order, treat the `Current status` section in `PLAN.md` as the source of truth for what is currently active.

## Human task boundaries

Human-only tasks must be clearly identified.
Do not claim human-only tasks are complete unless the user confirms they have done them.

Common human tasks include:

- creating a Supabase account or project
- running SQL in the Supabase SQL editor
- adding secrets to Streamlit Community Cloud
- deploying through a hosting dashboard

## When to update `PLAN.md`

Use `PLAN.md` as a roadmap, not as an implementation log.

Update `PLAN.md` only when:

- a milestone is completed
- milestone order changes
- project scope changes
- acceptance criteria change
- a major technical decision changes

Do not update `PLAN.md` for small implementation details, refactors, bug fixes, function names, UI tweaks, or minor SQL changes.

Detailed implementation notes should live in code, tests, migrations, or `README.md`, not in `PLAN.md`.

## Code and architecture guidelines

Keep the code modular, readable, and easy to change.

General expectations:

- keep UI code separate from database and reporting logic
- use reusable functions for shared logic
- prefer clear code over clever code
- keep schema changes in SQL migration files
- keep tests under `tests/`

Avoid placing database queries or reporting calculations directly in the Streamlit page code unless there is a strong reason.

## Database and data rules

Supabase PostgreSQL is the live database for the current version and should be treated as the source of truth unless the user requests an architectural change.

General database expectations:

- use parameterised SQL queries
- avoid string interpolation with user input in SQL
- handle connection failures gracefully
- keep connection and query concerns in a dedicated database module
- maintain `updated_at` consistently, preferably in the database

Unless a milestone says otherwise, `payment_method` and `notes` may remain optional.

For expense records, keep amount handling consistent:

- stored amounts keep their original sign
- reports should use the stored sign when calculating balances

## Secrets and security

Use Streamlit secrets as the primary secrets mechanism for local development and deployment.

Never commit secrets, database credentials, passwords, service role keys, or API keys to Git.
Never hard-code credentials in source code.
Never print secrets in logs, app output, error messages, or documentation examples.

Before deployment, document the chosen Supabase security approach.

For the online V1 app:

- protect access before sharing a public URL
- prefer a simple single-shared-password gate over a full multi-user auth system
- do not expose privileged keys in frontend-accessible code

## Data safety

Protect user data as the highest priority.

- never delete transactions without user confirmation
- avoid destructive schema changes unless explicitly requested
- explain risk when changing the database schema
- make sure CSV export exists before relying on edit/delete-heavy workflows
- warn before CSV imports when duplicate detection is limited

## User experience guidelines

The app should remain usable on both MacBook and iPhone.

Prefer:

- simple layouts
- clear actions and feedback
- minimal typing
- category dropdowns where appropriate
- readable transaction tables
- clear handling of uncategorised records

Use `Uncategorised` as the default category when none is provided, unless a future requirement changes that rule.

## Testing expectations

Use `pytest` for automated tests.
Do not overcomplicate UI testing for the early versions.
For each milestone, add or update tests where practical.

## Out of scope unless explicitly requested

Do not introduce the following on your own:

- SQLite or local PostgreSQL as an alternative live database
- database synchronisation systems
- paid APIs or paid hosting
- complex multi-user authentication
- AI categorisation or OCR
- automated keep-alive jobs
- advanced duplicate detection
- Open Banking or bank API integration
