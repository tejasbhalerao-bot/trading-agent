# Automated Trader

A system that studies the Indian share market each evening, suggests trades for the next day or two,
records every decision, and improves by checking its own record.

It runs on fake money for the first three to four months. It never places an order — it tells you
what it would do, and you place every order yourself.

**Start here:** [docs/spec.md](docs/spec.md) — the whole system in one document: the seven jobs,
the rules that bind them, and what is still open.

## Status

M0 (foundations and data check) and M1 (design of Decide, Record and Learn) are complete. M2 (design of Settle, Analyze, Fetch and Clean) is complete and awaiting decisions. Reports: [docs/reports/](docs/reports/). Milestones: [docs/plan.md](docs/plan.md).

## Build order

Milestones M0–M7 in [docs/plan.md](docs/plan.md). Dependency-first, which is not the same as the
design order in the spec: you cannot settle a trade before you have a price.

A backtest over history sets only the starting trust scores, and the paper-trading record overrides
them. The record that counts is built forward, day by day, because every bug that leaks tomorrow's
prices into today's decision makes a backtest look brilliant. A test guards against exactly that.
