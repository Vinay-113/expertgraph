"""Source-tree launcher, independent of editable-install .pth handling."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from expertgraph.cli import main

if __name__ == "__main__":
    main()
