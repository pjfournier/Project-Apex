"""SQLite-backed append-only Journal storage."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC
from pathlib import Path
from typing import Literal, Protocol

from apex.ports import Clock

from .chain import (
    GENESIS_HASH,
    ChainReport,
    compute_event_hash,
    payload_json,
    recompute_event_hash,
)
from .errors import (
    EventNotFoundError,
    InvalidEnvelopeError,
    JournalError,
    JournalWriteError,
    StoredEventCorruptionError,
)
from .events import Event
from .json_types import JsonObject, freeze_json, freeze_object
from .registry import registered_schema, validate_payload
from .ulid import new_monotonic_ulid

AppendStage = Literal["transaction_started", "row_inserted"]


class AppendObserver(Protocol):
    """Observe transactional append stages for interruption testing."""

    def reached(self, stage: AppendStage) -> None:
        """Observe an append stage."""
        ...


class JournalStore:
    """One-connection, one-writer SQLite Journal."""

    def __init__(
        self,
        path: Path,
        clock: Clock,
        *,
        append_observer: AppendObserver | None = None,
    ) -> None:
        self._path = path
        self._clock = clock
        self._append_observer = append_observer
        try:
            self._connection = sqlite3.connect(path, isolation_level=None)
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
            self._connection.set_authorizer(self._authorize)
        except sqlite3.Error as error:
            raise JournalWriteError(f"failed to initialize Journal at {path}") from error

    def __enter__(self) -> JournalStore:
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the owned SQLite connection."""
        self._connection.close()

    def append(
        self,
        actor: str,
        event_type: str,
        payload: object,
        *,
        session_id: str | None = None,
        turn_id: str | None = None,
        caused_by: str | None = None,
    ) -> Event:
        """Validate and atomically append one event."""
        frozen_value = freeze_json(payload)
        schema = registered_schema(event_type)
        validate_payload(schema, frozen_value)
        if not isinstance(frozen_value, Mapping):
            raise InvalidEnvelopeError("registered event payload must be an object")
        frozen_payload: JsonObject = frozen_value
        timestamp = self._clock.now()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidEnvelopeError("Clock must return an aware datetime")
        timestamp = timestamp.astimezone(UTC)

        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._observe("transaction_started")
            previous = self._head_row()
            seq = 1 if previous is None else previous[0] + 1
            previous_event_id = None if previous is None else previous[2]
            prev_hash = GENESIS_HASH if previous is None else previous[1]
            event_id = new_monotonic_ulid(timestamp, seq, previous_event_id)
            ts = timestamp.isoformat(timespec="microseconds").replace("+00:00", "Z")
            event_hash = compute_event_hash(
                event_id=event_id,
                seq=seq,
                ts=ts,
                actor=actor,
                event_type=event_type,
                schema_version=schema.schema_version,
                session_id=session_id,
                turn_id=turn_id,
                caused_by=caused_by,
                payload=frozen_payload,
                prev_hash=prev_hash,
            )
            event = Event(
                event_id=event_id,
                seq=seq,
                ts=ts,
                actor=actor,
                type=event_type,
                schema_version=schema.schema_version,
                session_id=session_id,
                turn_id=turn_id,
                caused_by=caused_by,
                payload=frozen_payload,
                prev_hash=prev_hash,
                hash=event_hash,
            )
            self._connection.execute(
                """
                INSERT INTO events (
                    event_id, seq, ts, actor, type, schema_version,
                    session_id, turn_id, caused_by, payload, prev_hash, hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.seq,
                    event.ts,
                    event.actor,
                    event.type,
                    event.schema_version,
                    event.session_id,
                    event.turn_id,
                    event.caused_by,
                    payload_json(event.payload),
                    event.prev_hash,
                    event.hash,
                ),
            )
            self._observe("row_inserted")
            self._connection.execute("COMMIT")
            return event
        except sqlite3.Error as error:
            self._rollback()
            raise JournalWriteError("atomic Journal append failed") from error
        except BaseException:
            self._rollback()
            raise

    def read_range(
        self,
        from_seq: int,
        to_seq: int | None = None,
        types: Sequence[str] | None = None,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> Iterator[Event]:
        """Read a filtered, ascending sequence range."""
        clauses = ["seq >= ?"]
        parameters: list[object] = [max(1, from_seq)]
        if to_seq is not None:
            clauses.append("seq <= ?")
            parameters.append(to_seq)
        if types:
            placeholders = ", ".join("?" for _ in types)
            clauses.append(f"type IN ({placeholders})")
            parameters.extend(types)
        if session_id is not None:
            clauses.append("session_id = ?")
            parameters.append(session_id)
        if turn_id is not None:
            clauses.append("turn_id = ?")
            parameters.append(turn_id)
        query = f"""
            SELECT event_id, seq, ts, actor, type, schema_version,
                   session_id, turn_id, caused_by, payload, prev_hash, hash
            FROM events
            WHERE {" AND ".join(clauses)}
            ORDER BY seq ASC
        """
        try:
            rows = self._connection.execute(query, parameters).fetchall()
        except sqlite3.Error as error:
            raise StoredEventCorruptionError("failed to read Journal range") from error
        events = tuple(self._row_to_event(row) for row in rows)
        return iter(events)

    def head(self) -> tuple[int, str]:
        """Return the current sequence and head hash."""
        row = self._head_row()
        return (0, GENESIS_HASH) if row is None else (row[0], row[1])

    def verify_chain(self, from_seq: int = 0, to_seq: int | None = None) -> ChainReport:
        """Recompute a range and report its first divergence."""
        start = max(1, from_seq)
        expected_prev = GENESIS_HASH
        if start > 1:
            prior = self._connection.execute(
                "SELECT hash FROM events WHERE seq = ?", (start - 1,)
            ).fetchone()
            if prior is None or not isinstance(prior[0], str):
                return ChainReport(False, start, start - 1, start, "missing predecessor")
            expected_prev = prior[0]

        rows = self._connection.execute(
            """
            SELECT event_id, seq, ts, actor, type, schema_version,
                   session_id, turn_id, caused_by, payload, prev_hash, hash
            FROM events
            WHERE seq >= ? AND (? IS NULL OR seq <= ?)
            ORDER BY seq ASC
            """,
            (start, to_seq, to_seq),
        ).fetchall()
        expected_seq = start
        checked_to = start - 1
        for row in rows:
            row_seq = _required_int(row[1], "seq")
            if row_seq != expected_seq:
                return ChainReport(False, start, checked_to, expected_seq, "sequence gap")
            try:
                event = self._row_to_event(row)
            except (InvalidEnvelopeError, StoredEventCorruptionError) as error:
                return ChainReport(False, start, checked_to, row_seq, str(error))
            if event.prev_hash != expected_prev:
                return ChainReport(False, start, checked_to, row_seq, "previous hash mismatch")
            if recompute_event_hash(event) != event.hash:
                return ChainReport(False, start, checked_to, row_seq, "event hash mismatch")
            expected_prev = event.hash
            expected_seq += 1
            checked_to = row_seq
        return ChainReport(True, start, checked_to, None, None)

    def walk_caused_by(self, event_id: str) -> tuple[Event, ...]:
        """Walk an event's causal chain from effect back to origin."""
        chain: list[Event] = []
        seen: set[str] = set()
        current_id: str | None = event_id
        while current_id is not None:
            if current_id in seen:
                raise StoredEventCorruptionError("caused_by cycle detected")
            seen.add(current_id)
            event = self._event_by_id(current_id)
            chain.append(event)
            current_id = event.caused_by
        return tuple(chain)

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT NOT NULL UNIQUE,
                seq INTEGER NOT NULL PRIMARY KEY CHECK (seq > 0),
                ts TEXT NOT NULL,
                actor TEXT NOT NULL,
                type TEXT NOT NULL,
                schema_version INTEGER NOT NULL CHECK (schema_version > 0),
                session_id TEXT,
                turn_id TEXT,
                caused_by TEXT,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL,
                FOREIGN KEY (caused_by) REFERENCES events(event_id)
            ) STRICT;

            CREATE TRIGGER IF NOT EXISTS events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'events are append-only');
            END;
            """
        )

    def _head_row(self) -> tuple[int, str, str] | None:
        row = self._connection.execute(
            "SELECT seq, hash, event_id FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return (
            _required_int(row[0], "seq"),
            _required_str(row[1], "hash"),
            _required_str(row[2], "event_id"),
        )

    def _event_by_id(self, event_id: str) -> Event:
        row = self._connection.execute(
            """
            SELECT event_id, seq, ts, actor, type, schema_version,
                   session_id, turn_id, caused_by, payload, prev_hash, hash
            FROM events WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        if row is None:
            raise EventNotFoundError(f"event {event_id!r} does not exist")
        return self._row_to_event(row)

    def _row_to_event(self, row: Sequence[object]) -> Event:
        try:
            raw_payload: object = json.loads(_required_str(row[9], "payload"))
            payload = freeze_object(raw_payload)
            return Event(
                event_id=_required_str(row[0], "event_id"),
                seq=_required_int(row[1], "seq"),
                ts=_required_str(row[2], "ts"),
                actor=_required_str(row[3], "actor"),
                type=_required_str(row[4], "type"),
                schema_version=_required_int(row[5], "schema_version"),
                session_id=_optional_str(row[6], "session_id"),
                turn_id=_optional_str(row[7], "turn_id"),
                caused_by=_optional_str(row[8], "caused_by"),
                payload=payload,
                prev_hash=_required_str(row[10], "prev_hash"),
                hash=_required_str(row[11], "hash"),
            )
        except (IndexError, TypeError, ValueError, JournalError) as error:
            raise StoredEventCorruptionError("stored event row is invalid") from error

    def _observe(self, stage: AppendStage) -> None:
        if self._append_observer is not None:
            self._append_observer.reached(stage)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            self._connection.execute("ROLLBACK")

    @staticmethod
    def _authorize(
        action: int,
        argument_one: str | None,
        argument_two: str | None,
        database: str | None,
        source: str | None,
    ) -> int:
        del argument_two, database, source
        if argument_one == "events" and action in {sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_DROP_TRIGGER and argument_one in {
            "events_no_update",
            "events_no_delete",
        }:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK


def _required_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise StoredEventCorruptionError(f"{field} is not text")
    return value


def _optional_str(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _required_str(value, field)


def _required_int(value: object, field: str) -> int:
    if not isinstance(value, int):
        raise StoredEventCorruptionError(f"{field} is not an integer")
    return value
