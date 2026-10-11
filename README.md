# Automated Trader

A system that studies the Indian share market each evening, suggests trades for the next day or two,
records every decision, and improves by checking its own record.

It runs on fake money for the first three to four months. It never places an order — it tells you
what it would do, and you place every order yourself.

**Start here:** [docs/spec.md](docs/spec.md) — the whole system in one document: the seven jobs,
the rules that bind them, and what is still open.

## Status

Design complete. Not yet built.

Next step is a data spike: prove that daily prices, two to three years of history, and corporate
actions (splits and bonuses) can all be obtained for the chosen universe. That answers the only
open question that could still change the design.

## Build order

Dependency-first, which is not the same as the design order in the spec. You cannot settle a trade
before you have a price.

1. One thin slice end to end — fetch, clean, one checklist, decide with fixed sizing, record, settle.
2. Learn, once the notebook has entries to read.

A run over historical data is for debugging the plumbing only. The record that counts is built
forward, day by day, because every bug that leaks tomorrow's prices into today's decision makes a
backtest look brilliant.
