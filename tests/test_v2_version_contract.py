from pathlib import Path

from bodulskihal_core import ALGORITHM_VERSION
from bodulskihal_core.adapter import SCHEMA_VERSION


def test_v2_version_contract_is_consistent():
    root = Path(__file__).parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert ALGORITHM_VERSION == "2.0.0"
    assert SCHEMA_VERSION == 2
    assert 'version = "2.0.0"' in pyproject
