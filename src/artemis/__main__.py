"""Module entrypoint enabling 'python -m artemis' execution."""

from __future__ import annotations

import sys

from artemis.cli import main

if __name__ == "__main__":
    sys.exit(main())
