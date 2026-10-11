# Repo Structure

How the code and the system's memory are laid out, and how the layout itself enforces the rules in [spec.md](../spec.md).

**Status:** Approved 2026-10-11. Revised after M0 (approved 2026-10-11): the daily run moved to GitHub Actions; Claude only reviews. See [reports/m0.md](../reports/m0.md).

---

## The tree

One repo, everything in a single tree. `main` holds both code and data. The only other branches are the ones Claude's daily review arrives on.

```
trading-agent/
├── .github/workflows/   the daily run (GitHub Actions), and the checks on every push
├── docs/          spec, plan, designs, and a log of the decisions Claude makes
├── config/        your limits, the share list, the checklists. Code can read these, never write them.
├── src/trader/
│   ├── fetch/ clean/ analyze/ decide/ record/ settle/ learn/   the seven jobs
│   ├── schema/    what the jobs pass to each other, and the check on Claude's review
│   ├── store/     the only code allowed to write to data/
│   ├── backtest/  runs the same jobs over past years
│   ├── report/    the daily report (read-only)
│   └── run.py     the one entry point the daily workflows run
├── routines/      instructions for Claude's daily review (a cloud routine)
├── tests/
└── data/          the system's memory, written only by the daily run
    ├── raw/       Fetch:   receipts: what was fetched, its checksum, and what failed (the downloads themselves are not kept; see pass4-fetch-clean.md)
    ├── history/   Clean:   verified prices, splits and bonuses, the "don't know" list
    ├── analysis/  Analyze: market mood and every check made
    ├── notebook/  Record:  decisions, skips, results
    ├── books/     Settle:  fills, holdings, balance
    ├── trust/     Learn:   trust scores, each version with its evidence, and suggestions for you
    ├── backtest/  backtest results, kept apart from the notebook
    └── reports/   the daily report, one file per day; written for you, read by nothing in the system
```

## Two rules for `data/`

1. **Only the daily run writes to it.**
2. **Nothing in it is ever changed or removed. Files only grow.** Each store adds lines to one file per month (e.g. `data/notebook/2026-10.jsonl`), which keeps every file far below GitHub's limits ([constraints.md](constraints.md)). A check confirms that no existing line was removed or changed.

## How the layout enforces the spec

| Spec rule | How the structure enforces it |
|---|---|
| One writer per fact | Each folder in `data/` has one owning job. Jobs write only through `store/`, which refuses any folder the job does not own. A test fails if any code outside `store/` writes a file. |
| The next job reads from the record, not from its neighbour | Jobs never import each other's code. They talk only through `data/` and the shapes in `schema/`. A test blocks imports between jobs. |
| Never look at the future | Every read of market data goes through `store/` with the date of the decision it feeds. Anything newer is refused. A test changes only future prices and checks that no past decision changes. |
| Your safety limits are yours | Limits live in `config/`, and `store/` has no way to write there. |
| Watchers are not jobs | `report/` gets read-only access. |
| Nothing is edited or deleted | The "files only grow" rule above, checked before every push and by a test. |
| Every change points at its evidence | Every entry records the exact code version that produced it, which always lives in this same repo. Trust-score versions link to the entries behind them. |

**Checklists** are short readable files in `config/checklists/`, built from named conditions such as "quiet for 10 days" or "volume at least 2× normal". Each has a version, and every candidate records the version that matched it.

**The backtest** feeds history through the real jobs, not a copy of them, so it tests what actually runs. It writes only to `data/backtest/`. Claude's veto is left out, because Claude already knows how past events turned out.

## The daily run

| Step | Where | What it does |
|---|---|---|
| 1. `run propose` | GitHub Actions, on a schedule | Fetch, Clean, Analyze and Decide produce the day's proposed trades, and commit them to `main`. |
| 2. Review | Cloud routine | Claude reads the proposals and writes one review file: the plain-English case, plus any vetoes with reasons. It pushes the review to a branch of its own (`claude/review-<date>`), never to `main`. |
| 3. `run finalize` | GitHub Actions, on a schedule | Takes **only the review file** from Claude's branch and checks it. Then Record, Settle and Learn run, the report is written, and the result is committed to `main`. |

The check in step 3 rejects any veto of a trade that was not proposed, any veto without a reason, and anything the review tries to add. Everything else on Claude's branch is ignored, so nothing Claude does in its session can reach the record except a review that passes this check.

If no review arrives, finalize carries on without one and records that there was none. Nothing waits for Claude, just as nothing waits for you.

Market data is fetched only by GitHub Actions. Anthropic's cloud cannot reach NSE, and the review does not need it to.

## How `main` is protected

1. **A GitHub rule on `main`** blocks pushes from everyone except you (code changes) and the finalize step.
2. **The finalize step pushes with a key that GitHub releases only to workflows running from `main`.** A workflow added on Claude's branch cannot get it.
3. **Scheduled workflows always run the version on `main`**, so the daily run cannot be swapped out from a branch.
4. **Before every push, the run checks** that nothing outside `data/` changed and nothing inside it was altered rather than added.

Points 1 and 2 are repo settings, made by you in M6 from step-by-step instructions, and each is tested before anything relies on it.

## Keeping mistakes out of a permanent record

The record cannot be edited, so bad entries are stopped before they get in:

- Every entry is checked against its format and sanity rules before it is written, and rejected if it fails.
- The permanent record starts at go-live (end of M6). Everything written during the build and the shakedown is practice and is discarded.

After go-live, a wrong entry is corrected by a new entry pointing at it, as the spec requires.
