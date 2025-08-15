# Optional Langfuse tracing bootstrap (no-op by default)
from typing import Optional

try:
    from langfuse import Langfuse  # type: ignore
except Exception:  # pragma: no cover - dependency optional
    Langfuse = None  # type: ignore

lf: Optional[object] = None

# Intentionally keep lazy; wire with env vars in config if needed.
