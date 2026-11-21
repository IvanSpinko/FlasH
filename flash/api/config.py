"""Settings for the web API, read from environment variables.

Every setting has a safe default, so the API runs without any configuration.
On a server, set them in ``.env`` next to ``compose.yaml`` (see ``.env.example``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiConfig:
    """Limits that protect a public server from running out of disk or memory."""

    max_upload_mb: float = 50
    """Largest file a user may upload (``FLASH_MAX_UPLOAD_MB``). Keep nginx's ``client_max_body_size`` in step."""

    max_open_tests: int = 1000
    """How many unfinished tests are kept in memory (``FLASH_MAX_OPEN_TESTS``); the oldest go first."""

    test_idle_hours: float = 6
    """An open test nobody touched for this long is forgotten (``FLASH_TEST_IDLE_HOURS``)."""

    log_level: str = "INFO"
    """How much the API writes to its log (``FLASH_LOG_LEVEL``): DEBUG, INFO, WARNING or ERROR."""

    @property
    def max_upload_bytes(self) -> int:
        """``max_upload_mb`` in bytes."""
        return int(self.max_upload_mb * 1024 * 1024)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ApiConfig:
        """Build the settings from environment variables, falling back to the defaults.

        Raises ``ValueError`` with the variable's name when a value is not a positive number,
        so a typo in ``.env`` stops the server at start instead of failing later.
        """
        env = os.environ if env is None else env
        defaults = cls()

        def number(name: str, default: float, kind: type = float) -> float:
            raw = env.get(name, "").strip()
            if not raw:
                return default
            try:
                value = kind(raw)
            except ValueError:
                raise ValueError(f"{name} must be a number, got {raw!r}") from None
            if value <= 0:
                raise ValueError(f"{name} must be greater than 0, got {raw!r}")
            return value

        level = env.get("FLASH_LOG_LEVEL", "").strip().upper() or defaults.log_level
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ValueError(f"FLASH_LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR, got {level!r}")

        return cls(
            max_upload_mb=number("FLASH_MAX_UPLOAD_MB", defaults.max_upload_mb),
            max_open_tests=int(number("FLASH_MAX_OPEN_TESTS", defaults.max_open_tests, int)),
            test_idle_hours=number("FLASH_TEST_IDLE_HOURS", defaults.test_idle_hours),
            log_level=level,
        )
