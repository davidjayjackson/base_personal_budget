---
name: budget-odb-build-workflow
description: How budget.odb is generated reproducibly from scripts; run order and engine
metadata: 
  node_type: memory
  type: project
  originSessionId: e1ed938b-9aab-4adb-b3b9-8ada4ffa523e
---

`budget.odb` (LibreOffice Base) is generated reproducibly by UNO scripts in `scripts/`, run with LibreOffice's bundled Python (`"C:\Program Files\LibreOffice\program\python.exe"`) because it ships the `uno` module. Close any interactive LibreOffice first (file lock).

Run order:
1. `build_odb.py` — creates embedded **Firebird** .odb: 5 tables (Accounts, Categories, Transactions, Budgets, RecurringTransactions) with PKs, 6 FKs, CHECK constraints, plus seed data.
2. `build_reports.py` — 4 Firebird views (`RPT_*`) + 4 thin `SELECT * FROM view` queries (`RptMonthlySpending`, `RptBudgetVsActual`, `RptAccountBalances`, `RptIncomeExpenseTrend`). Views hide complex SQL so the Report Builder engine can consume them — see [[report-builder-not-scriptable]].
3. `build_forms.py` — 4 embedded grid forms: `TransactionEntry`, `Accounts`, `Categories`, `RecurringSetup` (FK fields are dropdowns).
4. `verify_odb.py` / `verify_forms.py` — structural checks.

Each build script spawns its own headless soffice on a private socket + profile (`file:///c:/temp/lo_odb_build`, ports 2103–2107). Engine is Firebird, not HSQLDB (an old HSQLDB attempt is `budget.odb.hsqldb.bak`, gitignored). `personal_budget.ods` is the schema source-of-truth; seed-data ids in `build_odb.py` mirror its sheets. Reserved words `"date","type","month"` are quoted in SQL. See [[headless-forms-uno-gotchas]].

PROJECT COMPLETE and pushed to origin/main (David Jackson's repo davidjayjackson/base_personal_budget). All deliverables done and verified in the Base GUI: 5 tables, 4 views, 4 queries, 4 forms (dropdowns confirmed showing names), and 4 finished Report-Builder reports (created via the Base Report Wizard, named with the Rpt* prefix, in the Reports pane — all open with data). README documents the build/regenerate workflow and embeds `docs/reports.png` (screenshot of the Reports pane). Note: opening budget.odb in Base dirties the file (session churn) even with no edits — discard with `git checkout -- budget.odb` after closing Base.
