# Automated Trader

A system that studies the Indian share market each evening, suggests trades for the next day or two,
records every decision, and improves by checking its own record.

It runs on fake money for the first three to four months. It never places an order — it tells you
what it would do, and you place every order yourself.

**Start here:** [docs/spec.md](docs/spec.md) — the whole system in one document: the seven jobs,
the rules that bind them, and what is still open.

## Status

M0–M4 are complete: foundations, the full design, and the full system (all seven jobs, the evening run, Claude's review check, the daily report), with market history from January 2024 in `data/history/`. Next: M5, the backtest and go/no-go. Reports: [docs/reports/](docs/reports/). Milestones: [docs/plan.md](docs/plan.md).

## Try it

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python src/trader/run.py replay 2025-01-01 2025-03-31 --into /tmp/practice
```

## Build order

Milestones M0–M7 in [docs/plan.md](docs/plan.md). Dependency-first, which is not the same as the
design order in the spec: you cannot settle a trade before you have a price.

A backtest over history sets only the starting trust scores, and the paper-trading record overrides
them. The record that counts is built forward, day by day, because every bug that leaks tomorrow's
prices into today's decision makes a backtest look brilliant. A test guards against exactly that.
