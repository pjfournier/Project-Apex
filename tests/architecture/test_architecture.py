from pathlib import Path

import pytest

from tests.architecture.rules import check_file, check_tree

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("fixtures")


def test_project_tree_obeys_architecture() -> None:
    violations = check_tree(ROOT)
    rendered = "\n".join(
        f"{item.path.relative_to(ROOT)}:{item.line}: {item.rule}: {item.detail}"
        for item in violations
    )
    assert not violations, rendered


@pytest.mark.parametrize(
    ("fixture", "expected_rule"),
    [
        ("apex/policy/clock.py", "policy-purity"),
        ("apex/policy/network.py", "policy-purity"),
        ("apex/runtime/tool_adapter.py", "tool-adapter-monopoly"),
        ("apex/control/executor.py", "control-boundary"),
        ("apex/journal/dependency.py", "journal-foundation"),
        ("apex/runtime/ambient_clock.py", "ambient-clock"),
        ("apex/runtime/sql_outside_store.py", "sql-location"),
        ("apex/runtime/mutable_singleton.py", "module-mutable-state"),
    ],
)
def test_negative_fixture_is_rejected(fixture: str, expected_rule: str) -> None:
    violations = check_file(FIXTURES / fixture, FIXTURES)
    assert expected_rule in {item.rule for item in violations}
