# 0002 — Only store/ may start a process

**Decided.** A rules test fails if any package other than store/ imports subprocess or similar.

**Considered.** Allowing it where harmless (e.g. reading the git version).

**Why.** A shell command can write anywhere, which would get around the one-writer check. One exception would make the rule mean nothing, so there are none.
