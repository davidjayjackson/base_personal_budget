#!/usr/bin/env python
"""build_forms.py - create the data-entry form documents inside budget.odb.

Each form is an embedded form document holding a DataForm bound to one table
plus a GridControl for add/edit/delete. Foreign-key columns on the transaction
and recurring forms are ListBox (dropdown) columns that show the human-readable
Account / Category name while storing the id.

    TransactionEntry   -> Transactions   (account + category dropdowns)
    Accounts           -> Accounts
    Categories         -> Categories
    RecurringSetup     -> RecurringTransactions (account + category dropdowns)

Run with LibreOffice's bundled Python (needs the `uno` module):

    "C:\\Program Files\\LibreOffice\\program\\python.exe" scripts\\build_forms.py

Re-running replaces any form documents of the same name.
"""
import os
import sys
import time
import subprocess

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.bin"
PORT = 2106
PROFILE = "file:///c:/temp/lo_odb_build"


def log(msg):
    sys.stderr.write("[build_forms] %s\n" % msg)
    sys.stderr.flush()


# Per-form definition: table + ordered column list.
# Each column is (data_field, label) for a plain column, or
# (data_field, label, list_sql) for a dropdown bound to list_sql
# ("SELECT display, value ...", value stored via BoundColumn=2).
CAT_SQL = 'SELECT "name","id" FROM "CATEGORIES" ORDER BY "name"'
ACCT_SQL = 'SELECT "name","id" FROM "ACCOUNTS" ORDER BY "name"'

FORMS = [
    ("TransactionEntry", "TRANSACTIONS", [
        ("date", "Date"),
        ("account_id", "Account", ACCT_SQL),
        ("category_id", "Category", CAT_SQL),
        ("amount", "Amount"),
        ("description", "Description"),
        ("type", "Type"),
    ]),
    ("Accounts", "ACCOUNTS", [
        ("name", "Name"),
        ("type", "Type"),
        ("starting_balance", "Starting Balance"),
    ]),
    ("Categories", "CATEGORIES", [
        ("name", "Name"),
        ("parent_category_id", "Parent", CAT_SQL),
        ("kind", "Kind"),
    ]),
    ("RecurringSetup", "RECURRINGTRANSACTIONS", [
        ("description", "Description"),
        ("amount", "Amount"),
        ("frequency", "Frequency"),
        ("category_id", "Category", CAT_SQL),
        ("account_id", "Account", ACCT_SQL),
        ("next_due_date", "Next Due Date"),
    ]),
]


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


def nv(name, value):
    from com.sun.star.beans import NamedValue
    n = NamedValue()
    n.Name = name
    n.Value = value
    return n


def build_form(smgr, form_docs, conn, name, table, columns):
    import uno
    from com.sun.star.sdb.CommandType import TABLE
    from com.sun.star.form.ListSourceType import SQL as LST_SQL
    from com.sun.star.awt import Size, Point

    if form_docs.hasByName(name):
        form_docs.removeByName(name)

    # Create an empty form document inside the .odb.
    definition = form_docs.createInstanceWithArguments(
        "com.sun.star.sdb.DocumentDefinition", (
            nv("Name", name),
            nv("Parent", form_docs),
            nv("ActiveConnection", conn),
        ))
    form_docs.insertByName(name, definition)

    # Open it in design mode (via the command processor) to obtain the
    # editable Writer component that hosts the form.
    from com.sun.star.ucb import Command
    cmd = Command()
    cmd.Name = "openDesign"
    cmd.Handle = -1
    cmd.Argument = None
    try:
        component = definition.execute(cmd, definition.createCommandIdentifier(), None)
    except Exception as e:
        inner = getattr(e, "TargetException", None)
        raise RuntimeError("openDesign failed for %s: %r / inner=%r" % (name, e, inner))
    try:
        if hasattr(component, "getDrawPage"):
            draw_page = component.getDrawPage()
        else:
            draw_page = component.getDrawPages().getByIndex(0)
        forms = draw_page.getForms()

        data_form = component.createInstance("com.sun.star.form.component.DataForm")
        data_form.Command = table
        data_form.CommandType = TABLE
        forms.insertByName("MainForm", data_form)

        grid = component.createInstance("com.sun.star.form.component.GridControl")
        grid.Name = "Grid"
        data_form.insertByName("Grid", grid)

        for col in columns:
            field, label = col[0], col[1]
            list_sql = col[2] if len(col) > 2 else None
            if list_sql:
                gc = grid.createColumn("ListBox")
                gc.ListSourceType = LST_SQL
                gc.ListSource = (list_sql,)
                gc.BoundColumn = 2          # store 2nd result column (id)
            else:
                gc = grid.createColumn("TextField")
            gc.DataField = field
            gc.Label = label
            gc.Name = field
            grid.insertByName(field, gc)

        # Place the grid on the page.
        shape = component.createInstance("com.sun.star.drawing.ControlShape")
        shape.setSize(Size(26000, 12000))
        shape.setPosition(Point(500, 500))
        shape.setControl(grid)
        draw_page.add(shape)

        log("form %s built (%d columns)" % (name, len(columns)))
    finally:
        # Embedded documents must be closed through the definition, not the
        # component itself (the definition is the "document holder").
        store_cmd = Command()
        store_cmd.Name = "store"
        store_cmd.Handle = -1
        close_cmd = Command()
        close_cmd.Name = "close"
        close_cmd.Handle = -1
        try:
            definition.execute(store_cmd, definition.createCommandIdentifier(), None)
        except Exception:
            pass
        try:
            definition.execute(close_cmd, definition.createCommandIdentifier(), None)
        except Exception:
            pass


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

        form_docs = db_doc.getFormDocuments()
        for name, table, columns in FORMS:
            build_form(smgr, form_docs, conn, name, table, columns)

        db_doc.store()
        log("stored")

        print("== Form documents ==")
        for n in form_docs.getElementNames():
            print("  %s" % n)
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
