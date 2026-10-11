# Platform Constraints

The hard limits of everything the system runs on, and how the design stays inside each. Where a limit can be checked automatically, a test does it.

**Status:** Added in M4 (2026-10-11). Update whenever a new store, schedule or integration is added.

---

## GitHub: storage

| Limit | Value | How the design stays inside it | Checked by |
|---|---|---|---|
| Single file | Warning at 50 MB, **blocked at 100 MB** | Every growing data file holds **one month**, e.g. `data/history/prices/2026-10.csv` (about 3 MB) and `data/analysis/2026-10.jsonl` (about 6 MB). | A test fails if any file under `data/` exceeds 25 MB. |
| Repo size | Recommended under 1 GB, strongly under 5 GB; hard ceiling 10 GB (compressed) | About 40 MB compressed now; about 150 MB after the 2015–2023 backfill (M5); then about 40 MB per year. Under 1 GB for about 20 years. | The weekly health check reports the size (M6). |
| Single push | 2 GB | The largest push is the one-time backfill, about 250 MB. | — |

## GitHub Actions

| Limit | Value | How the design stays inside it |
|---|---|---|
| Minutes | Unlimited for a public repo; **2,000 a month if private** | About 300 minutes a month (one run of about 8 minutes per calendar day, plus checks). Fits even if the repo goes private. |
| Scheduled runs start late | Delays at busy times, worst at the top of the hour; under heavy load **queued runs can be dropped** | Schedules use odd minutes (e.g. :17). Each step is scheduled **several times** in its window, and a run that finds the day already done exits at once. |
| Schedules switched off | In a public repo, after **60 days with no activity** | The daily run commits every evening, which counts as activity. The weekly health check flags a stopped schedule. |
| Pushes by the workflow trigger nothing | Pushes made with the workflow's own token start no other workflows | The data checks run **inside** the run before it pushes (`store/publish.py`), not only in the separate checks workflow. |
| Job time limit | 6 hours | A run takes minutes. The one-time backfill runs in chunks. |
| Runs only from `main` | Scheduled workflows run the version on `main` | That is the protection the design relies on: a branch cannot swap the daily run. |

## Cloud routine (Claude's review)

| Limit | Value | How the design stays inside it |
|---|---|---|
| Internet access | A fixed list of sites; **NSE is blocked** | The review needs only the repo. All market data comes via GitHub Actions. |
| Schedule | At most once an hour; times in UTC | One review per evening, timed between propose and finalize. |
| Writing to the repo | Through the Claude GitHub App (installed) | Reviews go to a branch of their own (`claude/review-<date>`); finalize reads only the review file from it. |
| Tool limits do not hold | `allowed_tools` auto-approves; it does not restrict | Safety does not depend on them: nothing from the review reaches the record except a review file that passes a code check. |
| Usage | Counts against your Claude plan | One short session a day. |

## NSE

| Limit | Value | How the design stays inside it |
|---|---|---|
| Publishing time | Daily file at about 4:35pm IST | The evening run starts at 6:00pm IST and retries until 9:00pm. |
| Weekend sessions | Occasional (Budget-day Saturdays, special sessions) | Fetch tries every calendar day; a missing file on a weekend means closed. |
| IPv6 | Hung for 30 seconds per request on some networks | IPv4 only, short timeouts. |
| Politeness | Unpublished, but heavy scraping risks being blocked | One request at a time, with a pause between requests; about 3 requests a day when live. |
| Format changes | NSE changed its file format in July 2024 | Both formats are read and tested to give identical rows. A new change would show up as a failed day with reasons on the receipt. |

## The evening timetable (IST, with UTC)

| Step | Scheduled | Window | Why |
|---|---|---|---|
| Propose | 18:17, 19:17, 20:17 (12:47, 13:47, 14:47 UTC) | 18:00–21:00 | NSE is usually out by 4:35pm. Three tries survive one dropped run. |
| Claude's review | 21:17 (15:47 UTC) | — | After the last propose slot. |
| Finalize | 22:17, 23:17 (16:47, 17:47 UTC) | until midnight | After the review. Carries on without one if none arrived. |

If propose has not succeeded by 21:00, the day is marked failed, and the next evening catches it up.
