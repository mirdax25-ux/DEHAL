from pathlib import Path
import tomllib


def test_package_discovery_excludes_non_package_project_directories():
    root = Path(__file__).parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    find = config["tool"]["setuptools"]["packages"]["find"]

    assert find["include"] == ["bodulskihal_core*"]
    assert "grants*" in find["exclude"]
    assert "tests*" in find["exclude"]
    assert "examples*" in find["exclude"]
