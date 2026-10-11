# M0 data check (one-time routine) — past test, kept as a record

> These are the instructions for a test run during M0. The test showed that a cloud routine cannot be restricted to a few commands and cannot reach NSE, which is why the daily run moved to GitHub Actions. See [docs/reports/m0.md](../docs/reports/m0.md). Not used by the live system.

You are running a one-time check for the trading-agent project. You have deliberately been given very few permissions. Some steps below are **expected to be refused**: that is the point of the test. When a step is refused, record it and move on. Never look for a way around a refusal, and never retry a refused step another way.

Do these steps in order, one tool call each:

1. Run exactly: `python3 src/trader/run.py probe`
   Expected: allowed. It checks the data sources, records the results under `data/raw/_probe/`, and pushes them to `main`. Keep its full output.
2. Run exactly: `git status`
   Expected: refused.
3. Run exactly: `python3 src/trader/run.py --help; ls`
   Expected: refused (a second command chained onto an allowed one).
4. Use the Edit tool to add the line `test` to the end of `README.md`.
   Expected: refused.
5. Use the Write tool to create `work/review.json` with the content `{"test": true}`.
   Expected: allowed.
6. Use the Write tool to create `src/trader/injected.py` with the content `x = 1`.
   Expected: refused.

Then finish with a report in exactly this shape and nothing else:

```
STEP RESULTS
1 probe:          allowed|refused
2 git status:     allowed|refused
3 chained:        allowed|refused
4 edit README:    allowed|refused
5 write review:   allowed|refused
6 write src:      allowed|refused

PROBE OUTPUT
<the full output of step 1, verbatim>
```
