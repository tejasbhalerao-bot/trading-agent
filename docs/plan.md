# Milestone Plan

How the system described in [spec.md](spec.md) gets built and proven, from an empty repo to a decision on real money.

**Status:** Signed off 2026-10-11. M0 complete; awaiting checkpoint decisions ([reports/m0.md](reports/m0.md)).

Claude designs and builds end to end. You check in only at the end of each milestone, when Claude stops, reports, and brings the decisions that need you, each with its tradeoffs and a recommendation.

Milestones M0–M6 are building and take days to a couple of weeks, depending mostly on how easily the data can be fetched. M7 is the paper-trading period, which is fixed at three to four months and cannot be compressed.

---

## Decisions already made

| Decision | Choice |
|---|---|
| Where it runs | Claude Code cloud routines, not a local machine. Each run works on a fresh copy of this repo and saves its results back to it. |
| Language model | No API key. The routine's own Claude session writes the plain-English case and may veto a trade. Code checks its output, so it can never invent a trade. |
| Backtest | Allowed, with limits: see M5. |
| Repo structure | One repo, one branch. See [design/repo-structure.md](design/repo-structure.md). |

---

## Milestones

### M0 — Foundations and data check

**What gets done.** The repo laid out as designed in [design/repo-structure.md](design/repo-structure.md): the Python project, the test setup, and the checks that enforce the structure, including the one that rejects any change to `data/` other than added lines. A test that cloud routines can be limited to the two run commands and one review file. Then a one-time cloud routine checks whether we can get daily NSE/BSE prices, five or more years of history (enough to cover different market moods, including 2020), corporate actions, and the index member lists. The same run checks that the cloud can reach those sources and push results back to the repo.

**What it unlocks.** Proof that the system can be built where it will run. Everything after this assumes it can.

**Your decisions.** Data source; which shares to watch (top 100 or top 500); the minimum trading volume a share needs; whether the cloud setup holds up or we need a fallback.

### M1 — Design Pass 1: Decide, Record, Learn

**What gets done.** The detailed design for the core loop: the notebook format, how confidence is worked out, how trust scores update, how Claude's veto works and is checked, and how backtest results seed the starting trust scores without counting as real results.

**What it unlocks.** The spec's central bet becomes concrete enough to build and test: can the notebook improve future decisions?

**Your decisions.** Safety limits (risk per trade, maximum open positions, stop-loss rules); how confidence is worked out; the rules for the veto.

### M2 — Design Passes 2–4: Settle, Analyze, Fetch and Clean

**What gets done.** How fake fills are worked out, including gap opens and days when both the stop and the target were touched. The market-mood definition and the first set of checklists, kept deliberately small. Data cleaning and corporate-action handling. These passes are smaller, so they share one review.

**What it unlocks.** A complete design. Building starts with no open questions.

**Your decisions.** The first set of checklists and the market-mood definition.

### M3 — Thin slice, end to end

**What gets done.** Fetch → clean → one checklist → decide with fixed trade sizes → record → settle, run over past days. A test that fails if a decision changes when future prices change.

**What it unlocks.** The plumbing is proven before any learning is layered on top. Bugs are found here, where they are cheap to fix.

**Your decisions.** None. A report only.

### M4 — Full system

**What gets done.** All the checklists, market-mood detection, Decide with trade sizing inside your limits, exits on open positions, Learn with the confidence check, Claude's written case and veto, and the daily report.

**What it unlocks.** A complete system, ready to backtest.

**Your decisions.** How the daily report looks (you get a sample).

### M5 — Backtest and starting trust scores

**What gets done.** The rules are run over history and produce discounted starting trust scores. Any checklist that loses money after an estimate of costs is dropped.

Two limits keep the backtest honest:

- **It gives starting trust scores, and the notebook overrides them.** Backtest results stay separate from the notebook and count for less, much as the spec treats checks on shares we never bought. Paper-trading results take over as they arrive.
- **Claude's veto stays out of the backtest.** Claude already knows how past market events turned out, so any Claude judgment on historical data is looking at the future. The backtest tests the rules only.

**What it unlocks.** The system starts paper trading with sensible starting trust scores, not empty ones.

**Your decisions.** A real go/no-go. If no checklist makes money after costs, Claude stops and brings options instead of starting paper trading.

### M6 — Go live on paper

**What gets done.** The daily cloud routine (weekdays at 8pm IST), a catch-up routine at 10pm that does nothing if the day's run already finished, and a weekly health check. A two-week shakedown, fixing whatever breaks.

**What it unlocks.** The system runs every day without you or Claude.

**Your decisions.** Confirm the shakedown went cleanly.

### M7 — Paper-trading period (three to four months)

**What gets done.** The system runs daily, with a monthly health report. At the end comes the test the spec defines: was its confidence honest, did it behave properly through losing runs, and was the share of unknown results low enough that the record measures the market rather than our own assumptions?

**What it unlocks.** Your decision on real money. Even then, it only suggests trades and you place every order.

---

## What sign-off covers

- Committing and pushing to `main` on this repo, by Claude and by the routines.
- Creating the cloud routines named in M0 and M6 on your account, using Sonnet 5.5.
- Claude making the calls inside each milestone. Each one is logged in the repo with its reasoning, for review at the checkpoint.

## When Claude stops early, even mid-milestone

- The data check fails, or the cloud cannot reach the data or push to the repo.
- Cloud routines cannot be limited to the two run commands and one review file.
- A design problem would require changing the spec. Under its own rules, the spec reopens rather than being quietly worked around.
- Anything would need access beyond this repo and the routines named above.

## Before M0

Confirm the GitHub repo is private. It will hold the trading notebook.
