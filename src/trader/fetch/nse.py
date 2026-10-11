"""Downloads from NSE, exactly as received, with a receipt for every item.

IPv4 only, short timeouts, one request at a time (decision 0007).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import http.client
import socket
import time
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
MON = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
NEW_FORMAT_FROM = dt.date(2024, 7, 8)
PAUSE_SECONDS = 0.4


def price_file_url(d: dt.date) -> str:
    if d >= NEW_FORMAT_FROM:
        return f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    m = MON[d.month - 1]
    return f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.year}/{m}/cm{d.day:02d}{m}{d.year}bhav.csv.zip"


def index_file_url(d: dt.date) -> str:
    return f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"


HOLIDAYS_URL = "https://www.nseindia.com/api/holiday-master?type=trading"
SYMBOL_CHANGES_URL = "https://nsearchives.nseindia.com/content/equities/symbolchange.csv"


def corporate_actions_url(start: dt.date, end: dt.date) -> str:
    return (
        "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
        f"&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}"
    )


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addr = socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)[0][4]
        sock = socket.create_connection(addr, self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_IPv4HTTPSConnection, req, context=self._context)


_opener = urllib.request.build_opener(_IPv4HTTPSHandler())


def get(item: str, url: str, attempts: int = 3, timeout: float = 20) -> tuple[bytes | None, dict]:
    """Returns the body (or None) and a receipt line for it. Never raises for network trouble."""
    receipt = {"item": item, "url": url, "attempts": 0}
    for attempt in range(1, attempts + 1):
        receipt["attempts"] = attempt
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with _opener.open(req, timeout=timeout) as r:
                body = r.read()
            time.sleep(PAUSE_SECONDS)
            receipt.update(status="ok", http=200, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            return body, receipt
        except urllib.error.HTTPError as e:
            receipt.update(status="missing" if e.code == 404 else "failed", http=e.code, error=str(e))
            if e.code == 404:
                break
        except Exception as e:  # noqa: BLE001 - every failure is recorded on the receipt
            receipt.update(status="failed", http=None, error=f"{type(e).__name__}: {e}")
        time.sleep(PAUSE_SECONDS * 2 * attempt)
    return None, receipt
