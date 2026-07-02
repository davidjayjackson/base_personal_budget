---
name: report-builder-not-scriptable
description: "Report Builder reports can't be built via UNO here; crashes soffice"
metadata: 
  node_type: memory
  type: reference
  originSessionId: e1ed938b-9aab-4adb-b3b9-8ada4ffa523e
---

Building LibreOffice **Report Builder** reports programmatically via UNO does NOT work on this machine's LO build — it crashes soffice hard ("Binary URP bridge disposed during call") nondeterministically on a trivial setter (even `report.CommandType = QUERY`), or hangs mid-build. Tried both headless and VISIBLE soffice (2026-07 attempt) + settle delays; both crash on the first report. Crashing mid-store leaves a corrupt stub in the .odb (recover with `git checkout -- budget.odb`). Do not re-attempt scripted report generation.

API facts that ARE correct (the engine is just unstable): create via `getReportDocuments().createInstanceWithArguments("com.sun.star.sdb.DocumentDefinition", (Name, Parent, ActiveConnection, DocumentServiceName="com.sun.star.report.ReportDefinition"))`; `openDesign` command returns `com.sun.star.comp.report.OReportDefinition`; sections are ATTRIBUTES `.ReportHeader`/`.PageHeader`/`.Detail` (not getX()); add controls with `report.createInstance("com.sun.star.report.FixedText"/"FormattedField")` then `section.add(ctl)`; bind a field with `ctl.DataField = "field:[ColumnName]"`.

For actual Reports-pane reports, use the Base GUI **Report Wizard** (Reports pane > Use Wizard to Create Report > pick the Rpt* query > add all fields > Tabular > Finish) — stable where UNO is not.

CRITICAL for the wizard to work: the Report Builder engine (Pentaho/jfreereport, `StarReportDataFactory`) **re-processes the report's source SQL** and throws "Syntax error in SQL statement" on EXTRACT/CASE/COALESCE — regardless of the query's `EscapeProcessing` flag. Fix (done 2026-07, resolved): put all complex SQL in Firebird **views** (`RPT_*`, created in `build_reports.py`) and make each `Rpt*` query a trivial `SELECT * FROM <view>`. The engine then only sees a plain select it can't mangle. View column names avoid reserved words (YR/MO not YEAR/MONTH, ACCT_TYPE not TYPE). After creating reports in Base, must Ctrl+S the MAIN database window or they don't persist (learned the hard way — a first batch of wizard reports was lost by closing without saving). The 4 reports now exist in budget.odb, committed and pushed, and were VERIFIED opening with data in the Base GUI. See [[budget-odb-build-workflow]].
