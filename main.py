#!/usr/bin/python3
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from transfercachyos.__main__ import main

    sys.exit(main())
