import sqlite3
from contextlib import closing

from accounts.bounds import bounds
from archive.lookup import ArchiveConsistencyError, get_sealed_batch, read_receipt
from archive.receipts import PublicationReceipt
from archive.store import ArchiveStore
from counters.ledger import CounterLedger
from routes.catalog import RouteCatalog
from tests import DAY, DIAGONAL, FULL, INTO_X, WarehouseCase, archive_ids


class ArchiveTests(WarehouseCase):
    def use_disk_warehouse(self):
        root = self.directory()
        self.counters = self.database(CounterLedger, root / 'counters.sqlite')
        self.routes = self.database(RouteCatalog, root / 'routes.sqlite')
        self.archive = self.database(ArchiveStore, root / 'archive.sqlite')
        return root / 'archive.sqlite'

    def test_reopen_with_source_offline(self):
        path = self.use_disk_warehouse()
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, FULL)
        old = self.seal()
        original_receipt = read_receipt(self.archive, old)
        original_bound = bounds(self.archive, old, INTO_X)
        self.assertEqual(original_receipt, PublicationReceipt(old, DAY, 'c1', 'r1', 2, 2))
        self.assertEqual(original_bound, [1, 1])
        self.register({'A': 2, 'B': 1}, {'X': 2, 'Y': 1}, DIAGONAL, counts='c2', routes='r2')
        self.close_sources()
        self.archive.close()

        reopened = self.database(ArchiveStore, path)
        reopened.initialize()
        self.assertEqual(read_receipt(reopened, old), original_receipt)
        self.assertEqual(bounds(reopened, old, INTO_X), original_bound)
        self.assertEqual(bounds(reopened, old, DIAGONAL), [0, 2])
        self.assertEqual(get_sealed_batch(reopened, old).evidence.open_routes, FULL)
        self.assertEqual(archive_ids(path), ((old,), (old,)))

    def test_published_successor(self):
        path = self.use_disk_warehouse()
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, FULL)
        old = self.seal()
        self.register({'A': 2, 'B': 1}, {'X': 2, 'Y': 1}, DIAGONAL, counts='c2', routes='r2')
        new = self.seal('c2', 'r2')
        self.assertNotEqual(old, new)
        self.close_sources()
        self.archive.close()

        reopened = self.database(ArchiveStore, path)
        expected = {
            old: (PublicationReceipt(old, DAY, 'c1', 'r1', 2, 2), [1, 1], FULL),
            new: (PublicationReceipt(new, DAY, 'c2', 'r2', 3, 3), [2, 2], DIAGONAL),
        }
        for artifact in (new, old, new, old):
            receipt, interval, opened = expected[artifact]
            self.assertEqual(read_receipt(reopened, artifact), receipt)
            self.assertEqual(bounds(reopened, artifact, INTO_X), interval)
            self.assertEqual(get_sealed_batch(reopened, artifact).evidence.open_routes, opened)
        ids = tuple(sorted((old, new)))
        self.assertEqual(archive_ids(path), (ids, ids))

    def test_incomplete_publication_is_a_storage_error(self):
        path = self.use_disk_warehouse()
        self.register({'A': 3}, {'X': 3}, [('A', 'X')])
        artifact = self.seal()
        self.archive.close()
        with closing(sqlite3.connect(path)) as editor, editor:
            editor.execute('DELETE FROM receipts WHERE artifact_id = ?', (artifact,))
        reopened = self.database(ArchiveStore, path)
        with self.assertRaises(ArchiveConsistencyError):
            read_receipt(reopened, artifact)
        with self.assertRaises(ArchiveConsistencyError):
            bounds(reopened, artifact, [('A', 'X')])
