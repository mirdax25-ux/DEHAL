from pathlib import Path


def test_package_discovery_excludes_non_package_project_directories():
    root = Path(__file__).parents[1]
    config = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert '[tool.setuptools.packages.find]' in config
    assert 'include = ["bodulskihal_core*"]' in config
    assert 'exclude = ["grants*", "tests*", "examples*"]' in config
