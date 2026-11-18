import sqlite3
from pathlib import Path

from routes.snapshot import (
    RouteReceipt, RouteRevision, decode_route_revision, encode_route_revision,
)


class RouteRevisionConflict(ValueError):
    """This route revision already has a different registered definition."""


class RouteCatalog:
    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(path, isolation_level=None)
        try:
            self.initialize()
        except BaseException:
            self._db.close()
            raise

    def initialize(self) -> None:
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS route_revisions (
                day TEXT NOT NULL,
                revision TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (day, revision)
            ) WITHOUT ROWID
        ''')

    def put(self, revision: RouteRevision) -> RouteReceipt:
        with self._db:
            self._db.execute('BEGIN IMMEDIATE')
            existing = self.get(revision.day, revision.revision)
            if existing is not None:
                if not existing.same_definition(revision):
                    raise RouteRevisionConflict(
                        f'route revision {revision.day}/{revision.revision} already exists'
                    )
                return existing.receipt
            self._db.execute(
                'INSERT INTO route_revisions (day, revision, payload) VALUES (?, ?, ?)',
                (revision.day, revision.revision, encode_route_revision(revision)),
            )
        return revision.receipt

    def get(self, day: str, revision: str) -> RouteRevision | None:
        row = self._db.execute(
            'SELECT payload FROM route_revisions WHERE day = ? AND revision = ?',
            (day, revision),
        ).fetchone()
        return decode_route_revision(row[0]) if row is not None else None

    def close(self) -> None:
        self._db.close()
