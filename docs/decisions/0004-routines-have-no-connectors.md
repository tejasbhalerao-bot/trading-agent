# 0004 — Routines get no claude.ai connectors

**Decided.** Every routine is created with no connectors attached.

**Considered.** Leaving the defaults.

**Why.** On creation the server attached every connector on the account (Gmail, Slack, Drive, Calendar and others) to the M0 routine. The system needs none of them, and a session with fewer abilities has fewer ways to go wrong. If a report ever needs to reach you by email or Slack, that will be a separate decision.
