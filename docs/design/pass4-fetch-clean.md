# Design Pass 4: Fetch and Clean

How each day's market data is collected and made trustworthy. Fetch gets the numbers and says exactly what arrived. Clean decides what goes into the stored history. All checking happens in Clean, and every later job trusts the history without re-checking it.

**Status:** Approved 2026-10-11.

Background: [spec.md](../spec.md), [reports/m0.md](../reports/m0.md) (what M0 learned about the data).

---

## Words used here

| Word | Meaning |
|---|---|
| Daily price file | NSE's end-of-day file (the "bhavcopy"): open, high, low, close, volume and traded value for every share. |
| Corporate action | A company event that moves the price with no trading. Splits and bonuses matter here. |
| Unadjusted price | The price as it actually traded that day. |
| Adjusted price | A past price scaled for later splits and bonuses, so that a 1-for-5 split does not look like an 80% crash. |
| Receipt | Fetch's record of what it was asked for, what arrived, and what failed and why. |
| Don't know | Clean cannot verify a share's figures today. The share sits out the day, with the reason, and is retried. |

---

## Fetch

### What it gets, from NSE only

| Item | Source | When |
|---|---|---|
| Daily price file | NSE archive. The old format to 5 July 2024, the new format after. | Every trading day |
| Corporate actions, from 30 days back to 30 days ahead | NSE's corporate actions list | Every trading day |
| Index closing values (for market mood) | NSE's daily index file | Every trading day |
| Trading holidays | NSE's holiday list | Weekly |
| Symbol changes | NSE's symbol-change list | Weekly |

### When
- NSE publishes the daily price file at about **4:35pm IST**.
- The evening run starts at **6:00pm IST**. If a required file is not there yet, it retries every 30 minutes until **10:00pm IST**.
- After that the day is marked **failed**. The next evening's run fetches the missing day first.

### How
- One request at a time, with a pause between requests.
- IPv4 connections and short timeouts. In M2 testing, NSE's IPv6 address hung for 30 seconds on some networks.
- A browser-like identity, as plain scripts are sometimes refused.

### The receipt
Every run writes one receipt to `data/raw/` covering each item:
- what was asked for and from where;
- whether it arrived;
- its size and a fingerprint (a checksum), so the same file can be re-fetched and shown identical;
- the number of attempts, and the reason for any failure.

The day's status is **delivered** (every required item arrived), **failed** (with reasons), or **market closed** (on NSE's holiday list).

Fetch corrects nothing and judges nothing. It hands the files to Clean exactly as received, in the same run.

**The downloads themselves are not stored, only the receipts.** The files would add about 50 MB a year to the repo. NSE keeps its archive public, and the checksums prove what was received. This changes one line of [repo-structure.md](repo-structure.md): `data/raw/` holds receipts, not downloads.

---

## Clean

Clean asks one question of every figure: **did this happen in the market?** Never why. A share that fell 18% on bad news is true data and goes straight in.

### What it stores
| File | Holds |
|---|---|
| `data/history/prices/2026.csv` | One line per share per trading day, unadjusted: date, symbol, open, high, low, close, previous close, volume, traded value, number of trades. Ordinary shares only (NSE's "EQ" series). |
| `data/history/actions/2026.csv` | Verified splits and bonuses: symbol, effective date, ratio, NSE's own wording, and how it was verified. |
| `data/history/identity.csv` | Which ISIN each symbol had from which date, and symbol renames. A company's history follows it through both. |
| `data/history/skipped/2026.jsonl` | Every "don't know": share, date, reason. |

All lines are only ever added. History from January 2024 is fetched in M3; 2015–2023 is added in M5 for the backtest, through this same code. Sizes: about 35 MB per year of history, about 400 MB in all after that one-time fetch, within GitHub's comfortable limits.

### Checks on every share, every day

| Check | If it fails |
|---|---|
| Prices are positive, and the low ≤ open and close ≤ the high | Don't know |
| Today's "previous close" equals the close stored for the share yesterday | Don't know. (NSE's previous close is unadjusted even on a split day, so a mismatch means a data or identity problem.) |
| The share was in yesterday's universe but is missing today | Don't know: "not traded today", possibly suspended |
| A split or bonus takes effect today | Stored only if the price move, scaled by the announced ratio, is a normal day's move (within ±20%). Otherwise don't know. |
| The price moved more than 25% and no split or bonus explains it | Don't know for one day. Corporate action announcements can arrive late. If none appears by the next evening, the move is accepted as real. |
| The same share appears twice in one file | Don't know |

A "don't know" share is retried each evening. Missing one share for one evening is cheap. One false price spoils everything built on it.

### Other corporate actions
- **Demergers and schemes of arrangement** permanently break a price series. The share's history restarts on that date, and it needs fresh history before any checklist can match it.
- **Dividends and rights issues** are not adjusted for. At these sizes they move the price by far less than a normal day.

### Adjusted prices, without looking at the future
Adjusted prices are worked out when they are read, never stored. A split is only applied to earlier prices **once its effective date has passed** relative to the decision being made. A backtest on 1 March 2020 must not know about a split that happened in 2021.

---

## Market-closed and missing days

- A day on NSE's holiday list is "market closed": no run beyond Fetch.
- A weekday with no file and no holiday listed is retried, then marked failed. If the next trading day's previous-close figures match the last stored closes, the missing day was an unscheduled closure, and it is recorded as such.

## Tested in M3

- Old- and new-format files for the same dates (January to July 2024) produce identical history lines.
- Every row of the checks table, one test each.
- A split appears in adjusted prices only after its effective date.
- Re-running Clean on the same files changes nothing.
