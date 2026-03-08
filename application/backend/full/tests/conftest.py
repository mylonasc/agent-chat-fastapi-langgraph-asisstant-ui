import sys
from pathlib import Path

# Ensure backend/full directory is on PYTHONPATH for test imports
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
