# 0012 — The daily report is saved in data/reports/

**Decided.** The report is written to `data/reports/<month>/<date>.md` by the run, through a writer owned by "report". A rules test fails if any job reads that folder.

**Considered.** Keeping the report only in the workflow's log, or outside `data/`.

**Why.** It has to be saved somewhere you can open it, from your phone too, and the run only pushes `data/`. Nothing in the system reads it, so it stays a watcher, as the spec requires.
