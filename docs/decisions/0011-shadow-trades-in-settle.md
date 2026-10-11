# 0011 — Skipped candidates are settled as shadow trades

**Decided.** Settle also settles every skipped candidate that had a stop and target, by the same rules, as one-share "shadow" trades outside the account. Learn uses them only for suggestions.

**Considered.** Learn working out skipped candidates' outcomes itself, or no suggestions at all.

**Why.** Working out what a trade would have done is Settle's job. Learn doing it would duplicate Settle's rules, which the spec's boundary rule forbids. Shadow trades never touch the balance or the trust scores, keeping the spec's rule that untraded checks only raise suggestions.
