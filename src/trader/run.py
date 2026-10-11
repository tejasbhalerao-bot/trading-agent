"""The one entry point the cloud routines may run.

    python3 src/trader/run.py probe      M0 data check: probe sources, record, publish
    python3 src/trader/run.py propose    (M3)
    python3 src/trader/run.py finalize   (M3)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO / "src"))

from trader.fetch import probe  # noqa: E402
from trader.store import Store  # noqa: E402
from trader.store.publish import publish  # noqa: E402


def cmd_probe(no_publish: bool = False) -> int:
    report = probe.run()
    print(probe.summary(report))
    stamp = report["probed_at"].replace(":", "").replace("+0000", "Z")
    path = Store(REPO).writer("fetch").add_file(
        f"_probe/{stamp}.json", (json.dumps(report, indent=2) + "\n").encode()
    )
    print(f"recorded {path.relative_to(REPO)}")
    if not no_publish:
        print(f"published {publish(REPO, f'M0 data check {stamp}') or 'nothing'}")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["probe"]:
        return cmd_probe(no_publish="--no-publish" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
