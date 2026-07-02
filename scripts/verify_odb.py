#!/usr/bin/env python
"""verify_odb.py - open budget.odb and report tables, row counts, FK metadata,
and prove FK + CHECK constraints are enforced. Run with LibreOffice python."""
import os
import sys
import time
import subprocess

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.bin"
PORT = 2104
# Reuse the already-initialised build profile: cold first-run profile setup
# (incl. Java init) can take longer than the connect window.
PROFILE = "file:///c:/temp/lo_odb_build"


def connect(ctx_local):
    import uno
    resolver = ctx_local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", ctx_local)
    url = "uno:socket,host=localhost,port=%d;urp;StarOffice.ComponentContext" % PORT
    last = None
    for _ in range(160):
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
        conn = data_source.getConnection("", "")
        stmt = conn.createStatement()

        # Firebird stores unquoted identifiers upper-case; quoted ones
        # ("date","type","month") keep their given case.
        print("== Tables & row counts ==")
        for t in ["ACCOUNTS", "CATEGORIES", "TRANSACTIONS", "BUDGETS", "RECURRINGTRANSACTIONS"]:
            rs = stmt.executeQuery("SELECT COUNT(*) FROM %s" % t)
            rs.next()
            print("  %-22s %d rows" % (t, rs.getInt(1)))

        print("== Foreign keys (imported keys) ==")
        try:
            md = conn.getMetaData()
            for t in ["TRANSACTIONS", "BUDGETS", "RECURRINGTRANSACTIONS", "CATEGORIES"]:
                rs = md.getImportedKeys("", "PUBLIC", t)
                while rs.next():
                    print("  %s.%s -> %s.%s" % (
                        t, rs.getString(8), rs.getString(3), rs.getString(4)))
        except Exception as e:
            print("  (metadata introspection skipped: %s)" % str(e).splitlines()[0][:60])

        print("== FK enforcement (expect failure) ==")
        try:
            stmt.execute("INSERT INTO TRANSACTIONS (\"date\",ACCOUNT_ID,CATEGORY_ID,AMOUNT,\"type\") "
                         "VALUES ('2026-01-01', 999, 1, 5.00, 'Expense')")
            print("  FAIL: bad account_id was accepted!")
        except Exception as e:
            print("  OK: rejected bad account_id (%s)" % str(e).splitlines()[0][:70])

        print("== CHECK enforcement (expect failure) ==")
        try:
            stmt.execute("INSERT INTO ACCOUNTS (NAME,\"type\",STARTING_BALANCE) "
                         "VALUES ('Bad', 'Crypto', 0)")
            print("  FAIL: bad account type was accepted!")
        except Exception as e:
            print("  OK: rejected bad type (%s)" % str(e).splitlines()[0][:70])

        print("== Sample join (transactions with names) ==")
        rs = stmt.executeQuery(
            "SELECT t.\"date\", a.NAME, c.NAME, t.AMOUNT, t.\"type\" "
            "FROM TRANSACTIONS t "
            "JOIN ACCOUNTS a ON t.ACCOUNT_ID=a.ID "
            "JOIN CATEGORIES c ON t.CATEGORY_ID=c.ID ORDER BY t.\"date\"")
        while rs.next():
            print("  %s | %-16s | %-24s | %8s | %s" % (
                rs.getString(1), rs.getString(2), rs.getString(3),
                rs.getString(4), rs.getString(5)))

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
