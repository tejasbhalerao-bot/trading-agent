# 0007 — Fetch uses IPv4 and short timeouts

**Decided.** Fetch connects to NSE over IPv4 only, with short timeouts.

**Considered.** The system default (IPv6 first).

**Why.** In M2, connections to NSE's IPv6 address hung for 30 seconds each on your network before falling back, which made a bulk download crawl. Scripts that fall back instantly (like curl) were unaffected.
