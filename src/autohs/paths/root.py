"""Locate the AutoHS repository root from a source checkout."""

from pathlib import Path


def repo_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "autohs").is_dir():
            return parent
    raise RuntimeError("找不到 AutoHS 仓库根目录")
