#!/usr/bin/env python
"""verify_forms.py - reopen each form document in budget.odb and report its
bound table plus grid columns (proving the forms persisted correctly)."""
import os
import sys
import time
import subprocess

SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.bin"
PORT = 2107
PROFILE = "file:///c:/temp/lo_odb_build"


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
    from com.sun.star.ucb import Command
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
        db_doc = data_source.DatabaseDocument
        conn = data_source.getConnection("", "")
        form_docs = db_doc.getFormDocuments()

        print("== Form documents ==")
        for name in form_docs.getElementNames():
            definition = form_docs.getByName(name)
            cmd = Command()
            cmd.Name = "openDesign"
            cmd.Handle = -1
            cmd.Argument = None
            comp = definition.execute(cmd, definition.createCommandIdentifier(), None)
            try:
                dp = comp.getDrawPage() if hasattr(comp, "getDrawPage") \
                    else comp.getDrawPages().getByIndex(0)
                mainform = dp.getForms().getByName("MainForm")
                grid = mainform.getByName("Grid")
                cols = []
                for cn in grid.getElementNames():
                    c = grid.getByName(cn)
                    kind = "dropdown" if c.getPropertySetInfo().hasPropertyByName(
                        "ListSource") else "text"
                    cols.append("%s(%s)" % (cn, kind))
                print("  %-18s -> %-22s [%s]" % (
                    name, mainform.Command, ", ".join(cols)))
            finally:
                close_cmd = Command()
                close_cmd.Name = "close"
                close_cmd.Handle = -1
                try:
                    definition.execute(close_cmd, definition.createCommandIdentifier(), None)
                except Exception:
                    pass
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
