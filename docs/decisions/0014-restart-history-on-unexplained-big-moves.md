# 0014 — An unexplained move beyond 35% restarts the share's history

**Decided.** If a share's price moves more than 35% in a day and no corporate action explains it, Clean drops its earlier history (it restarts from the next day). Settle records any trade open across such a break as unknown. Moves between 25% and 35% still sit out one day and are then accepted as real.

**Considered.** Accepting every move after a one-day pause (the M3 rule).

**Why.** The M5 rebuild found NSE's corporate-action list misses some splits and demergers: JSW Steel −90% (2017), Cadila −80% (2015), Crompton Greaves −72% (2016), Tata Motors −40% (2025). Kept as real, each would plant a fake crash in the share's averages, and book a fake loss of up to 90% on any trade open across it. NSE's widest daily price band is 20%, and moves beyond 35% with no news of an action were mostly these missing actions. Real ones also exist (Jet Airways, DHFL, PSU banks in October 2017), but losing a share's eligibility for about 60 days is cheap; a false price spoils everything built on it. Applied to the rebuilt history by adding the same restart records the rule writes (392 of them); the stored prices are unchanged.
