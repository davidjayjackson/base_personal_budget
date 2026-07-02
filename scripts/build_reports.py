#!/usr/bin/env python
"""build_reports.py - add the analytical report queries to budget.odb.

Base reports are built on top of queries; these saved queries are the report
data sources (and are directly viewable under "Queries" in Base):

    RptMonthlySpending     - monthly spending by category (expenses)
    RptBudgetVsActual      - planned vs. actual spend per category/month
    RptAccountBalances     - account balance summary (starting + net activity)
    RptIncomeExpenseTrend  - income vs. expense trend by month

Run with LibreOffice's bundled Python (needs the `uno` module):

    "C:\\Program Files\\LibreOffice\\program\\python.exe" scripts\\build_reports.py

Re-running replaces any queries of the same name.
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


# Firebird dialect. Quoted lowercase identifiers ("date","type","month")
# keep their case; everything else is folded to upper-case.
QUERIES = {
    "RptMonthlySpending": """
        SELECT EXTRACT(YEAR  FROM t."date") AS "Year",
               EXTRACT(MONTH FROM t."date") AS "Month",
               c.name                       AS "Category",
               SUM(t.amount)                AS "Spent"
        FROM   transactions t
               JOIN categories c ON t.category_id = c.id
        WHERE  t."type" = 'Expense'
        GROUP  BY EXTRACT(YEAR FROM t."date"),
                  EXTRACT(MONTH FROM t."date"),
                  c.name
        ORDER  BY 1, 2, 4 DESC
    """,
    "RptBudgetVsActual": """
        SELECT c.name            AS "Category",
               b."month"         AS "BudgetMonth",
               b.planned_amount  AS "Planned",
               COALESCE(SUM(t.amount), 0)                    AS "Actual",
               b.planned_amount - COALESCE(SUM(t.amount), 0) AS "Remaining"
        FROM   budgets b
               JOIN categories c ON b.category_id = c.id
               LEFT JOIN transactions t
                      ON t.category_id = b.category_id
                     AND t."type" = 'Expense'
                     AND EXTRACT(YEAR  FROM t."date") = EXTRACT(YEAR  FROM b."month")
                     AND EXTRACT(MONTH FROM t."date") = EXTRACT(MONTH FROM b."month")
        GROUP  BY c.name, b."month", b.planned_amount
        ORDER  BY b."month", c.name
    """,
    "RptAccountBalances": """
        SELECT a.name             AS "Account",
               a."type"           AS "Type",
               a.starting_balance AS "StartingBalance",
               COALESCE(SUM(CASE WHEN t."type" = 'Income'  THEN  t.amount
                                 WHEN t."type" = 'Expense' THEN -t.amount
                                 ELSE 0 END), 0)                        AS "NetActivity",
               a.starting_balance
                 + COALESCE(SUM(CASE WHEN t."type" = 'Income'  THEN  t.amount
                                     WHEN t."type" = 'Expense' THEN -t.amount
                                     ELSE 0 END), 0)                    AS "CurrentBalance"
        FROM   accounts a
               LEFT JOIN transactions t ON t.account_id = a.id
        GROUP  BY a.name, a."type", a.starting_balance
        ORDER  BY a.name
    """,
    "RptIncomeExpenseTrend": """
        SELECT EXTRACT(YEAR  FROM t."date") AS "Year",
               EXTRACT(MONTH FROM t."date") AS "Month",
               SUM(CASE WHEN t."type" = 'Income'  THEN t.amount ELSE 0 END) AS "Income",
               SUM(CASE WHEN t."type" = 'Expense' THEN t.amount ELSE 0 END) AS "Expense",
               SUM(CASE WHEN t."type" = 'Income'  THEN t.amount ELSE 0 END)
                 - SUM(CASE WHEN t."type" = 'Expense' THEN t.amount ELSE 0 END) AS "Net"
        FROM   transactions t
        GROUP  BY EXTRACT(YEAR FROM t."date"), EXTRACT(MONTH FROM t."date")
        ORDER  BY 1, 2
    """,
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

        queries = data_source.getQueryDefinitions()
        for name, sql in QUERIES.items():
            clean = " ".join(sql.split())
            if queries.hasByName(name):
                queries.removeByName(name)
            qd = smgr.createInstance("com.sun.star.sdb.QueryDefinition")
            qd.setPropertyValue("Command", clean)
            qd.setPropertyValue("EscapeProcessing", True)
            queries.insertByName(name, qd)
            log("query %s added" % name)

        db_doc.store()
        log("stored")

        # Prove each query executes and report row counts.
        conn = data_source.getConnection("", "")
        stmt = conn.createStatement()
        print("== Report queries ==")
        for name, sql in QUERIES.items():
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
