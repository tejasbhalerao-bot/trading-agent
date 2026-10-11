# How to Read the Daily Report

Every trading evening, after the market closes, the system writes a plan for the next morning. This page explains what it is telling you and why. No trading background needed.

## What the system does, in one paragraph

Each evening it looks at the 500 most-traded shares on NSE and checks each one against three **checklists**: written recipes for a short price move that has often happened before. A share that meets every condition of a checklist becomes a candidate. The system picks the best few within your safety limits and plans each trade completely in advance: when to buy, the price to sell at if it goes well, the price to sell at if it goes badly, and the latest day to get out. It runs on fake money. It never places an order; you do, if you choose to follow along.

## Your routine, if you follow along

| When | What to do |
|---|---|
| Evening | Read the report's "In short" section. |
| Next morning, 9:00–9:08am | Place the buys and sells it lists, as "at market" orders in the pre-open session. |
| After a buy goes through | Set its stop-loss and target with your broker as one order (GTT-OCO). |
| Nothing else | Each trade ends by itself at its stop-loss, its target, or its time limit. |

## The three prices every trade has

| Price | Meaning | Why it exists |
|---|---|---|
| **Target** | If the price rises to this, sell and keep the profit. | Takes the gain the trade was aiming for, before it can slip away. |
| **Stop-loss** | If the price falls to this, sell and accept a small loss. | Caps how much one trade can lose. Set before buying and never moved. |
| **Time limit** | If neither has happened after 3 trading days, sell at the next open. | Each checklist bets on a move **within a few days**. If it hasn't come by then, the idea hasn't worked, and the money is better used for a new trade. Without a time limit, money could sit for weeks in a trade that is going nowhere. |

The target is set 1.5 times as far above the buying price as the stop-loss is below it, so a win is bigger than a loss. That is why a trade can be worth taking even if only about half of such trades make money.

## The checklists

Each checklist is a short list of yes/no conditions, every one answerable from the numbers alone. The report shows each condition with the actual figures for that share. The full definitions are in [config/checklists/](../config/checklists/).

| Checklist | The idea, in plain words |
|---|---|
| **Quiet breakout** | A share that has traded in a narrow band for two weeks breaks above it, on much heavier trading than usual. Such break-outs often continue for a few days. |
| **Pullback in an uptrend** | A share that has been rising steadily dips for three days. In a rising share, short dips often bounce back. |
| **Gap up that holds** | A share opens at least 3% higher, usually on news, and holds the gain all day on heavy trading. The buying often carries on. |

## Words in the report

| Word | Meaning |
|---|---|
| **Pre-open session** | 9:00–9:08am. Orders placed then are filled at the day's opening price. |
| **GTT-OCO order** | A standing order at your broker with two prices (stop-loss and target). Whichever is reached first sells the shares and cancels the other. The name varies by broker. |
| **How likely** | Of the system's past trades like this one, the share that made money. The system checks regularly whether these figures are honest. |
| **Expected gain** | What a trade like this has made or lost on average, after combining how often it wins with how much a win and a loss are each worth. |
| **Market mood** | Whether the whole market (the Nifty 500 index) is rising, falling or mixed, judged against its average price of the last 50 days. Checklists are tracked separately in each mood, because a pattern that works in a rising market may fail in a falling one. |
| **Losing-run brake** | Your safety rule: if the practice account falls 10% below its highest, each trade risks half as much. At 15%, new buys pause for 10 trading days. |
| **Switched off** | A checklist that has clearly lost money in a particular market mood is skipped in that mood. |
| **Unknown** | On a few days a share's price touches both its stop-loss and its target. Daily prices can't say which came first, so the system records the result as unknown rather than guess. |

## What each section is for

| Section | Purpose | Do you need to act? |
|---|---|---|
| In short | Tomorrow's actions in four lines. | Read this first. |
| 1. Buy tomorrow morning | Each new trade: why this share, its plan, how likely it is to work, and why that many shares. | Yes, if following along. |
| 2. Sell tomorrow morning | Trades whose 3 days are up: what was bought, and why it is being sold. | Yes: cancel its stop-loss and target, then sell at the open. |
| 3. Trades still running | Trades under way, with their prices and last day. | Only check their stop-loss and target orders are active. |
| 4. Trades that ended today | How each finished trade ended, and what it made or lost. | No. |
| 5. Other shares that qualified | Shares that met a checklist but weren't picked, and why: usually no room, since at most 5 trades run at once. | No. |
| 6. The practice account and the market | The fake-money balance, whether the brake is on, and the market mood. | No. |
| 7. Is the system working properly? | Green ticks when data, Claude's review and the honesty check are all fine; warnings when something needs a look. | Only if a warning appears. |

## If you skip a suggestion

The system keeps its own books. It doesn't know what you actually bought. If you skipped a buy, ignore the later instruction to sell it.
