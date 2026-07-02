---
name: headless-forms-uno-gotchas
description: Pitfalls when creating Base form documents headlessly via UNO
metadata: 
  node_type: memory
  type: reference
  originSessionId: e1ed938b-9aab-4adb-b3b9-8ada4ffa523e
---

Creating embedded Base form documents headlessly via UNO (see [[budget-odb-build-workflow]], `build_forms.py`) required these non-obvious fixes:

- Create the form def via `form_docs.createInstanceWithArguments("com.sun.star.sdb.DocumentDefinition", (NamedValues...))` — the service specifier is a required first arg; NamedValues carry `Name`, `Parent`, `ActiveConnection`. Do NOT pass a `URL`/`private:factory/swriter` arg → causes ErrorCodeIOException.
- Open for editing with the **`openDesign` command** via the definition's XCommandProcessor (`definition.execute(cmd, createCommandIdentifier(), None)`); plain `definition.open()` throws WrappedTargetException on a fresh empty def.
- The opened component exposes `getDrawPages()` (plural), not `getDrawPage()` — use `getDrawPages().getByIndex(0)`.
- **Never call `component.store()`** on the embedded form — it segfaults soffice (Binary URP bridge disposed). Persist by executing the `store` then `close` commands on the *definition* (the "document holder"), then `db_doc.store()`.
- `ActiveConnection` can be set at creation but is NOT settable on a definition fetched later via `getByName` (UnknownPropertyException).
- Grid ListBox (dropdown) columns: `createColumn("ListBox")`, `ListSourceType = SQL`, `ListSource = ("SELECT name,id FROM ...",)` (tuple), `BoundColumn = 2` to store id / show name. VERIFIED in the Base GUI: dropdowns display the names correctly, so `BoundColumn = 2` is right for a `SELECT name,id` list source.
