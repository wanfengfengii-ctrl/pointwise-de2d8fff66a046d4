from accounts.bounds import bounds
from accounts.queries import QueryInputError, UnknownEndpointError
from archive.lookup import UnknownArtifactError, read_receipt
from tests import DIAGONAL, FULL, INTO_X, WarehouseCase, oracle_cases, route_subsets


class BoundsTests(WarehouseCase):
    def four_routes(self):
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, FULL)
        return self.seal()

    def test_joint_inbound_bound(self):
        artifact = self.four_routes()
        self.close_sources()
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X')]), [0, 1])
        self.assertEqual(bounds(self.archive, artifact, INTO_X), [1, 1])
        self.assertEqual(bounds(self.archive, artifact, DIAGONAL), [0, 2])

    def test_empty_and_closed_routes(self):
        self.register({'A': 1, 'B': 2}, {'X': 1, 'Y': 2}, DIAGONAL)
        artifact = self.seal()
        self.assertEqual(bounds(self.archive, artifact, []), [0, 0])
        self.assertEqual(bounds(self.archive, artifact, [('B', 'X'), ('B', 'X')]), [0, 0])
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X'), ('B', 'X')]), [1, 1])

    def test_duplicate_open_route(self):
        self.register({'A': 1, 'B': 2}, {'X': 1, 'Y': 2}, DIAGONAL)
        artifact = self.seal()
        repeated = [('A', 'X'), ('A', 'X')]
        self.assertEqual(bounds(self.archive, artifact, repeated), [1, 1])
        self.assertEqual(bounds(self.archive, artifact, [('A', 'X')]), [1, 1])
        self.assertEqual(bounds(self.archive, artifact, iter(repeated)), [1, 1])

    def test_unknown_endpoint(self):
        artifact = self.four_routes()
        for bad in [('A', 'not-a-pool'), ('X', 'X'), ('A', 'B')]:
            with self.subTest(route=bad), self.assertRaises(UnknownEndpointError):
                bounds(self.archive, artifact, [bad])
        self.assertEqual(bounds(self.archive, artifact, INTO_X), [1, 1])

    def test_mixed_endpoints(self):
        artifact = self.four_routes()
        for group in ([*INTO_X, ('A', 'missing')], [('A', 'missing'), *INTO_X]):
            with self.assertRaises(UnknownEndpointError):
                bounds(self.archive, artifact, group)
        self.assertEqual(read_receipt(self.archive, artifact).pool_total, 2)
        self.assertEqual(bounds(self.archive, artifact, INTO_X), [1, 1])

    def test_malformed_route_group(self):
        artifact = self.four_routes()
        for group in (None, 'AX', [('A',)], [([], 'X')]):
            with self.subTest(group=group), self.assertRaises(QueryInputError):
                bounds(self.archive, artifact, group)

    def test_unknown_artifact(self):
        with self.assertRaises(UnknownArtifactError):
            bounds(self.archive, 42, [('A', 'X')])

    def test_swapped_pool_totals(self):
        lines = {'A': 1, 'B': 1, 'C': 1}
        opened = tuple((line, pool) for line in lines for pool in ('X', 'Y'))
        self.register(lines, {'X': 1, 'Y': 2}, opened)
        self.register(lines, {'X': 2, 'Y': 1}, opened, counts='c2')
        old, new = self.seal(), self.seal('c2')
        self.close_sources()
        for artifact in (old, new):
            self.assertEqual(read_receipt(self.archive, artifact).pool_total, 3)
            for route in opened:
                self.assertEqual(bounds(self.archive, artifact, [route]), [0, 1])
        to_x = [(line, 'X') for line in lines]
        self.assertEqual(bounds(self.archive, old, to_x), [1, 1])
        self.assertEqual(bounds(self.archive, new, to_x), [2, 2])

    def test_query_order(self):
        artifact = self.four_routes()
        self.assertEqual(bounds(self.archive, artifact, reversed(DIAGONAL)), [0, 2])
        self.assertEqual(bounds(self.archive, artifact, reversed(INTO_X)), [1, 1])
        self.assertEqual(bounds(self.archive, artifact, DIAGONAL), [0, 2])

        opened = (('A', 'X'), ('A', 'Y'), ('B', 'X'))
        put_again = 'r2'
        self.register({'A': 1, 'B': 1}, {'X': 1, 'Y': 1}, opened, routes=put_again)
        forced = self.seal(routes=put_again)
        self.assertEqual(bounds(self.archive, forced, [('A', 'X')]), [0, 0])
        self.assertEqual(bounds(self.archive, forced, opened[1:]), [2, 2])

    def test_enumerated_oracle(self):
        checked = 0
        for index, (lines, pools, opened, allocations) in enumerate(oracle_cases()):
            if not allocations:
                continue
            revision = str(index)
            self.register(lines, pools, opened, counts=revision, routes=revision)
            artifact = self.seal(revision, revision)
            for selected in route_subsets():
                with self.subTest(lines=lines, pools=pools, opened=opened, selected=selected):
                    values = [sum(flow.get(route, 0) for route in selected) for flow in allocations]
                    self.assertEqual(bounds(self.archive, artifact, selected), [min(values), max(values)])
                    checked += 1
        self.assertGreater(checked, 0)
