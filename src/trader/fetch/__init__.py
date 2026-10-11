"""Fetch: downloads the day's prices exactly as they arrived, with a receipt. Writes data/raw/ (receipts only)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from trader.store import Store, month_file

from . import nse


@dataclass
class Delivery:
    """What one day's fetch handed to Clean."""
    date: dt.date
    status: str  # delivered | failed | market_closed
    files: dict[str, bytes] = field(default_factory=dict)


def fetch_day(store: Store, d: dt.date, historical: bool = True) -> Delivery:
    """Fetches the price file and index closes for one trading date.

    A missing price file for a past date means NSE was closed that day. For today it
    means the file is not published yet, which is a failure the evening retries handle.
    """
    files, items = {}, []
    price, r = nse.get("price_file", nse.price_file_url(d))
    items.append(r)
    if price is None and r["status"] == "missing" and historical:
        status = "market_closed"
    else:
        index, r2 = nse.get("index_closes", nse.index_file_url(d))
        items.append(r2)
        if price is not None:
            files["price_file"] = price
        if index is not None:
            files["index_closes"] = index
        status = "delivered" if price is not None and index is not None else "failed"
    _receipt(store, d, status, items)
    return Delivery(d, status, files)


def fetch_corporate_actions(store: Store, start: dt.date, end: dt.date, on: dt.date) -> bytes | None:
    body, r = nse.get("corporate_actions", nse.corporate_actions_url(start, end))
    _receipt(store, on, "delivered" if body is not None else "failed", [r])
    return body


def fetch_reference(store: Store, d: dt.date) -> dict[str, bytes | None]:
    """NSE's trading holidays and symbol changes. Small files, fetched each evening."""
    holidays, r1 = nse.get("holidays", nse.HOLIDAYS_URL)
    changes, r2 = nse.get("symbol_changes", nse.SYMBOL_CHANGES_URL)
    _receipt(store, d, "delivered" if holidays and changes else "failed", [r1, r2])
    return {"holidays": holidays, "symbol_changes": changes}


def _receipt(store: Store, d: dt.date, status: str, items: list[dict]) -> None:
    store.writer("fetch").append_records(month_file(d, "jsonl"), [{"date": d.isoformat(), "day_status": status, "items": items}])
