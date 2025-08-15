import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'import backend' works
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force pytest-anyio to use asyncio backend (avoid requiring 'trio')
import pytest

@pytest.fixture
def anyio_backend():
    return "asyncio"
