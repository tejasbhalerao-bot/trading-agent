# Design Pass 3: Analyze

How the system decides which shares to look at, reads the market's mood, and checks every share against every checklist. Analyze reports facts only. It never ranks or scores; choosing is Decide's job.

**Status:** Draft for approval at the end of M2. Open choices are marked **[your call]** and listed in [reports/m2.md](../reports/m2.md).

Background: [spec.md](../spec.md), [pass1-decide-record-learn.md](pass1-decide-record-learn.md).

---

## Words used here

| Word | Meaning |
|---|---|
| Universe | The shares the system may look at this month. |
| Moving average | The average closing price over the last N trading days. "50-day average" = the average of the last 50 closes. |
| Typical daily move | The average size of a share's daily price swing over the last 14 trading days, including overnight gaps. Traders call it ATR. |
| Average volume | The average number of shares traded per day over the previous 20 trading days. |
| Checklist | A set of yes/no conditions that must all be true, plus where the stop and target go. |
| Candidate | A share that met every condition of a checklist today. |

---

## The universe

On the first trading day of each month, the universe becomes the **500 ordinary shares with the highest median daily traded value over the previous 60 trading days**, counting only shares with at least 60 days of history. It is built from NSE's own daily files, so live trading and the backtest use exactly the same rule, and there is no bias from today's index lists.

## Market mood [your call]

Recommended rule, from the Nifty 500 index:

| Mood | When |
|---|---|
| **Up** | The index closes above its 50-day average, **and** that average is higher than it was 10 trading days ago. |
| **Down** | The index closes below its 50-day average, **and** that average is lower than it was 10 trading days ago. |
| **Sideways** | Anything else. |

What it gives over 2015–2026 (2,633 trading days):

| | Up | Down | Sideways |
|---|---|---|---|
| Share of days | 59% | 22% | 20% |

- A mood lasts about 15 trading days on average. Half of all spells are 6 days or shorter, so it reacts within a week or two.
- The split is steady across 2015–19, 2020–22 and 2023–26.

**Alternative:** mood from breadth, i.e. the share of our 500 stocks closing above their own 50-day average (above 60% = up, below 40% = down). It needs no index file, but is harder to picture than "the market is above its average and rising".

## Rules every checklist shares

A share is only checked if, today:
- it is in this month's universe;
- it has at least 60 trading days of clean history;
- it traded freely: the day's high and low differ (not stuck at a price limit);
- no split, bonus, demerger or scheme takes effect within the next 4 trading days, the longest a trade could be open.

**Exits, the same for every checklist:**
- **Stop:** today's close minus one typical daily move.
- **Target:** today's close plus 1.5 typical daily moves.
- **Time limit:** 3 trading days.

The same exits everywhere keep the checklists comparable, and keep any difference in results down to the entry conditions.

## The first checklists [your call]

Three well-known patterns, all buys (cash trading cannot sell short). Each condition is a yes or no answered from the numbers alone.

### 1. Quiet breakout (`quiet-breakout-v1`)
The spec's own example.
1. **Quiet for two weeks:** over the previous 10 trading days, the highest high is no more than 8% above the lowest low.
2. **Breaks out:** today's close is above that 10-day high.
3. **On heavy volume:** today's volume is at least 2× average volume.

### 2. Pullback in an uptrend (`uptrend-pullback-v1`)
1. **Uptrend:** today's close is above the 50-day average, and that average is higher than 10 trading days ago.
2. **Pulled back:** the share closed lower on each of the last 3 days.

### 3. Gap up that holds (`gap-up-holds-v1`)
1. **Gapped up:** today's open is at least 3% above yesterday's close.
2. **Held the gain:** today's close is at or above today's open, and in the top quarter of the day's range.
3. **On heavy volume:** today's volume is at least 3× average volume.

**How the thresholds were chosen.** From the usual published versions of these patterns, and from how often they fire. **Never from profit.** No profit figure was computed in choosing them. Profitability is first measured in M5's backtest. Any change after that is a new version, measured from scratch.

**How often they fire** (top 500, July 2023 to October 2026, 790 trading days; no profit figures computed):

| Checklist | Matches per day | Days with no match | Results that would be unknown | Too expensive for the ₹2,000 limit |
|---|---|---|---|---|
| Quiet breakout | about 4 | 18% | 0.5% | 25% |
| Pullback in an uptrend | about 18 | 3% | 0.1% | 22% |
| Gap up that holds | about 0.4 | 74% | 1.4% | 24% |

What this means:
- **There will be more candidates than room.** With 5 positions held up to 3 days, about 2 new trades a day are possible. Decide's ranking decides which.
- **Pullbacks will dominate the candidates;** gap-ups will be rare. Over paper trading, gap-ups may produce only about 10 trades, so their trust will lean on their backtest record and the overall record.
- **Unknown results will be rare** (under 1.5%), which matters for the spec's final test.
- **About 1 candidate in 4 is unaffordable** under the ₹2,000 limit.

---

## What Analyze records

Every check, matches and misses, with the real figures. They are kept rather than recalculated later, because a recalculation shows what today's code *would* have seen, while the record shows what the system *did* see. Files under `data/analysis/` (lines only ever added):

| Line | Written | Holds |
|---|---|---|
| Universe | Monthly | The 500 shares and their median traded values. |
| Mood | Daily | The mood and the index figures behind it. |
| Check | Daily, one per share | The share's figures (close, 10-day high and low, 50-day average then and 10 days ago, typical daily move, volume, average volume, open, previous close) and, per checklist and version, pass or fail with the first condition that failed. |

About 500 check lines a day, roughly 20 MB a year.

**A candidate** is a check line where every condition of a checklist passed. Its ID (e.g. `2026-10-12/RELIANCE/quiet-breakout-v1`) points back to that line, which keeps the spec's link from every candidate to the check that produced it.

## What Analyze does not do

- No ranking, no scoring, no "nearly matched". A match against a written checklist is a fact; a score is an opinion, and opinions belong to Decide.
- No reading of news. Claude's review covers what the numbers cannot see.

## Tested in M3

- Each condition, true and false, on hand-built price series.
- The universe on a month boundary uses only the previous 60 days.
- A split due inside the holding period excludes the share.
- Adding future prices changes no check made before them.
