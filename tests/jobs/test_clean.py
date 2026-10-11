"""Clean, one test per row of the checks table in docs/design/pass4-fetch-clean.md."""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile

from trader.clean import Cleaner, parse
from trader.store import Store

D1, D2, D3 = dt.date(2025, 3, 3), dt.date(2025, 3, 4), dt.date(2025, 3, 5)
NEW_COLS = ["TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "OpnPric",
            "HghPric", "LwPric", "ClsPric", "LastPric", "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd"]
OLD_COLS = ["SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "LAST", "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL",
            "TIMESTAMP", "TOTALTRADES", "ISIN"]


def new_file(d, rows):
    """rows: (symbol, open, high, low, close, prev_close[, isin])"""
    lines = [",".join(NEW_COLS)]
    for s, o, h, l, c, p, *isin in rows:
        isin = isin[0] if isin else f"INE{s:0>9}"
        lines.append(f"{d},{d},CM,NSE,STK,1,{isin},{s},EQ,{o},{h},{l},{c},{c},{p},1000,{1000 * c},10")
    return _zip("\n".join(lines))


def old_file(d, rows):
    lines = [",".join(OLD_COLS)]
    for s, o, h, l, c, p, *isin in rows:
        isin = isin[0] if isin else f"INE{s:0>9}"
        lines.append(f"{s},EQ,{o},{h},{l},{c},{c},{p},1000,{1000 * c},{d:%d-%b-%Y},10,{isin}")
    return _zip("\n".join(lines))


def _zip(text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("f.csv", text)
    return buf.getvalue()


def cleaned(tmp_path, days, announcements=()):
    store = Store(tmp_path)
    c = Cleaner(store)
    if announcements:
        c.add_announcements(json.dumps(list(announcements)).encode(), seen=D1, backfill=False)
    for d, rows in days:
        c.clean_day(d, new_file(d, rows), None)
    skipped = store.records_all("history/skipped")
    return store, {(r["symbol"], r["date"]): r["reason"] for r in skipped}


def split(symbol, ex, ratio="From Rs 10/- Per Share To Rs 5/- Per Share"):
    return {"symbol": symbol, "series": "EQ", "exDate": f"{ex:%d-%b-%Y}", "subject": f"Face Value Split (Sub-Division) - {ratio}"}


def test_old_and_new_formats_give_identical_rows():
    rows = [("AAA", 10, 11, 9, 10.5, 10), ("BBB", 20, 21, 19, 20.5, 20)]
    assert parse.price_rows(old_file(D1, rows)) == parse.price_rows(new_file(D1, rows))


def test_funds_and_etfs_are_left_out():
    rows = parse.price_rows(new_file(D1, [("AAA", 10, 11, 9, 10, 10), ("NIFTYBEES", 10, 11, 9, 10, 10, "INF204KB14I2")]))
    assert [r["symbol"] for r in rows] == ["AAA"]


def test_inconsistent_prices_are_dont_know(tmp_path):
    _, skipped = cleaned(tmp_path, [(D1, [("AAA", 10, 9, 11, 10, 10)])])
    assert "not consistent" in skipped[("AAA", "2025-03-03")]


def test_previous_close_must_match_the_stored_close(tmp_path):
    _, skipped = cleaned(tmp_path, [(D1, [("AAA", 10, 11, 9, 10, 10)]), (D2, [("AAA", 10, 11, 9, 10, 10.4)])])
    assert "does not match stored close" in skipped[("AAA", "2025-03-04")]


def test_a_share_missing_today_is_dont_know(tmp_path):
    _, skipped = cleaned(tmp_path, [(D1, [("AAA", 10, 11, 9, 10, 10), ("BBB", 5, 6, 4, 5, 5)]),
                                    (D2, [("AAA", 10, 11, 9, 10, 10)])])
    assert skipped[("BBB", "2025-03-04")] == "not traded today"


def test_a_duplicated_share_is_dont_know(tmp_path):
    _, skipped = cleaned(tmp_path, [(D1, [("AAA", 10, 11, 9, 10, 10), ("AAA", 10, 11, 9, 10, 10)])])
    assert "more than once" in skipped[("AAA", "2025-03-03")]


def test_a_split_matching_the_price_is_stored_and_applied_only_from_its_date(tmp_path):
    store, skipped = cleaned(tmp_path, [(D1, [("AAA", 100, 101, 99, 100, 100)]), (D2, [("AAA", 50, 51, 49, 50.5, 100)])],
                             announcements=[split("AAA", D2)])
    assert not skipped
    h = store.history()
    assert h.as_of(D1).bars("AAA")[-1].close == 100     # before the split took effect: unadjusted
    assert h.as_of(D2).bars("AAA")[0].close == 50       # after: the earlier price is halved


def test_a_split_day_rising_by_a_full_price_band_still_verifies(tmp_path):
    # CGCL, 5 March 2024: a 1-for-2 split and a 1:1 bonus (4x together), then the price rose 20%.
    bonus = {"symbol": "AAA", "series": "EQ", "exDate": f"{D2:%d-%b-%Y}", "subject": "Bonus 1:1"}
    _, skipped = cleaned(tmp_path, [(D1, [("AAA", 960, 970, 950, 964.15, 960)]), (D2, [("AAA", 250, 290, 245, 289.25, 964.15)])],
                         announcements=[split("AAA", D2, "From Rs 2/- Per Share To Re 1/- Per Share"), bonus])
    assert not skipped


def test_a_split_not_matching_the_price_is_dont_know_and_history_restarts(tmp_path):
    store, skipped = cleaned(tmp_path, [(D1, [("AAA", 100, 101, 99, 100, 100)]), (D2, [("AAA", 98, 99, 97, 98, 100)]),
                                        (D3, [("AAA", 98, 99, 97, 98.5, 98)])], announcements=[split("AAA", D2)])
    assert "does not match the price move" in skipped[("AAA", "2025-03-04")]
    assert [b.date for b in store.history().as_of(D3).bars("AAA")] == [D3]


def test_a_move_beyond_35_percent_with_no_corporate_action_restarts_history(tmp_path):
    # e.g. JSW Steel, 4 Jan 2017: -90%, a 1-for-10 split missing from NSE's corporate-action list.
    store, skipped = cleaned(tmp_path, [(D1, [("AAA", 100, 101, 99, 100, 100)]), (D2, [("AAA", 10, 10.2, 9.8, 10, 100)]),
                                        (D3, [("AAA", 10, 10.3, 9.9, 10.1, 10)])])
    assert "history restarts" in skipped[("AAA", "2025-03-04")]
    assert [b.date for b in store.history().as_of(D3).bars("AAA")] == [D3]


def test_a_big_unexplained_move_sits_out_one_day_then_is_accepted(tmp_path):
    store, skipped = cleaned(tmp_path, [(D1, [("AAA", 100, 101, 99, 100, 100)]), (D2, [("AAA", 70, 71, 69, 70, 100)]),
                                        (D3, [("AAA", 70, 72, 69, 71, 70)])])
    assert "sitting out one day" in skipped[("AAA", "2025-03-04")]
    assert ("AAA", "2025-03-05") not in skipped
    assert store.history().as_of(D3).bars("AAA")[-1].close == 71


def test_a_new_cleaner_picks_up_where_the_last_one_stopped(tmp_path):
    cleaned(tmp_path, [(D1, [("AAA", 10, 11, 9, 10, 10)])])
    again = Cleaner(Store(tmp_path))
    assert again.prev_day == D1 and again.last["AAA"] == (D1, 10.0)


def test_a_rename_carries_history_but_an_old_rename_of_a_reused_symbol_does_not(tmp_path):
    store, _ = cleaned(tmp_path, [(D1, [("OLDCO", 10, 11, 9, 10, 10), ("REUSED", 5, 6, 4, 5, 5)])])
    c = Cleaner(store)
    changes = f"Old Co Ltd,OLDCO,NEWCO,{D2:%d-%b-%Y}\nSomeone Else,REUSED,OTHER,01-JAN-2010\n".encode()
    assert c.add_renames(changes, D2) == 1
    c.clean_day(D2, new_file(D2, [("NEWCO", 10, 11, 9, 10.2, 10), ("REUSED", 5, 6, 4, 5, 5)]), None)
    h = Store(tmp_path).history().as_of(D2)
    assert [b.close for b in h.bars("NEWCO")] == [10, 10.2]
    assert [b.close for b in h.bars("REUSED")] == [5, 5]


def test_dates_in_every_format_nse_has_used():
    # Some 2020 price files wrote 13-Jul-20 instead of 13-JUL-2020.
    for text in ("2020-07-13", "13-JUL-2020", "13-Jul-20", "13-07-2020"):
        assert parse._date(text) == dt.date(2020, 7, 13)


def test_an_unreadable_file_fails_its_day_and_the_next_day_carries_on(tmp_path):
    store = Store(tmp_path)
    c = Cleaner(store)
    c.clean_day(D1, new_file(D1, [("AAA", 10, 11, 9, 10, 10)]), None)
    out = c.clean_day(D2, b"not a zip file", None)
    assert out["stored"] == 0 and "could not be read" in out["failed"]
    assert Cleaner(Store(tmp_path)).prev_day == D2           # a new run does not retry the bad day forever
    c.clean_day(D3, new_file(D3, [("AAA", 10, 11, 9, 10.5, 10.2)]), None)
    assert Store(tmp_path).history().as_of(D3).bars("AAA")[-1].close == 10.5
