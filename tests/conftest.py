import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os  # noqa: E402

# stage 5: the app must not ask GitHub for updates while the tests run (the silent start-up check)
os.environ.setdefault("SE_NO_UPDATE_CHECK", "1")
