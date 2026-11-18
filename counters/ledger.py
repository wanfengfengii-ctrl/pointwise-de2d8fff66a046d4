import sqlite3
from pathlib import Path

from counters.codec import decode_counter_revision, encode_counter_revision
from counters.revisions import CounterReceipt, CounterRevision


class CounterRevisionConflict(ValueError):
    """This counter revision already has different registered content."""


class CounterLedger:
    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(path, isolation_level=None)
        try:
            self.initialize()
        except BaseException:
            self._db.close()
            raise

    def initialize(self) -> None:
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS counter_revisions (
                day TEXT NOT NULL,
                revision TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (day, revision)
            ) WITHOUT ROWID
        ''')

    def put(self, revision: CounterRevision) -> CounterReceipt:
        with self._db:
            self._db.execute('BEGIN IMMEDIATE')
            existing = self.get(revision.day, revision.revision)
            if existing is not None:
                if not existing.same_counts(revision):
                    raise CounterRevisionConflict(
                        f'counter revision {revision.day}/{revision.revision} already exists'
                    )
                return existing.receipt
            self._db.execute(
                'INSERT INTO counter_revisions (day, revision, payload) VALUES (?, ?, ?)',
                (revision.day, revision.revision, encode_counter_revision(revision)),
            )
        return revision.receipt

    def get(self, day: str, revision: str) -> CounterRevision | None:
        row = self._db.execute(
            'SELECT payload FROM counter_revisions WHERE day = ? AND revision = ?',
            (day, revision),
        ).fetchone()
        return decode_counter_revision(row[0]) if row is not None else None

    def close(self) -> None:
        self._db.close()
