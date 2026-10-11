# Design Pass 2: Settle

How the system works out what its fake trades would actually have done, using only real daily prices. The honesty of the whole paper-trading period rests on this job: a result made up here looks exactly like a real one to everything that reads the notebook later.

**Status:** Draft for approval at the end of M2.

Background: [spec.md](../spec.md) (the seven jobs), [pass1-decide-record-learn.md](pass1-decide-record-learn.md) (how trades are decided).

---

## Words used here

| Word | Meaning |
|---|---|
| Open / high / low / close | A share's first price of the day, highest, lowest and last. NSE's daily file gives these four, and nothing about the order in which they happened. |
| Gap | The share opens well away from yesterday's close, e.g. after overnight news. |
| Locked day | A day when the high equals the low: the share was stuck at its daily price limit and almost nobody could trade it. |
| Unknown | A result daily prices cannot settle. Recorded as unknown, never guessed. |
| Trading day | A day NSE is open, per NSE's holiday list. |

---

## What Settle reads and writes

- **Reads:** final decisions (the notebook), cleaned prices and corporate actions (history), and its own books so far.
- **Writes:** `data/books/2026.jsonl`, one line per event (entered, not entered, exited, unknown, adjusted for a split), plus one snapshot of the account per trading day. Only Settle writes here.
- Record then reads Settle's events and writes each finished trade's `result` into the notebook.

Settle never asks you what happened. It reads the market.

---

## Entering a trade

A buy decided on day 0 is placed at the open of day 1.

| What day 1 shows | Outcome |
|---|---|
| Opens between the stop and the target | **Entered** at the open price. |
| Opens at or below the stop, or at or above the target | **Not entered**: "opened beyond its exit". |
| Locked day, or the share did not trade | **Not entered**: "could not trade". |
| No price for the share yet (Clean said "don't know") | **Waiting**: tried again next evening, for up to 5 trading days, then **not entered**: "no price". |

Quantity is as decided. If the open price makes the trade cost more than the cash available, the quantity is cut to fit, and the cut is recorded.

## Exiting a trade

Each trading day the trade is held (day 1 included, from the entry onwards), the day is checked in this order:

1. **Locked day:** nothing can be sold. The trade carries on, and the day does not count towards the time limit.
2. **Opened at or below the stop:** exited **at the open**, worse than the stop. A gap through a stop is a real loss and is booked as one.
3. **Opened at or above the target:** exited **at the open**, better than the target.
4. **The day's range touched both the stop and the target:** **unknown**. Daily prices cannot say which came first.
5. **The low touched the stop:** exited **at the stop**.
6. **The high touched the target:** exited **at the target**.
7. **None of these:** held. After the close of the third counted day, the trade is exited **at the next open** (the time limit).

On day 1 steps 2 and 3 cannot apply, since the trade was entered at that open.

**Exact fills are assumed** at the stop and the target. Real stop orders often fill slightly worse. This flatters results a little, and is revisited together with costs before any real money.

## Unknowns

- **Once unknown, always unknown.** No later information is used to pick a side.
- **Valued both ways.** The worse case counts the trade as exited at the stop; the better case counts it as exited at the target. Both are kept.
- **No price for a held share** (suspended, or Clean said "don't know"): the trade waits, re-checked each evening. After 5 trading days without a price it becomes unknown, with the reason.

## Corporate actions during a trade

If a split or bonus takes effect while a trade is open, Clean records it with its ratio. Settle then scales the trade to match, and records the change:
- **quantity up** by the ratio;
- **entry, stop and target down** by the same ratio.

The trade's value and risk do not change. (Analyze skips any share with a split or bonus due inside the holding period, so this should be rare. This rule covers announcements that arrive late.)

Dividends are ignored. At the sizes involved they move the price by well under a typical day's range.

---

## The account

Each trading day Settle writes one snapshot:

| Figure | Meaning |
|---|---|
| Cash | Starting balance, minus what open trades cost, plus what closed trades returned. |
| Open positions | Each with quantity, entry, stop, target, days held, and the day's close. |
| Balance, worse case | Cash plus open positions at the day's close, with every unknown trade counted at its stop. |
| Balance, better case | The same, with every unknown counted at its target. |
| Gap | Better case minus worse case: how much the unknowns could matter. |
| Highest balance so far | The highest worse-case balance to date. The losing-run brake uses it. |

**Tomorrow's trade sizes come from the worse-case balance**, as the spec requires. The gap is reported every day, so a growing pile of unknowns is visible at once.

**Gross only.** Results are sell price minus buy price. Costs are applied later by Learn, using the cost estimate (currently zero).

---

## What Settle needs from other jobs

| From | Must provide |
|---|---|
| Record | Final decisions with quantity, stop, target and time limit. |
| Clean | Daily open, high, low and close per share, unadjusted. Verified splits and bonuses with ratio and effective date. A "don't know" list with reasons. |
| Fetch (via Clean) | NSE's trading-day calendar, so the time limit counts trading days only. |

## Tested in M3

- Every row of the two tables above, one test each.
- A gap through a stop is booked at the open, not at the stop.
- A both-touched day is unknown, and the account shows both cases.
- A split during a trade leaves its value and risk unchanged.
- Settling the same days twice gives identical books.
