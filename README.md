Project: Personal Budget Application (LibreOffice Base + Calc)
Objective: Build a personal budget management application using LibreOffice Base, backed by a .odb database file named budget.odb. Table structure should be prototyped first in a Calc spreadsheet (personal_budget.ods) before being implemented as actual database tables.
Deliverables

personal_budget.ods — a Calc workbook where each sheet represents the layout/schema of one database table (column headers, data types noted, sample rows). This is the design reference, not the live data.
budget.odb — the LibreOffice Base database file containing:

Tables (built from the .ods layouts)
Primary keys and indexes
Relationships (foreign keys) between tables
Data entry/display forms
Finished reports


Supporting documentation (README) explaining the schema, relationships, and how to use the forms/reports.

Suggested Database Tables (to define in personal_budget.ods first)

Accounts — bank/credit accounts (id, name, type, starting_balance)
Categories — spending categories (id, name, parent_category_id for sub-categories)
Transactions — individual income/expense entries (id, date, account_id, category_id, amount, description, type)
Budgets — planned monthly amounts per category (id, category_id, month, planned_amount)
RecurringTransactions — templated recurring bills/income (id, description, amount, frequency, category_id, account_id, next_due_date)

(Adjust/add tables as needed — this is a starting structure.)
Relationships

Transactions.account_id → Accounts.id
Transactions.category_id → Categories.id
Budgets.category_id → Categories.id
RecurringTransactions.account_id → Accounts.id
RecurringTransactions.category_id → Categories.id
Categories.parent_category_id → Categories.id (self-referencing, optional)

Forms Needed

Transaction entry form (add/edit/delete transactions, with dropdowns for account and category)
Account management form
Category management form
Recurring transaction setup form

Reports Needed

Monthly spending by category
Budget vs. actual spending
Account balance summary
Income vs. expense trend over time

Technical Notes for Implementation

Build tables via .odb HSQLDB/Firebird embedded engine (LibreOffice Base default)
Consider scripting table/form/report creation via the LibreOffice UNO API (Python) for reproducibility, since Base GUI work isn't easily version-controlled
Keep personal_budget.ods as the single source of truth for schema design — update it first, then regenerate/adjust the .odb tables to match
