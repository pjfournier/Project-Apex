from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from apex.journal import JournalStore
from apex.projections import ProjectionService

ROOT = Path(__file__).resolve().parents[2]
EVENTS_FIXTURE = ROOT / "fixtures" / "journals" / "m2_projection_events.json"
SNAPSHOTS_FIXTURE = ROOT / "fixtures" / "journals" / "m2_projection_snapshots.json"


class SteppingClock:
    def __init__(self) -> None:
        self._next = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        value = self._next
        self._next += timedelta(microseconds=1)
        return value


def test_golden_projection_replay_matches_reviewed_snapshots(tmp_path: Path) -> None:
    raw_events: object = json.loads(EVENTS_FIXTURE.read_text(encoding="utf-8"))
    expected: object = json.loads(SNAPSHOTS_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(raw_events, list)
    assert isinstance(expected, dict)

    with JournalStore(tmp_path / "journal.db", SteppingClock()) as journal:
        for raw_event in raw_events:
            assert isinstance(raw_event, Mapping)
            event = cast(Mapping[str, object], raw_event)
            actor = event["actor"]
            event_type = event["type"]
            assert isinstance(actor, str)
            assert isinstance(event_type, str)
            journal.append(actor, event_type, event["payload"])

        service = ProjectionService(journal)
        service.rebuild_all()
        actual = {
            name: json.loads(_required_snapshot_json(journal, name)) for name in service.names
        }

    assert actual == expected


def _required_snapshot_json(journal: JournalStore, name: str) -> str:
    snapshot = journal.load_projection_snapshot(name)
    assert snapshot is not None
    return snapshot.state_json
