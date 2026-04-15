"""Repository-local `.env` loading helpers."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _normalize_env_value(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1].strip()
    return normalized


def load_repo_dotenv(
    *,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Load repo-root `.env` into the provided environment mapping.

    Existing process environment values win over `.env` values.
    """
    target = os.environ if environ is None else environ
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return dict(target)

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in target:
            continue
        target[key] = _normalize_env_value(value)

    return dict(target)
