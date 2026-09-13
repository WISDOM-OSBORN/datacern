"""`datacern-web` launcher: starts the Streamlit UI programmatically."""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.web import cli as stcli


def main(argv: list[str] | None = None) -> int:
    app = Path(__file__).with_name("streamlit_app.py")
    args = ["streamlit", "run", str(app), "--server.headless", "true"]
    if argv:
        args.extend(argv)
    sys.argv = args
    stcli.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
