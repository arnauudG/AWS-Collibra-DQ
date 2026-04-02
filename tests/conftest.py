from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from collibra_dq_starter import orchestrator


@pytest.fixture(autouse=True)
def reset_project_root_cache() -> None:
    # Keep tests isolated from global module cache.
    orchestrator._PROJECT_ROOT_CACHE = None
    yield
    orchestrator._PROJECT_ROOT_CACHE = None
