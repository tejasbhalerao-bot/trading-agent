# 0009 — Practice runs are written outside the repo

**Decided.** Replays over past days write their notebook, books and analysis to a separate folder, not to `data/`. Only real market history (and Fetch's receipts) goes into the repo before go-live.

**Considered.** Writing practice output to `data/` and deleting it at go-live.

**Why.** The record in `data/` should only ever hold the system's real paper-trading decisions. Keeping practice out from the start means nothing has to be deleted later, and nothing practice-made can be mistaken for the record.
