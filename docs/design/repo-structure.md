# Repo Structure

How the code and the system's memory are laid out, and how the layout itself enforces the rules in [spec.md](../spec.md).

**Status:** Approved 2026-10-11.

---

## The tree

One repo, one branch, everything in a single tree.

```
trading-agent/
├── docs/          spec, plan, designs, and a log of the decisions Claude makes
├── config/        your limits, the share list, the checklists. Code can read these, never write them.
├── src/trader/
│   ├── fetch/ clean/ analyze/ decide/ record/ settle/ learn/   the seven jobs
│   ├── schema/    what the jobs pass to each other
│   ├── store/     the only code allowed to write to data/
│   ├── backtest/  runs the same jobs over past years
│   ├── report/    daily report and health check (read-only)
│   └── run.py     what the daily routine runs
├── routines/      instructions for each cloud routine
├── tests/
└── data/          the system's memory, written only by the daily run
    ├── raw/       Fetch:   downloads exactly as received, with receipts
    ├── history/   Clean:   verified prices, splits and bonuses, the "don't know" list
    ├── analysis/  Analyze: market mood and every check made
    ├── notebook/  Record:  decisions, skips, results
    ├── books/     Settle:  fills, holdings, balance
    ├── trust/     Learn:   trust scores, each version with its evidence
    └── backtest/  backtest results, kept apart from the notebook
```

## Two rules for `data/`

1. **Only the daily run writes to it.**
2. **Nothing in it is ever changed or removed. Files only grow.** Each store adds lines to one file per year, and a check confirms that no existing line was removed or changed.

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

## The daily run, and what the routine may do

1. `run propose`: Fetch, Clean, Analyze and Decide produce the day's proposed trades.
2. The routine's Claude reads them and writes one review file: the plain-English case, plus any vetoes with reasons.
3. `run finalize`: checks the review, rejecting any veto of a trade that was not proposed, any veto without a reason, and any addition. Then Record, Settle and Learn run, and the run commits and pushes.

The routine is allowed only those two commands and that one file. It has no git and no code editor, so it cannot touch code. The run refuses to push if anything outside `data/` changed, or anything inside it was altered rather than added.

**To verify in M0:** that cloud routines support this level of tool restriction. If they do not, Claude reports back before going further.

## Keeping mistakes out of a permanent record

The record cannot be edited, so bad entries are stopped before they get in:

- Every entry is checked against its format and sanity rules before it is written, and rejected if it fails.
- The permanent record starts at go-live (end of M6). Everything written during the build and the shakedown is practice and is discarded.

After go-live, a wrong entry is corrected by a new entry pointing at it, as the spec requires.
