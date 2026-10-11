# 0005 — Keep Fetch's receipts, not the downloaded files

**Decided.** `data/raw/` holds a receipt for every download: what was asked for, whether it arrived, its size and checksum, and why anything failed. The files themselves are used in the same run and then discarded.

**Considered.** Storing every downloaded file in the repo.

**Why.** About 50 MB a year of extra repo size for files NSE keeps publicly. The checksum proves what was received, and the file can be re-fetched and compared.
