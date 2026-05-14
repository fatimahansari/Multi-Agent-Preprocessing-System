"""Pytest configuration: make the package root importable without installation."""

import sys
from pathlib import Path

# Ensure `aai_mas_preprocessing/` is on sys.path so that bare imports like
# `from core.agent_base import BaseAgent` resolve correctly when pytest is
# invoked from the project root or from inside the package directory.
_PACKAGE_ROOT = Path(__file__).parent.resolve()
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))
