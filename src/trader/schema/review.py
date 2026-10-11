"""The shape of Claude's daily review, and the check it must pass.

A review can only comment on and object to proposed buys. It cannot add a trade,
change a number or touch an exit. Anything that breaks the shape rejects the whole
review, and the evening carries on without it. Design: pass1-decide-record-learn.md.
"""

from __future__ import annotations

import json

VETO_CATEGORIES = {
    "event": "An event inside the holding period (e.g. results due)",
    "corporate_action": "A corporate action inside the holding period",
    "legal_or_regulatory": "Legal or regulatory news",
    "data_looks_wrong": "The figures look wrong",
}
MAX_CASE_WORDS = 120
MIN_REASON_CHARS = 20


def check_review(raw: bytes | str | None, date: str, proposal_ids: set[str]) -> tuple[dict | None, list[str]]:
    """Returns (review, []) if acceptable, else (None, reasons it was rejected)."""
    if raw is None:
        return None, ["no review arrived"]
    try:
        review = json.loads(raw)
    except (ValueError, TypeError) as e:
        return None, [f"not valid JSON: {e}"]
    problems = []
    if not isinstance(review, dict) or set(review) != {"date", "reviews"}:
        return None, ["must be an object with exactly 'date' and 'reviews'"]
    if review["date"] != date:
        problems.append(f"review is for {review['date']}, not {date}")
    if not isinstance(review["reviews"], list):
        return None, problems + ["'reviews' must be a list"]
    seen = set()
    for i, item in enumerate(review["reviews"]):
        where = f"review {i + 1}"
        if not isinstance(item, dict) or not set(item) <= {"id", "case", "veto"} or "id" not in item or "case" not in item:
            problems.append(f"{where}: must have 'id' and 'case', optionally 'veto', and nothing else")
            continue
        if item["id"] not in proposal_ids:
            problems.append(f"{where}: {item['id']} was not proposed today")
        if item["id"] in seen:
            problems.append(f"{where}: {item['id']} reviewed twice")
        seen.add(item["id"])
        if not isinstance(item["case"], str) or not item["case"].strip():
            problems.append(f"{where}: the case is empty")
        elif len(item["case"].split()) > MAX_CASE_WORDS:
            problems.append(f"{where}: the case is over {MAX_CASE_WORDS} words")
        veto = item.get("veto")
        if veto is not None:
            if not isinstance(veto, dict) or set(veto) != {"category", "reason"}:
                problems.append(f"{where}: a veto must have exactly 'category' and 'reason'")
            elif veto["category"] not in VETO_CATEGORIES:
                problems.append(f"{where}: veto category {veto['category']!r} is not on the list")
            elif not isinstance(veto["reason"], str) or len(veto["reason"].strip()) < MIN_REASON_CHARS:
                problems.append(f"{where}: a veto needs a reason of at least {MIN_REASON_CHARS} characters naming a fact")
    return (None, problems) if problems else (review, [])
