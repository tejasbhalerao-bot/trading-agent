# 0010 — Fetch tries every calendar day, weekends included

**Decided.** Fetch asks NSE for a price file every day. A missing file on a past date means the market was closed.

**Considered.** Weekdays only.

**Why.** NSE holds occasional weekend sessions (a special Saturday session on 18 May 2024, Budget-day Saturdays, Diwali's Muhurat session). Missing one broke the previous-close check for every share the next trading day: 1,845 false "don't know"s in the M3 trial.
