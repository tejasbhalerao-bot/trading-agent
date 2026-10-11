# 0003 — GitHub checks on every push

**Decided.** Every push runs the full test suite and the "data files only grow" check (.github/workflows/checks.yml).

**Considered.** Running checks only inside the daily run.

**Why.** The daily run already checks before it pushes. This catches the same problems in pushes from anywhere else, including Claude's code pushes. It does not block a push; the run's own check is what prevents a bad one.
