#!/usr/bin/env python
"""build_reports.py - add the analytical report views + queries to budget.odb.

The LibreOffice Report Builder engine (Pentaho/jfreereport) re-processes a
report's source SQL and chokes on advanced Firebird SQL (EXTRACT/CASE/COALESCE)
with "Syntax error in SQL statement" -- regardless of the query's
escape-processing flag. So the analytics live in database **views** (validated
once by Firebird at creation), and each saved query is a trivial
`SELECT * FROM <view>` that no engine can mangle. Reports built on these
queries execute cleanly.

    RptMonthlySpending     - monthly spending by category (expenses)
    RptBudgetVsActual      - planned vs. actual spend per category/month
    RptAccountBalances     - account balance summary (starting + net activity)
    RptIncomeExpenseTrend  - income vs. expense trend by month

Run with LibreOffice's bundled Python (needs the `uno` module); close Base
first so the .odb isn't locked:

    "C:\\Program Files\\LibreOffice\\program\\python.exe" scripts\\build_reports.py

Re-running replaces the views and queries.
"""
import os
import sys
import time
import subprocess

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.bin"
PORT = 2105
PROFILE = "file:///c:/temp/lo_odb_build"


def log(msg):
    sys.stderr.write("[build_reports] %s\n" % msg)
    sys.stderr.flush()


# Views hold all the complex SQL. Column names avoid Firebird reserved words
# (YEAR/MONTH/TYPE) so they need no quoting downstream. Quoted lowercase
# identifiers ("date","type","month") are the table columns.
VIEWS = {
    "RPT_MONTHLY_SPENDING": """
        CREATE OR ALTER VIEW RPT_MONTHLY_SPENDING (YR, MO, CATEGORY, SPENT) AS
        SELECT EXTRACT(YEAR  FROM t."date"),
               EXTRACT(MONTH FROM t."date"),
               c.name,
               SUM(t.amount)
        FROM   transactions t
               JOIN categories c ON t.category_id = c.id
        WHERE  t."type" = 'Expense'
        GROUP  BY EXTRACT(YEAR FROM t."date"),
                  EXTRACT(MONTH FROM t."date"),
                  c.name
    """,
    "RPT_BUDGET_VS_ACTUAL": """
        CREATE OR ALTER VIEW RPT_BUDGET_VS_ACTUAL
            (CATEGORY, BUDGET_MONTH, PLANNED, ACTUAL, REMAINING) AS
        SELECT c.name,
               b."month",
               b.planned_amount,
               COALESCE(SUM(t.amount), 0),
               b.planned_amount - COALESCE(SUM(t.amount), 0)
        FROM   budgets b
               JOIN categories c ON b.category_id = c.id
               LEFT JOIN transactions t
                      ON t.category_id = b.category_id
                     AND t."type" = 'Expense'
                     AND EXTRACT(YEAR  FROM t."date") = EXTRACT(YEAR  FROM b."month")
                     AND EXTRACT(MONTH FROM t."date") = EXTRACT(MONTH FROM b."month")
        GROUP  BY c.name, b."month", b.planned_amount
    """,
    "RPT_ACCOUNT_BALANCES": """
        CREATE OR ALTER VIEW RPT_ACCOUNT_BALANCES
            (ACCOUNT, ACCT_TYPE, STARTING_BALANCE, NET_ACTIVITY, CURRENT_BALANCE) AS
        SELECT a.name,
               a."type",
               a.starting_balance,
               COALESCE(SUM(CASE WHEN t."type" = 'Income'  THEN  t.amount
                                 WHEN t."type" = 'Expense' THEN -t.amount
                                 ELSE 0 END), 0),
               a.starting_balance
                 + COALESCE(SUM(CASE WHEN t."type" = 'Income'  THEN  t.amount
                                     WHEN t."type" = 'Expense' THEN -t.amount
                                     ELSE 0 END), 0)
        FROM   accounts a
               LEFT JOIN transactions t ON t.account_id = a.id
        GROUP  BY a.name, a."type", a.starting_balance
    """,
    "RPT_INCOME_EXPENSE_TREND": """
        CREATE OR ALTER VIEW RPT_INCOME_EXPENSE_TREND (YR, MO, INCOME, EXPENSE, NET) AS
        SELECT EXTRACT(YEAR  FROM t."date"),
               EXTRACT(MONTH FROM t."date"),
               SUM(CASE WHEN t."type" = 'Income'  THEN t.amount ELSE 0 END),
               SUM(CASE WHEN t."type" = 'Expense' THEN t.amount ELSE 0 END),
               SUM(CASE WHEN t."type" = 'Income'  THEN t.amount ELSE 0 END)
                 - SUM(CASE WHEN t."type" = 'Expense' THEN t.amount ELSE 0 END)
        FROM   transactions t
        GROUP  BY EXTRACT(YEAR FROM t."date"), EXTRACT(MONTH FROM t."date")
    """,
}

# Saved queries are thin wrappers so the report engine sees only a plain select.
QUERIES = {
    "RptMonthlySpending":    "SELECT * FROM RPT_MONTHLY_SPENDING",
    "RptBudgetVsActual":     "SELECT * FROM RPT_BUDGET_VS_ACTUAL",
    "RptAccountBalances":    "SELECT * FROM RPT_ACCOUNT_BALANCES",
    "RptIncomeExpenseTrend": "SELECT * FROM RPT_INCOME_EXPENSE_TREND",
}


def connect(ctx_local):
    import uno
    resolver = ctx_local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", ctx_local)
    url = "uno:socket,host=localhost,port=%d;urp;StarOffice.ComponentContext" % PORT
    last = None
    for _ in range(120):
        try:
            return resolver.resolve(url)
        except Exception as e:
            last = e
            time.sleep(0.5)
    raise RuntimeError("connect failed: %s" % last)


def main():
    import uno
    odb = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "budget.odb")
    odb_url = uno.systemPathToFileUrl(odb)

    log("spawning soffice on port %d" % PORT)
    proc = subprocess.Popen([
        SOFFICE, "--headless", "--norestore", "--invisible", "--nologo",
        "--nofirststartwizard", "-env:UserInstallation=" + PROFILE,
        "--accept=socket,host=localhost,port=%d;urp;StarOffice.ServiceManager" % PORT,
    ])
    try:
        ctx = connect(uno.getComponentContext())
        smgr = ctx.ServiceManager
        db_context = smgr.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", ctx)
        data_source = db_context.getByName(odb_url)
        db_doc = data_source.DatabaseDocument

        conn = data_source.getConnection("", "")
        stmt = conn.createStatement()

        # 1) Create/refresh the views in the embedded Firebird database.
        for name, ddl in VIEWS.items():
            stmt.execute(" ".join(ddl.split()))
            log("view %s created" % name)

        # 2) Create/refresh the wrapper queries (run SQL directly).
        queries = data_source.getQueryDefinitions()
        for name, sql in QUERIES.items():
            if queries.hasByName(name):
                queries.removeByName(name)
            qd = smgr.createInstance("com.sun.star.sdb.QueryDefinition")
            qd.setPropertyValue("Command", sql)
            qd.setPropertyValue("EscapeProcessing", False)
            queries.insertByName(name, qd)
            log("query %s added" % name)

        db_doc.store()
        log("stored")

        # 3) Prove each query executes and report row counts.
        print("== Report views/queries ==")
        for name in QUERIES:
            rs = stmt.executeQuery("SELECT COUNT(*) FROM \"%s\"" % name)
            rs.next()
            print("  %-22s %d rows" % (name, rs.getInt(1)))
        conn.close()
        return 0
    finally:
        try:
            smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx).terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
