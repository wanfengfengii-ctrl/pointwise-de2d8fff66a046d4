import sqlite3
from collections.abc import Callable
from pathlib import Path

from archive.artifacts import SealedBatch, encode_sealed_batch
from archive.receipts import PublicationReceipt, encode_receipt, receipt_matches_batch

ARCHIVE_VERSION = 1
MAX_ARTIFACT_ID = (1 << 63) - 1
PublicationBuilder = Callable[[int], tuple[SealedBatch, PublicationReceipt]]
BeforeCommit = Callable[[int], None]


class ArchiveVersionError(RuntimeError):
    """The archive schema version is unsupported."""


class ArchiveStore:
    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(path, isolation_level=None)
        self._pending_id: int | None = None
        try:
            self._db.execute('PRAGMA foreign_keys = ON')
            self.initialize()
        except BaseException:
            self._db.close()
            raise

    def initialize(self) -> None:
        if self._db.in_transaction:
            raise RuntimeError('cannot initialize during an archive transaction')
        with self._db:
            self._db.execute('BEGIN IMMEDIATE')
            version = self._db.execute('PRAGMA user_version').fetchone()[0]
            if version == ARCHIVE_VERSION:
                return
            if version != 0:
                raise ArchiveVersionError(f'unsupported archive version {version}')
            self._db.execute('''
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id INTEGER PRIMARY KEY CHECK (artifact_id > 0),
                    payload TEXT NOT NULL
                )
            ''')
            self._db.execute('''
                CREATE TABLE IF NOT EXISTS receipts (
                    artifact_id INTEGER PRIMARY KEY REFERENCES artifacts (artifact_id),
                    payload TEXT NOT NULL
                )
            ''')
            self._db.execute(f'PRAGMA user_version = {ARCHIVE_VERSION}')

    def commit_publication(
        self, build: PublicationBuilder, before_commit: BeforeCommit | None = None,
    ) -> int:
        if self._db.in_transaction:
            raise RuntimeError('cannot publish during an archive transaction')
        try:
            with self._db:
                self._db.execute('BEGIN IMMEDIATE')
                previous = self._db.execute(
                    'SELECT COALESCE(MAX(artifact_id), 0) FROM artifacts'
                ).fetchone()[0]
                artifact_id = previous + 1
                if artifact_id > MAX_ARTIFACT_ID:
                    raise OverflowError('archive artifact identifiers are exhausted')
                self._pending_id = artifact_id
                batch, receipt = build(artifact_id)
                if batch.artifact_id != artifact_id or not receipt_matches_batch(receipt, batch):
                    raise ValueError('publication materials do not match the allocated artifact')
                self._db.execute(
                    'INSERT INTO artifacts (artifact_id, payload) VALUES (?, ?)',
                    (artifact_id, encode_sealed_batch(batch)),
                )
                self._db.execute(
                    'INSERT INTO receipts (artifact_id, payload) VALUES (?, ?)',
                    (artifact_id, encode_receipt(receipt)),
                )
                if before_commit is not None:
                    before_commit(artifact_id)
            return artifact_id
        finally:
            self._pending_id = None

    def read_publication(self, artifact_id: int) -> tuple[str | None, str | None]:
        if type(artifact_id) is not int or not 1 <= artifact_id <= MAX_ARTIFACT_ID:
            return None, None
        if artifact_id == self._pending_id:
            return None, None
        return self._db.execute('''
            SELECT (SELECT payload FROM artifacts WHERE artifact_id = :id),
                   (SELECT payload FROM receipts WHERE artifact_id = :id)
        ''', {'id': artifact_id}).fetchone()

    def close(self) -> None:
        self._db.close()
