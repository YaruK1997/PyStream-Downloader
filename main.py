#!/usr/bin/env python3
"""PyStream-Downloader Main Entrypoint."""

import sys
from src.cli import run_app

if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        print(f"\n[Fatal Error] {e}", file=sys.stderr)
        sys.exit(1)
