# Design Pass 1: Decide, Record, Learn

How the system chooses trades, writes them down, and learns from the results. These three jobs carry the project's central bet: can a record of past decisions measurably improve future ones? They are designed together because Learn can only learn what Record kept, and Record can only keep what Decide exposed.

**Status:** Approved 2026-10-11. Decisions are recorded in [reports/m1.md](../reports/m1.md).

Background: [spec.md](../spec.md) describes the seven jobs. [repo-structure.md](repo-structure.md) describes where things live.

---

## Words used here

| Word | Meaning |
|---|---|
| Candidate | A share that matched every condition of a checklist today. Found by Analyze. |
| Checklist | A named set of yes/no conditions, plus its own exit rules (where the stop and target go, and the longest hold). Each has a version. |
| Market mood | Up, down or sideways, as of the decision date. Defined in M2. |
| Cell | One checklist in one market mood, e.g. "breakout v1 in an up market". Trust is tracked per cell. |
| R | The amount risked on a trade: entry price minus stop price, per share. A trade that loses its full stop is −1R; one that gains twice its risk is +2R. Using R lets trades of different sizes be compared. |
| Net | After an estimate of trading costs. Set to zero for now (see "Costs"), so net equals gross until it is revisited. |
| Win | A trade whose net result is above zero. |
| Unknown | A trade whose result daily prices cannot settle, e.g. the day's range touched both the stop and the target. Settle reports these; nobody guesses them. |
| Trust version | A numbered snapshot of everything Learn believes. Every decision names the version it was made under. |

---

## One evening, step by step

| Order | Step | Runs on |
|---|---|---|
| 1 | **Fetch** and **Clean** today's prices | GitHub Actions |
| 2 | **Settle** yesterday's decisions against today's prices: fills, stops, targets, the account | GitHub Actions |
| 3 | **Record** the result of every trade that finished today | GitHub Actions |
| 4 | **Learn** from those results; write a new trust version if anything changed | GitHub Actions |
| 5 | **Analyze** today's prices: market mood, candidates | GitHub Actions |
| 6 | **Decide**: exits and buys for tomorrow. **Record** them as *proposals* | GitHub Actions |
| 7 | **Claude reviews** the proposals: writes the case for each, may object to one | Cloud routine |
| 8 | **Check** the review; **Record** the final decisions; write the daily report | GitHub Actions |

**Spec note.** The spec lists the jobs in the order a single decision lives through them: decide today, settle tomorrow. The run order above differs on purpose. Settle and Learn must run *before* Decide, otherwise Decide would count a position as open after it had already been stopped out that day. No job's responsibility changes. This needs your approval because the spec says "in this order, every day".

---

## Decide

### What it reads
All of it read from `data/`, dated today or earlier:
- Today's candidates and market mood (Analyze).
- Open positions, the account balance, and the account's highest balance so far (Settle).
- The latest trust version (Learn).
- Your safety limits and the cost estimate (`config/`).

### Exits come first
Every exit is fixed at the moment of buying, and Decide never moves it:
- **Stop:** sell if the price falls to the stop.
- **Target:** sell if the price rises to the target.
- **Time limit:** if neither has happened by the close of the third trading day, sell at the next open.

Where the stop and target go comes from the checklist's own exit rule. Fixed exits are the easiest to test and the hardest to fool yourself with. There is no trailing stop and no "it looks weak, get out". Those can be added later as a new checklist version, measured like everything else.

### Buys
1. **Entry:** buy at tomorrow's opening price, using the exchange's pre-open order. If the share opens below the stop or above the target, the trade is cancelled and recorded as "not entered: opened beyond its exit".
2. **Eligibility.** A candidate is dropped, with the reason recorded, if:
   - the share is already held;
   - its cell is switched off (see "Trust scores");
   - the safety limits leave no room for it.
3. **One checklist per share.** If a share matched two checklists, the one with the higher expected result is kept, and the other is recorded as skipped.
4. **Ranking.** If there are more candidates than room, they are ranked by expected net result in R (see "Trust scores"), highest first. Ties go to the share with the higher trading value, then alphabetically, so the same inputs always give the same choice.
5. **Size.** Quantity = (balance × risk per trade) ÷ (entry − stop), rounded down. The entry estimate is today's close. Then capped by the maximum position size, the maximum total open risk, and the cash on hand (this is cash trading, so nothing is borrowed). If the result is zero shares, the candidate is skipped as "cannot afford one share within the limits". With a small account this happens often, e.g. for shares priced above ₹2,000.

**Learning never changes size.** Confidence and trust decide *what* is bought. Only your limits decide *how much*, as the spec requires.

### Safety limits
Stored in `config/limits.yaml`, which code can read but never write. Set by you on 2026-10-11.

| Limit | Value | What it does |
|---|---|---|
| Paper starting balance | ₹10,000 | The fake money the account starts with. |
| Risk per trade | 1% of the balance (₹100 at the start) | The amount lost if a stop is hit. |
| Max open positions | 5 | How many shares may be held at once. |
| Max position size | 20% of the balance (₹2,000 at the start) | The most in any one share. Stops a very tight stop from creating a huge position, and limits the damage from one share crashing overnight. |
| Max total open risk | 5% of the balance | The most that can be lost if every open stop is hit at once. |
| Losing-run brake | 10% below the highest balance: risk per trade halves. 15% below: no new buys for 10 trading days, then resume at half risk until back within 10%. | Automatic, so nothing waits for you. |

**In practice** the 20% cap binds on about 72% of trades (M2 measurement: the typical stop is 3.2% below the price). So the real risk per trade is usually about ₹60, not ₹100.

A stop on every buy is not a setting. It is always on.

### What it produces
- **Proposals:** every buy and exit, each with quantity, stop, target, time limit, confidence, expected result, the reasons in a plain sentence written by code, and links (see "Record").
- **Skips:** every candidate not proposed, with its reason.

Given the same inputs, Decide always produces the same output. M3 tests this, and tests that changing any future price changes nothing.

---

## Claude's review

### What Claude gets
Today's proposals and skips from the notebook, the candidates' figures, and the repo. It may look up public news.

### What Claude may do
For each proposed buy:
- **Write the case:** a plain-English paragraph (at most 120 words) on why the trade fits.
- **Object (veto):** only by choosing a category and giving a reason that names a specific fact.

| Veto category | Example |
|---|---|
| Event inside the holding period | Quarterly results are due tomorrow. |
| Corporate action inside the holding period | A split takes effect on day two, which breaks the stop and target. |
| Legal or regulatory news | A regulator has barred the company from raising money. |
| Data looks wrong | The volume figure is 100× its usual level with no news. |

Claude cannot add a trade, change a number, or touch exits.

### The check
The review is a single file on Claude's own branch. Finalize rejects the whole review, records why, and carries on without it if:
- it is for the wrong date;
- it mentions a trade that was not proposed, or the same trade twice;
- a veto has no category from the list, or a reason under 20 characters;
- it contains anything else.

If no review arrives, finalize carries on and records "no review". Every decision also carries code's own one-line reasoning, so the record is complete with or without Claude.

### Veto power
Decided: **vetoes are recorded but not obeyed during paper trading.** The trade is taken anyway and the objection is kept. At the end of paper trading the record answers the question: did the trades Claude objected to do worse? Only if they did does the veto get real power. That is the spec's "the veto needs justifying before it is granted", answered by evidence.

This cannot be tested on past data. Claude already knows how past events turned out, so its judgment on history would be looking at the future.

---

## Confidence

**Definition.** Confidence is the estimated chance that a trade ends as a win, net of costs. That is specific enough to check later: of all trades given 60%, did about 60% win?

**How it is worked out:** it is the measured win rate of the trade's cell, smoothed:
- **Paper trades count fully. Backtest trades count a quarter each**, capped so the backtest can never outweigh 20 paper trades. Paper results soon take over.
- **A cell with little evidence borrows from its checklist's record in all moods**, and a checklist with little evidence borrows from the overall record. The borrowing fades as the cell's own evidence grows. This is the standard remedy for small samples, and it can be explained in one sentence.
- **Unknowns count as losses** in the number used for decisions. That is the cautious end of the range, matching how Settle books the account.

**The honesty check.** Each time Learn runs, it groups past trades by the confidence they were given (40–50%, 50–60%, and so on) and compares each group's stated confidence with what actually happened:
- what actually happened is shown as a range: unknowns counted as losses at one end, as wins at the other;
- each group is judged **honest**, **overconfident**, **underconfident** or **not enough trades yet**, allowing for the margin of error that small numbers bring.

**What the check changes.** One thing only. If, across at least 30 trades, confidence is clearly too high, Learn halves the weight given to backtest trades. Overconfidence most likely comes from the backtest flattering the checklists. It never raises the backtest's weight automatically. More trust has to come from real results.

---

## Trust scores

For every cell, Learn keeps:
- paper trades, and separately backtest trades: wins, losses, unknowns;
- the win rate as a range (unknowns as losses, unknowns as wins);
- average net result in R, as a range. An unknown counts as the stop at one end and the target at the other;
- the smoothed estimates used by Decide (expected net R, confidence);
- the notebook entries behind every number.

**Switching a cell off.** During paper trading, a cell stays on until the evidence shows it loses. It switches off once it has at least 10 paper trades and even its most generous estimate is below zero. Paper money costs nothing, and trading is the only way to learn, so cells are innocent until proven guilty.

With real money the rule will flip: a cell switches on only once even its most cautious estimate is above zero. That rule is for the end of M7, not now.

A new version of a checklist starts with no paper record. Its new backtest gives it a starting point.

---

## Record (the notebook)

One file per month, `data/notebook/2026-10.jsonl`, one entry per line. Only Record writes it, and lines are only ever added.

| Entry | Written | Holds |
|---|---|---|
| `run` | Start and end of each evening | Date, code version, trust version, whether the review arrived, was rejected or was missing, and counts. |
| `proposal` | Step 6 | Everything Decide proposed, as listed above. |
| `skip` | Step 6 | A candidate not proposed, and why. |
| `review` | Step 8 | Claude's case and any veto per proposal, or why the review was rejected. |
| `decision` | Step 8 | The final buys and exits, with the safety limits as they stood. |
| `result` | Step 3, once a trade finishes | Filled or not; entry and exit prices; why it exited (stop, target, time limit, opened beyond its exit, unknown); gross and net result; result in R. |
| `correction` | When needed | Points at an earlier entry and states what was wrong. Never edits it. |

**Links that must survive** (spec, "three links"):
- every entry has a fixed ID, e.g. `2026-10-12/RELIANCE/breakout-v1`;
- a decision names its trust version and the candidate check that produced it;
- a result names its decision;
- the code version is recorded on every evening's `run` entry.

**Written before anything acts.** Decisions are saved to the repo before the daily report exists, so a decision survives even if the run dies straight after.

---

## Learn

Runs each evening after the day's results are recorded (step 4).

- **Only taken trades move trust scores.** That includes trades taken despite a veto. Candidates that were skipped become **suggestions** for you to review (e.g. "breakout v1 candidates skipped for lack of room won 9 of 12"), never score changes. A trade that was never taken has no slippage and no stop-outs, so its result always flatters.
- **No single win rate while results are unknown.** Always a range, plus how many were unknown.
- **Unknowns are never dropped.** They are the volatile days.
- **Judged net, not gross.** Both are shown; decisions use net.
- **Every new trust version lists what changed and the entries that caused it.** A version that cannot show its evidence is not written.

Learn writes to `data/trust/2026-10.jsonl`: one line per trust version, including any suggestions. Suggestions come from Settle's shadow trades (see pass2-settle.md), and are raised only when skipped candidates beat the taken ones by more than 5 percentage points over at least 20 taken trades.

---

## Costs

Ignored for now, by your decision: the cost estimate in `config/costs.yaml` is zero, so "net" equals gross. The mechanism stays, so costs can be switched on with one number.

**Revisit before any real money.** At ₹1,000–2,000 per position, a broker's flat fee of about ₹15 per sale is about 1% of the trade, plus 0.1% securities transaction tax on each side.

## What Pass 1 needs from other jobs (handed to M2)

| From | Must provide |
|---|---|
| Analyze | Each candidate with its share, checklist and version, the figures that matched, and the checklist's exit rule. The market mood for the day. |
| Checklists | Each checklist states its stop rule, target rule and time limit, as well as its conditions. |
| Settle | For each decision: entered or not, entry price, exit price and reason, or unknown with the reason. The open positions, the balance (worse case and better case), and the highest balance so far. |

---

## What the paper period can and cannot prove

About 80 trading days, with at most 5 positions held 1–3 days, gives roughly 100–150 trades. (M1 estimated 60–120. M2 found candidates are plentiful, about 22 a day, so room, not candidates, is the limit.) That means:
- **Confidence can be shown honest only roughly**, to within about ±10 percentage points. Finer claims would need more trades.
- **Per-cell evidence will be thin**, about 5–10 trades per cell with 4 checklists and 3 moods. This is why cells borrow from their checklist's record, and why the first set of checklists should be small (M2).
- **The veto test will rest on perhaps 10–20 objections.** Enough to see a large effect, not a small one.

At the end of M7, the report will state the trade count, and if it is too thin to judge, recommend extending paper trading rather than overstating what was shown.
