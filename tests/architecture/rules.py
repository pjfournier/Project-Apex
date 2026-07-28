"""AST-based architecture rules for Project Apex."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    rule: str
    detail: str


_POLICY_FORBIDDEN_ROOTS = {
    "anthropic",
    "datetime",
    "google.generativeai",
    "http",
    "openai",
    "os",
    "random",
    "requests",
    "socket",
    "time",
    "urllib",
}
_MUTABLE_FACTORIES = {"defaultdict", "deque", "dict", "list", "set"}
_SQL_WRITE = re.compile(r"\b(?:INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|REPLACE)\b", re.IGNORECASE)


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(tree: ast.AST) -> Iterable[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from ((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                yield (
                    node.lineno,
                    (node.module if alias.name == "*" else f"{node.module}.{alias.name}"),
                )


def _is_mutable(node: ast.expr) -> bool:
    if isinstance(node, (ast.Dict, ast.List, ast.Set)):
        return True
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id in _MUTABLE_FACTORIES
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in _MUTABLE_FACTORIES
    return False


def check_file(path: Path, source_root: Path) -> list[Violation]:
    module = _module_name(path, source_root)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []

    for line, imported in _imports(tree):
        if imported.startswith("apex.adapters.tools") and module != "apex.enforcement.pep":
            violations.append(
                Violation(path, line, "tool-adapter-monopoly", f"{module} imports {imported}")
            )
        if module.startswith("apex.policy") and (
            imported.startswith(("apex.adapters", "apex.runtime"))
            or any(
                imported == root or imported.startswith(f"{root}.")
                for root in _POLICY_FORBIDDEN_ROOTS
            )
        ):
            violations.append(
                Violation(path, line, "policy-purity", f"{module} imports {imported}")
            )
        if module.startswith("apex.control") and imported.startswith(
            ("apex.adapters.tools", "apex.runtime.executor")
        ):
            violations.append(
                Violation(path, line, "control-boundary", f"{module} imports {imported}")
            )
        if (
            module.startswith("apex.journal")
            and imported.startswith("apex.")
            and not imported.startswith("apex.ports")
        ):
            violations.append(
                Violation(path, line, "journal-foundation", f"{module} imports {imported}")
            )

    for node in ast.walk(tree):
        if module != "apex.ports" and isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name in {
                "date.today",
                "datetime.now",
                "datetime.utcnow",
                "datetime.datetime.now",
                "time.monotonic",
                "time.perf_counter",
                "time.time",
            }:
                violations.append(Violation(path, node.lineno, "ambient-clock", name))
        if (
            module != "apex.journal.store"
            and isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _SQL_WRITE.search(node.value)
        ):
            violations.append(
                Violation(path, node.lineno, "sql-location", "SQL write outside journal.store")
            )

    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
        if value is not None and _is_mutable(value):
            violations.append(
                Violation(path, node.lineno, "module-mutable-state", ast.unparse(value))
            )

    return violations


def check_tree(source_root: Path) -> list[Violation]:
    return [
        violation
        for path in sorted((source_root / "apex").rglob("*.py"))
        for violation in check_file(path, source_root)
    ]
