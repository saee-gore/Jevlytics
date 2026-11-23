"""Static security checks over the repository. These fail the build if a control is weakened."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),  # Anthropic-style key
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
]
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".sql",
    ".ini",
    ".example",
    ".jsonl",
    ".csv",
}


def _tracked_files() -> list[Path]:
    skip_dirs = {".venv", ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    files = []
    for path in ROOT.rglob("*"):
        if path.is_file() and not any(part in skip_dirs for part in path.parts):
            files.append(path)
    return files


def test_gitignore_excludes_env_files() -> None:
    lines = {line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
    assert ".env" in lines
    assert ".env.*" in lines
    assert "!.env.example" in lines


def test_env_example_contains_no_real_secret_values() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            if key.endswith(("_KEY", "_SECRET")):
                assert value.strip() == "", f"{key} must be blank in .env.example"


def test_no_secret_shaped_strings_anywhere_in_repo() -> None:
    offenders = []
    for path in _tracked_files():
        if path.suffix not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        if path.name == "test_repo_hygiene.py":
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                offenders.append(f"{path.relative_to(ROOT)} matches {pattern.pattern[:30]}")
    assert offenders == []


def test_env_file_is_excluded_from_version_control() -> None:
    """A local .env with real keys may exist on a developer machine. It must never be tracked."""
    lines = [line.strip() for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert ".env" in lines, ".env must be listed in .gitignore"
    if (ROOT / ".git").exists() and shutil.which("git"):
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0, "a real .env is tracked by git and must be removed from the index"


def _app_python_files() -> list[Path]:
    return sorted(APP.rglob("*.py"))


@pytest.mark.parametrize("path", _app_python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_app_code_does_not_execute_shell_or_dynamic_code(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_calls = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in banned_calls, f"{path.name}: {node.func.id}()"
        if isinstance(node, ast.Import):
            assert all(alias.name != "subprocess" for alias in node.names), path.name
        if isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess", path.name
            assert node.module not in {"os.system"}, path.name


def test_only_parameterised_text_queries_in_app_code() -> None:
    """Every text() call in app/ must use a module-level constant or a literal, never an f-string
    or a concatenation that could carry user input. The one permitted interpolation is the constant
    BASE_WHERE fragment, which contains no user data."""
    for path in _app_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "text":
                if not node.args:
                    continue
                arg = node.args[0]
                assert not isinstance(arg, ast.JoinedStr) and not isinstance(arg, ast.BinOp), (
                    f"{path.relative_to(ROOT)} builds SQL dynamically at line {node.lineno}"
                )


def test_analytics_queries_module_has_no_user_input_interpolation() -> None:
    source = (APP / "analytics" / "queries.py").read_text(encoding="utf-8")
    # The only f-string placeholder allowed is {BASE_WHERE}, a constant defined in the same module.
    placeholders = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", source))
    assert placeholders <= {"BASE_WHERE"}
