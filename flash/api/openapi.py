"""Write the API's OpenAPI document to a file.

    python -m flash.api.openapi                 # writes docs/openapi.json
    python -m flash.api.openapi path/to/file.json

The running API serves the same document at ``/openapi.json`` (with Swagger UI
at ``/docs`` and ReDoc at ``/redoc``). The copy in ``docs/`` lets people read or
generate clients from it without running anything; a test keeps it up to date.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from ..service import FlashService
from ..storage import JsonStore
from .app import create_app
from .config import ApiConfig

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def build_schema() -> dict:
    """The OpenAPI document as a dict, built without touching the real data folder."""
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(FlashService(JsonStore(tmp)), ApiConfig(log_level="WARNING"))
        return app.openapi()


def render(schema: dict) -> str:
    """The document as stable, readable JSON (same input, same text), ending with a newline."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the document to the path in ``argv`` or to ``docs/openapi.json``."""
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else DEFAULT_PATH
    path.write_text(render(build_schema()), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
