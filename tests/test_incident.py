"""Regressions for the 2025-04-09 transport reconciliation incident.

These cases pin the two failure modes that the old capacity heuristic missed:
feasibility must reject balanced batches whose open routes cannot jointly
carry every endpoint count, and route-group bounds must be optimized over
complete feasible allocations rather than summed from independent edge
intervals.
"""

from accounts.bounds import bounds
from archive.lookup import get_sealed_batch, read_receipt
from counters.imports import stage_counters
from routes.registration import put_routes
from settlement.failures import InfeasibleBatchError
from tests import DAY, DIAGONAL, FULL, INTO_X, WarehouseCase, archive_ids


class IncidentAdmissionTests(WarehouseCase):
    def test_closed_routes_to_a_pool_reject_without_publication(self):
        path = self.directory() / 'archive.sqlite'
        self.archive = self.database(self.archive.__class__, path)
        lines, pools = {'A': 1, 'B': 1}, {'X': 1, 'Y': 1}
        stage_counters(self.counters, DAY, 'balanced', lines, pools)
        put_routes(self.routes, DAY, 'all', lines, pools, FULL)
        good = self.seal('balanced', 'all')
        put_routes(self.routes, DAY, 'closed-Y', lines, pools, INTO_X)
        with self.assertRaises(InfeasibleBatchError):
            self.seal('balanced', 'closed-Y')
        # Rejection happens before any archive write: no artifact or receipt.
        self.assertEqual(archive_ids(path), ((good,), (good,)))

    def test_three_by_three_hall_violation_rejects(self):
        path = self.directory() / 'archive.sqlite'
        self.archive = self.database(self.archive.__class__, path)
        lines, pools = {'A': 1, 'B': 1, 'C': 1}, {'X': 1, 'Y': 1, 'Z': 1}
        opened = (('A', 'X'), ('B', 'X'), ('C', 'Y'), ('C', 'Z'))
        self.register(lines, pools, opened)
        with self.assertRaises(InfeasibleBatchError):
            self.seal()
        self.assertEqual(archive_ids(path), ((), ()))

    def test_large_scale_hall_violation_rejects(self):
        huge = 1 << 200
        lines, pools = {'A': huge, 'B': huge}, {'X': huge, 'Y': huge}
        self.register(lines, pools, INTO_X)
        with self.assertRaises(InfeasibleBatchError):
            self.seal()

    def test_feasible_again_after_route_revision_restores_capacity(self):
        lines, pools = {'A': 1, 'B': 1, 'C': 1}, {'X': 1, 'Y': 1, 'Z': 1}
        opened = [('A', 'X'), ('B', 'X'), ('C', 'Y'), ('C', 'Z')]
        self.register(lines, pools, opened)
        with self.assertRaises(InfeasibleBatchError):
            self.seal()
        put_routes(
            self.routes, DAY, 'r2', ['A', 'B', 'C'], ['X', 'Y', 'Z'],
            opened + [('A', 'Y')],
        )
        artifact = self.seal(routes='r2')
        self.assertEqual(
            bounds(self.archive, artifact, [('A', 'Y'), ('B', 'X'), ('C', 'Z')]),
            [3, 3],
        )


class IncidentAuditTests(WarehouseCase):
    def test_into_x_coupled_bounds_on_full_batch(self):
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, FULL)
        artifact = self.seal()
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X')]), [0, 1])
        # The incident reported [0, 2] here; X always receives exactly one.
        self.assertEqual(bounds(self.archive, artifact, INTO_X), [1, 1])
        self.assertEqual(bounds(self.archive, artifact, DIAGONAL), [0, 2])

    def test_closed_route_carries_zero_even_when_requested(self):
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, DIAGONAL)
        artifact = self.seal()
        self.assertEqual(bounds(self.archive, artifact, FULL), [2, 2])
        self.assertEqual(bounds(self.archive, artifact, INTO_X), [1, 1])
        self.assertEqual(bounds(self.archive, artifact, [('B', 'X')]), [0, 0])

    def test_offline_reopen_reads_full_two_side_evidence(self):
        path = self.directory() / 'archive.sqlite'
        self.archive = self.database(self.archive.__class__, path)
        lines, pools = {'A': 1, 'B': 1}, {'X': 1, 'Y': 1}
        self.register(lines, pools, FULL)
        artifact = self.seal()
        self.close_sources()
        self.archive.close()

        reopened = self.database(self.archive.__class__, path)
        evidence = get_sealed_batch(reopened, artifact).evidence
        self.assertEqual(evidence.lines, (('A', 1), ('B', 1)))
        self.assertEqual(evidence.pools, (('X', 1), ('Y', 1)))
        self.assertEqual(evidence.open_routes, FULL)
        self.assertEqual(bounds(reopened, artifact, INTO_X), [1, 1])
        receipt = read_receipt(reopened, artifact)
        self.assertEqual((receipt.line_total, receipt.pool_total), (2, 2))

    def test_bounds_independent_endpoints_need_not_share_one_allocation(self):
        # The min and max may come from different complete allocations.
        self.register({'A': 2, 'B': 2}, {'X': 2, 'Y': 2}, FULL)
        artifact = self.seal()
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X')]), [0, 2])
        self.assertEqual(bounds(self.archive, artifact, INTO_X), [2, 2])
        self.assertEqual(bounds(self.archive, artifact, DIAGONAL), [0, 4])
