# Automated Trader

A system that studies the Indian share market each evening, suggests trades for the next day or two,
records every decision, and improves by checking its own record.

It runs on fake money for the first three to four months. It never places an order — it tells you
what it would do, and you place every order yourself.

**Start here:** [docs/spec.md](docs/spec.md) — the whole system in one document: the seven jobs,
the rules that bind them, and what is still open.

**Daily reports:** [data/reports/](data/reports/), one file per trading day, e.g.
`data/reports/2026-10/2026-10-12.md`. They start when paper trading goes live (M6). Until then, see the
[sample report](docs/reports/m4-sample-daily-report.md) and
[how to read the daily report](docs/how-to-read-the-daily-report.md).

## Status

M0–M5 are complete. The M5 backtest over 2015–2026 found that none of the checklists makes money once trading costs are counted, so paper trading has **not** started. See [docs/reports/m5.md](docs/reports/m5.md) for the result and the options. Reports: [docs/reports/](docs/reports/). Milestones: [docs/plan.md](docs/plan.md).

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
