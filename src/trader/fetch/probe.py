"""M0 data check: can this machine reach every candidate data source?

Throwaway. Records what each source returned, as received, and judges nothing.
Uses the standard library only, so it runs on a fresh machine with no installs.
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import time
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
MON = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def _nse_new(d: dt.date) -> str:
    return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"


def _nse_old(d: dt.date) -> str:
    m = MON[d.month - 1]
    return f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.year}/{m}/cm{d.day:02d}{m}{d.year}bhav.csv.zip"


def _corp_actions(year: int) -> str:
    return (
        "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
        f"&from_date=01-01-{year}&to_date=31-12-{year}"
    )


def sources(today: dt.date) -> dict[str, str]:
    recent = _last_weekday(today - dt.timedelta(days=3))
    return {
        "nse_bhavcopy_recent": _nse_new(recent),
        "nse_bhavcopy_full_recent": f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{recent:%d%m%Y}.csv",
        "nse_bhavcopy_old_2019": _nse_old(dt.date(2019, 1, 1)),
        "nse_bhavcopy_old_2010": _nse_old(dt.date(2010, 1, 4)),
        "nifty500_list": "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        "nse_corp_actions_2024": _corp_actions(2024),
        "nse_corp_actions_2012": _corp_actions(2012),
        "bse_bhavcopy_recent": f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{recent:%Y%m%d}_F_0000.CSV",
        "yahoo_chart": "https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS?range=1mo&interval=1d",
    }


def _last_weekday(d: dt.date) -> dt.date:
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def fetch(url: str) -> dict:
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            result = {"status": r.status, "bytes": len(body), "head": body[:120].decode("latin-1")}
    except urllib.error.HTTPError as e:
        result = {"status": e.code, "error": str(e)}
    except Exception as e:  # noqa: BLE001 - a probe records every failure as found
        result = {"status": None, "error": f"{type(e).__name__}: {e}"}
    result["seconds"] = round(time.monotonic() - start, 2)
    return result


def run() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    results = {}
    for name, url in sources(now.date()).items():
        results[name] = {"url": url, **fetch(url)}
        time.sleep(1)
    return {
        "probed_at": now.isoformat(timespec="seconds"),
        "machine": {"python": sys.version.split()[0], "platform": platform.platform()},
        "sources": results,
    }


def summary(report: dict) -> str:
    lines = [f"probed_at {report['probed_at']}  python {report['machine']['python']}"]
    for name, r in report["sources"].items():
        lines.append(f"  {name:28} {r['status']!s:5} {r.get('bytes', r.get('error', ''))}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
