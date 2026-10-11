"""Reads NSE's files into plain rows. Both price-file formats give identical rows."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import zipfile

from trader.schema import BONUS, RESTART, SPLIT

_OLD = {"symbol": "SYMBOL", "series": "SERIES", "isin": "ISIN", "open": "OPEN", "high": "HIGH", "low": "LOW", "close": "CLOSE",
        "prev_close": "PREVCLOSE", "volume": "TOTTRDQTY", "value": "TOTTRDVAL", "trades": "TOTALTRADES", "date": "TIMESTAMP"}
_NEW = {"symbol": "TckrSymb", "series": "SctySrs", "isin": "ISIN", "open": "OpnPric", "high": "HghPric", "low": "LwPric", "close": "ClsPric",
        "prev_close": "PrvsClsgPric", "volume": "TtlTradgVol", "value": "TtlTrfVal", "trades": "TtlNbOfTxsExctd", "date": "TradDt"}


def price_rows(zipped: bytes) -> list[dict]:
    """Company shares only (EQ series, ISIN starting INE; funds and ETFs start INF), in NSE's order,
    values as text exactly as given."""
    z = zipfile.ZipFile(io.BytesIO(zipped))
    text = z.read(z.namelist()[0]).decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    cols = _NEW if "TckrSymb" in (reader.fieldnames or []) else _OLD
    rows = []
    for r in reader:
        if (r.get(cols["series"]) or "").strip() != "EQ" or not (r.get(cols["isin"]) or "").strip().startswith("INE"):
            continue
        row = {k: (r.get(v) or "").strip() for k, v in cols.items() if k != "series"}
        row["date"] = _date(row["date"]).isoformat()
        rows.append(row)
    return rows


def index_rows(text: bytes, names=("Nifty 500", "Nifty 50")) -> list[dict]:
    out = []
    for r in csv.DictReader(io.StringIO(text.decode("latin-1"))):
        name = (r.get("Index Name") or "").strip()
        if name in names:
            out.append({"date": _date(r["Index Date"].strip()).isoformat(), "index": name,
                        "open": r["Open Index Value"].strip(), "high": r["High Index Value"].strip(),
                        "low": r["Low Index Value"].strip(), "close": r["Closing Index Value"].strip()})
    return out


_SPLIT = re.compile(r"split.*?from\s+(?:rs\.?|re\.?)\s*([\d.]+).*?to\s+(?:rs\.?|re\.?)\s*([\d.]+)", re.I)
_BONUS = re.compile(r"bonus\s*(\d+)\s*:\s*(\d+)", re.I)
_RESTART = re.compile(r"demerger|scheme of arrangement|capital reduction", re.I)


def corporate_actions(body: bytes) -> list[dict]:
    """Splits, bonuses and series restarts, with their factor (new shares per old). Others ignored."""
    out = []
    for a in json.loads(body):
        if a.get("series") != "EQ":
            continue
        subject = " ".join((a.get("subject") or "").split())
        kind, factor = parse_subject(subject)
        if kind:
            out.append({"symbol": a["symbol"], "ex_date": _date(a["exDate"]).isoformat(),
                        "kind": kind, "factor": factor, "subject": subject})
    return out


def parse_subject(subject: str) -> tuple[str | None, float]:
    m = _SPLIT.search(subject)
    if m:
        old, new = float(m.group(1)), float(m.group(2))
        return (SPLIT, old / new) if new > 0 and old > new else (None, 1.0)
    m = _BONUS.search(subject)
    if m:
        new, held = int(m.group(1)), int(m.group(2))
        return (BONUS, (new + held) / held) if held > 0 else (None, 1.0)
    if _RESTART.search(subject):
        return RESTART, 1.0
    return None, 1.0


def holidays(body: bytes) -> set[dt.date]:
    """Trading holidays for ordinary shares (NSE's "CM" segment)."""
    return {_date(h["tradingDate"]) for h in json.loads(body).get("CM", [])}


def symbol_changes(body: bytes) -> list[tuple[str, str, dt.date]]:
    """(old symbol, new symbol, date) from NSE's symbol-change list (no header row)."""
    out = []
    for row in csv.reader(io.StringIO(body.decode("latin-1"))):
        if len(row) >= 4:
            try:
                out.append((row[-3].strip(), row[-2].strip(), _date(row[-1].strip())))
            except ValueError:
                continue
    return out


def _date(s: str) -> dt.date:
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d-%b-%y"):  # "%d-%b-%y": e.g. 13-Jul-20 in some 2020 files
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date {s!r}")
