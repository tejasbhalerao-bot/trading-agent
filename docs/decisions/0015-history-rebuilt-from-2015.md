# 0015 — Market history rebuilt from 2015 in one pass

**Decided.** For the backtest, the whole history was rebuilt from 1 January 2015 to 9 October 2026 in one pass, and it replaced the January 2024 history.

**Considered.** Fetching 2015–2023 separately and joining it to the existing history.

**Why.** Clean checks each day against the day before, so history must be built in date order. The rebuilt 2024–2026 part matches the old one in all but 8 of 1,292,043 rows. All 8 are small splits checked a month late, after the share had left NSE's ordinary-share list; the rebuild treated them cautiously (history restarts). Two problems surfaced and were fixed: a 2020 file that writes dates as "13-Jul-20", and an unreadable file now fails only its own day (decision in the M5 report).
