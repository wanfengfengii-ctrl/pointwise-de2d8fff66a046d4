from accounts.bounds import bounds
from archive.lookup import UnknownArtifactError, get_sealed_batch, read_receipt
from archive.receipts import PublicationReceipt
from archive.store import ArchiveStore
from counters.imports import stage_counters
from routes.registration import put_routes
from settlement.failures import InfeasibleBatchError, SourceBindingError
from tests import DAY, DIAGONAL, FULL, INTO_X, OTHER_DAY, WarehouseCase, archive_ids, oracle_cases


class PublicationTests(WarehouseCase):
    def use_disk_archive(self):
        path = self.directory() / 'archive.sqlite'
        self.archive = self.database(ArchiveStore, path)
        return path

    def assert_unpublished(self, archive, artifact_id):
        with self.assertRaises(UnknownArtifactError):
            get_sealed_batch(archive, artifact_id)
        with self.assertRaises(UnknownArtifactError):
            read_receipt(archive, artifact_id)

    def test_one_route_receipt(self):
        self.register({'A': 3}, {'X': 3}, [('A', 'X')])
        artifact = self.seal()
        self.assertEqual(read_receipt(self.archive, artifact), PublicationReceipt(artifact, DAY, 'c1', 'r1', 3, 3))
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X')]), [3, 3])

    def test_exact_source_pair(self):
        self.register({'A': 3, 'B': 0}, {'X': 3, 'Y': 0}, DIAGONAL)
        self.register({'A': 4, 'B': 0}, {'X': 4, 'Y': 0}, FULL, counts='c2', routes='r2')
        old, new = self.seal(), self.seal('c2', 'r2')
        self.assertNotEqual(old, new)
        self.assertEqual(read_receipt(self.archive, old), PublicationReceipt(old, DAY, 'c1', 'r1', 3, 3))
        self.assertEqual(read_receipt(self.archive, new), PublicationReceipt(new, DAY, 'c2', 'r2', 4, 4))
        original = get_sealed_batch(self.archive, old).evidence
        self.assertEqual(original.open_routes, DIAGONAL)
        self.assertEqual(original.lines, (('A', 3), ('B', 0)))

    def test_source_binding(self):
        path = self.use_disk_archive()
        self.register({'A': 1}, {'X': 1}, [('A', 'X')])
        self.register({'A': 1}, {'X': 1}, [('A', 'X')], counts='later', routes='later', day=OTHER_DAY)
        for counts, routes in (('later', 'r1'), ('c1', 'later'), ('missing', 'r1'), ('c1', 'missing')):
            with self.subTest(counts=counts, routes=routes), self.assertRaises(SourceBindingError):
                self.seal(counts, routes)
        self.assertEqual(archive_ids(path), ((), ()))

    def test_endpoint_coverage(self):
        path = self.use_disk_archive()
        put_routes(self.routes, DAY, 'r1', ['A', 'B'], ['X', 'Y'], DIAGONAL)
        counter_cases = (
            ({'A': 1}, {'X': 1, 'Y': 0}),
            ({'A': 1, 'B': 0}, {'X': 1}),
            ({'A': 1, 'B': 0, 'C': 0}, {'X': 1, 'Y': 0}),
            ({'A': 1, 'B': 0}, {'X': 1, 'Y': 0, 'Z': 0}),
            ({'A': 1, 'Y': 0}, {'X': 1, 'B': 0}),
        )
        for index, (lines, pools) in enumerate(counter_cases):
            revision = f'c{index}'
            stage_counters(self.counters, DAY, revision, lines, pools)
            with self.subTest(lines=lines, pools=pools), self.assertRaises(SourceBindingError):
                self.seal(revision)
        self.assertEqual(archive_ids(path), ((), ()))

    def test_infeasible_balanced_margins(self):
        path = self.use_disk_archive()
        self.register({'A': 1, 'B': 1, 'C': 1}, {'X': 1, 'Y': 1, 'Z': 1}, (
            ('A', 'X'), ('B', 'X'), ('C', 'Y'), ('C', 'Z'),
        ))
        with self.assertRaises(InfeasibleBatchError):
            self.seal()
        self.assert_unpublished(self.archive, 1)
        self.assertEqual(archive_ids(path), ((), ()))

    def test_closed_pool(self):
        path = self.use_disk_archive()
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, INTO_X)
        with self.assertRaises(InfeasibleBatchError):
            self.seal()
        self.assert_unpublished(self.archive, 1)
        self.assertEqual(archive_ids(path), ((), ()))

    def test_unequal_totals(self):
        path = self.use_disk_archive()
        self.register({'A': 2}, {'X': 3}, [('A', 'X')])
        with self.assertRaises(InfeasibleBatchError):
            self.seal()
        self.assertEqual(archive_ids(path), ((), ()))

    def test_restored_route(self):
        opened = [('A', 'X'), ('B', 'X'), ('C', 'Y'), ('C', 'Z')]
        self.register({'A': 1, 'B': 1, 'C': 1}, {'X': 1, 'Y': 1, 'Z': 1}, opened)
        with self.assertRaises(InfeasibleBatchError):
            self.seal()
        put_routes(
            self.routes, DAY, 'r2', ['A', 'B', 'C'], ['X', 'Y', 'Z'], opened + [('A', 'Y')],
        )
        artifact = self.seal(routes='r2')
        self.assertEqual(read_receipt(self.archive, artifact).route_revision, 'r2')
        self.assertEqual(bounds(self.archive, artifact, [('A', 'Y'), ('B', 'X'), ('C', 'Z')]), [3, 3])

    def test_zero_batch(self):
        self.register({'A': 0, 'B': 0}, {'X': 0, 'Y': 0}, [('A', 'X')])
        artifact = self.seal()
        self.assertEqual(read_receipt(self.archive, artifact), PublicationReceipt(artifact, DAY, 'c1', 'r1', 0, 0))
        self.assertEqual(bounds(self.archive, artifact, FULL), [0, 0])
        self.register({}, {}, (), counts='empty', routes='empty')
        self.assertEqual(bounds(self.archive, self.seal('empty', 'empty'), []), [0, 0])

    def test_unknown_receipt(self):
        with self.assertRaises(UnknownArtifactError):
            read_receipt(self.archive, 42)
        with self.assertRaises(UnknownArtifactError):
            read_receipt(self.archive, 1 << 64)

    def test_abort_before_commit(self):
        class AbortPublication(Exception):
            pass

        path = self.use_disk_archive()
        self.register({'A': 3}, {'X': 3}, [('A', 'X')])
        self.register({'A': 4}, {'X': 4}, [('A', 'X')], counts='c2', routes='r2')
        old_id = self.seal()
        previous_ids = ((old_id,), (old_id,))
        self.assertEqual(archive_ids(path), previous_ids)
        observer = self.database(ArchiveStore, path)
        attempted = []

        def abort(artifact_id):
            attempted.append(artifact_id)
            self.assertNotEqual(artifact_id, old_id)
            self.assert_unpublished(observer, artifact_id)
            self.assert_unpublished(self.archive, artifact_id)
            self.assertEqual(archive_ids(path), previous_ids)
            self.assertEqual(read_receipt(observer, old_id).line_total, 3)
            raise AbortPublication('before commit')

        with self.assertRaisesRegex(AbortPublication, 'before commit'):
            self.seal('c2', 'r2', before_commit=abort)
        self.assertEqual(len(attempted), 1)
        self.archive.close()
        observer.close()
        reopened = self.database(ArchiveStore, path)
        self.assert_unpublished(reopened, attempted[0])
        self.assertEqual(archive_ids(path), previous_ids)
        self.assertEqual(read_receipt(reopened, old_id).line_total, 3)
        self.assertEqual(bounds(reopened, old_id, [('A', 'X')]), [3, 3])

    def test_enumerated_feasibility(self):
        accepted = rejected = 0
        for index, (lines, pools, opened, allocations) in enumerate(oracle_cases()):
            revision = str(index)
            self.register(lines, pools, opened, counts=revision, routes=revision)
            with self.subTest(lines=lines, pools=pools, opened=opened):
                if allocations:
                    receipt = read_receipt(self.archive, self.seal(revision, revision))
                    self.assertEqual((receipt.line_total, receipt.pool_total), (sum(lines.values()), sum(pools.values())))
                    accepted += 1
                else:
                    with self.assertRaises(InfeasibleBatchError):
                        self.seal(revision, revision)
                    rejected += 1
        self.assertGreater(accepted, 0)
        self.assertGreater(rejected, 0)

    def test_exact_large_counts(self):
        quantity = 1 << 15000
        self.register({'A': quantity}, {'X': quantity}, [('A', 'X')])
        artifact = self.seal()
        receipt = read_receipt(self.archive, artifact)
        self.assertEqual((receipt.line_total, receipt.pool_total), (quantity, quantity))
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X')]), [quantity, quantity])
