# Automated Trader

A system that studies the Indian share market each evening, suggests trades for the next day or two, writes down every decision, and improves by checking its own record.

It runs on fake money for the first three to four months. No real money until its own notebook has earned it.

**What it trades.** Shares bought with cash on NSE and BSE, held one to three days. No intraday, no futures and options — both are where beginners lose fastest. Decisions are made after the market closes, from the day's final prices.

**What it will never do.** Place an order. It tells you what it would do; you place every order yourself. That is permanent, not a starting arrangement.

---

## The seven jobs

In this order, every day.

### 1. Fetch — get the numbers

Downloads the day's prices and volumes for every share on our list, and delivers them exactly as they arrived.

It also hands over a receipt: of everything it was asked to get, what came through and what failed, with a reason for each miss.

It corrects nothing, not even an obvious error, and never judges whether a gap matters. A day is either delivered with a full receipt or marked failed.

### 2. Clean — make the numbers trustworthy

Adds the day's numbers to the stored history, correcting for company events that move a price without anything being traded. A share split turns one ₹1,000 share into five ₹200 shares — that looks like a crash and isn't.

It asks one question only: did this happen in the market? Never why. A share that fell 18% on bad news is true data and goes straight in.

When it cannot verify something it says *don't know*: that share sits out the day, with a reason, and is retried tomorrow. Missing one share for one evening is cheap. One false price spoils everything built on it.

All checking happens here. Every later job trusts the stored history without re-checking it.

### 3. Analyze — find the matches

First, the market's mood: trending up, trending down, or going sideways. A good-looking share in a bad market is usually a bad trade.

Then it runs every share against every checklist we hold. A checklist is a set of conditions that must all be true — say, quiet for two weeks, then closing above that range, on more than double the usual volume. Every condition is a yes or no that can be answered from the numbers. No opinions, no "looks strong".

A share that ticks every box becomes a candidate, with the real figures attached: not "high volume" but "3.1 times normal".

It reports and ranks nothing. Choosing between candidates is the next job.

**Full match or nothing.** It never scores shares on how close they came. A match against a written checklist is a fact; a score is an opinion, and opinions belong to Decide.

**It writes down every check it made** — matches and misses, with the real figures. These are kept rather than recalculated later, because a recalculation shows what the system *should* have seen under today's code, while the record shows what it *did* see, mistakes included.

### 4. Decide — pick the trades

Takes the candidates, the market's mood, what we already hold, and what the system has learned so far, then chooses what to buy and what to sell.

Every buy carries four things: how much, the price to sell at if it goes wrong, the price to sell at if it goes right, and how sure the system is.

It also decides exits on what we already hold. Knowing when to get out matters as much as knowing when to get in.

It can never invent a trade that matched no checklist, and never breach your safety limits.

### 5. Record — write it down first

Before anything acts on a decision, it goes in the notebook: the reasoning, the figures, how sure the system was. Shares considered and skipped go in too, with the reason — "passed on this and it rose 4%" is exactly the kind of mistake worth learning from.

Nothing is ever edited or deleted. Corrections are new entries pointing at the old ones.

Writing first is deliberate. If the machine dies overnight the decision survives, and the next job reads its work from the notebook rather than from Decide. That makes the notebook the spine of the system instead of a log kept to one side.

This same job writes a second time, later, once the result is known.

### 6. Settle — find out what happened

The next day it takes the pending decisions and the real prices and works out the facts: did the buy go through, at what price, did the stop or the target trigger, what is each holding worth now.

It reports gross profit and loss only — sell price minus buy price. Brokerage and taxes depend on your broker and are yours to handle; it records the trade size so you can work out the rest.

When the figures cannot settle it — the day's range touched both the stop and the target, and daily prices cannot say which came first — it writes *don't know* instead of inventing a result. A made-up loss and a real one look identical to anything reading the notebook later.

One number still has to be chosen: the account balance, because tomorrow's trade sizes are worked out from it. It takes the worse of the two possibilities, and tracks the running gap against the better one.

It never asks you what happened. It reads the market.

### 7. Learn — get better

Reads the finished notebook and updates how much to trust each checklist in each kind of market, along with how honest the system's confidence has been.

Confidence is tested: of all the times it said eight out of ten, was it right about eight times out of ten?

Every change must point at the entries that justify it. A learning step that cannot show its working is indistinguishable from noise — and it is what real money will eventually be trusting.

Four things it must hold to:

- Only real, completed trades move the trust scores. Checks on shares we never bought can raise suggestions for a human to review, nothing more: an untraded trade has no slippage and no stop-outs, so its result always flatters.
- Never one win rate when results are unknown. It gives a range — the floor counting every unknown as a loss, the ceiling counting each as a win — and how many were unknown.
- Never discard the unknowns. They are the volatile days, and dropping them leaves the system confident about conditions it never examined.
- Never judge a checklist on gross figures alone. One averaging a 0.4% win is positive before costs and dead after them.

---

## Rules that bind everything

- **Never look at the future.** No job may use anything that wasn't known when the decision it feeds was made. This is the most important rule here.
- **Your safety limits are yours.** Risk per trade, a stop-loss on every buy, a cap on open positions — you set them, they are fixed, and nothing automatic can change them. Learning tunes *what* to trade, never *how much* is at stake.
- **One writer per fact.** Clean alone writes market history. Settle alone writes the account books. Record alone writes decisions. Learn alone writes trust scores.
- **Nothing waits for you.** Every job finishes from data alone. You set the rules in advance and the system reads them as they stand, so it still runs on the days you are busy.
- **It never buys.** Its authority stops at Decide, in every phase.
- **The books are its own.** Since it neither places orders nor asks what you placed, its account is a model of its own decisions. Skip a suggestion and it may later tell you to sell something you never held. Your real profit and loss is yours.
- **Clear beats clever.** Where a more powerful method competes with a more explainable one, the explainable one wins. Trust is the product.
- **Three links must survive.** Every decision names the version of the trust scores it was made under. Every notebook entry links its decision to its result. Every candidate points back to the check that produced it.
- **Boundary problems go up, not sideways.** If detailed design finds one job can't give another what it needs, this document reopens. A job that works around a neighbour's bad output has quietly absorbed the neighbour's work.
- **Watchers are not jobs.** Reports, dashboards, alerts and the timer that starts each run all read from the system; nothing in the system depends on them.

---

## Words

| Word | Meaning |
|---|---|
| Universe | The fixed list of shares the system may look at. |
| Checklist (setup) | Conditions that must all be true before a share is considered. |
| Candidate | A share that ticked every box today — shortlisted, not chosen. |
| Market mood (regime) | Trending up, trending down, or sideways. |
| Stop-loss | The price to sell at to stop a loss growing. Fixed before buying. |
| Target | The price to sell at to take the profit. |
| Trade size | How much money goes into one trade. |
| Fill | What actually happened when an order met the market. A decision is a wish; a fill is a fact. |
| Slippage | The gap between the price you planned and the price you got. |
| Notebook (journal) | Every decision and result, written down, never edited. |
| Trust scores | How much to trust each checklist in each market mood. Learn updates these. |
| Paper trading | Practising with fake money on real prices. |
| Gross P&L | Sell price minus buy price, nothing taken out. |

---

## Still to decide

| Question | Current thinking |
|---|---|
| Who writes the reasoning | Rules find the candidates; a language model writes the plain-English case and may veto a trade, but never invents one. The veto needs justifying before it is granted. |
| How confidence is worked out | What goes into the number, and how the honesty check feeds back into it. |
| Which shares to watch | The largest 100 or the largest 500, and the floor below which a share trades too thinly for fake fills to predict real ones. |
| Where it runs | Which data sources, and whether a laptop or a server. Running every day without fail is the point. |

---

## Order of work

Detailed design happens in four passes, ordered by what could sink the project rather than by the daily sequence.

1. **Decide, Record and Learn together.** They carry the whole bet: can a record of past decisions measurably improve future ones? Learn can only learn what Record kept, and Record can only keep what Decide exposed — so they are designed as one.
2. **Settle.** The honesty of the entire fake-money period rests on how it works out fills. Small job, large consequence.
3. **Analyze.** Well-trodden ground. The risk is holding too many checklists, not designing them wrong.
4. **Fetch and Clean.** Ordinary engineering with known answers. Last, and briefly.

**The test at the end of the fake-money period** is not whether the notebook shows a profit — a kind few months can manufacture that. It is whether confidence proved honest, whether the system behaved properly through losing runs, and whether few enough results were unknown that the record measures the market rather than our own assumptions.
