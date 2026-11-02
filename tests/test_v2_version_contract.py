from pathlib import Path

from b_1_2_core import ALGORITHM_VERSION
from b_1_2_core.adapter import SCHEMA_VERSION


def test_v2_version_contract_is_consistent():
    root = Path(__file__).parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert ALGORITHM_VERSION == "2.1.2"
    assert SCHEMA_VERSION == 3
    assert 'version = "2.1.2"' in pyproject
