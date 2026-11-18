from routes.catalog import RouteCatalog, RouteRevisionConflict
from routes.registration import put_routes
from routes.snapshot import RouteReceipt
from routes.validation import RouteInputError
from tests import DAY, DIAGONAL, FULL, OTHER_DAY, DatabaseCase


class RouteTests(DatabaseCase):
    def setUp(self):
        self.catalog = self.database(RouteCatalog)

    def test_unknown_pool_route(self):
        receipt = put_routes(self.catalog, DAY, 'r1', ['A'], ['X'], [('A', 'X')])
        with self.assertRaises(RouteInputError):
            put_routes(self.catalog, DAY, 'bad', ['A'], ['X'], [('A', 'missing')])
        self.assertIsNone(self.catalog.get(DAY, 'bad'))
        self.assertEqual(self.catalog.get(DAY, 'r1').receipt, receipt)
        self.assertEqual(self.catalog.get(DAY, 'r1').open_routes, (('A', 'X'),))

    def test_wrong_side(self):
        receipt = put_routes(self.catalog, DAY, 'r1', ['A', 'B'], ['X'], [('A', 'X')])
        for bad_route in (('A', 'B'), ('X', 'X')):
            with self.subTest(route=bad_route), self.assertRaises(RouteInputError):
                put_routes(self.catalog, DAY, 'bad', ['A', 'B'], ['X'], [bad_route])
        self.assertIsNone(self.catalog.get(DAY, 'bad'))
        self.assertEqual(self.catalog.get(DAY, 'r1').receipt, receipt)
        both_sides = put_routes(self.catalog, DAY, 'r2', ['A'], ['A'], [('A', 'A')])
        self.assertEqual(both_sides, RouteReceipt(DAY, 'r2'))

    def test_immutable_retry(self):
        receipt = put_routes(self.catalog, DAY, 'r1', ['A', 'B'], ['X', 'Y'], FULL)
        same = put_routes(self.catalog, DAY, 'r1', ['B', 'A'], ['Y', 'X'], reversed(FULL))
        self.assertEqual(receipt, RouteReceipt(DAY, 'r1'))
        self.assertEqual(same, receipt)
        with self.assertRaises(RouteRevisionConflict):
            put_routes(self.catalog, DAY, 'r1', ['A', 'B'], ['X', 'Y'], DIAGONAL)
        with self.assertRaises(RouteRevisionConflict):
            put_routes(self.catalog, DAY, 'r1', ['A', 'B'], ['X', 'Y', 'Z'], FULL)
        self.assertEqual(self.catalog.get(DAY, 'r1').open_routes, FULL)

    def test_reopen_catalog(self):
        path = self.directory() / 'routes.sqlite'
        first = self.database(RouteCatalog, path)
        original = put_routes(first, DAY, 'r1', ['A', 'B'], ['X', 'Y'], FULL)
        first.close()
        reopened = self.database(RouteCatalog, path)
        saved = reopened.get(DAY, 'r1')
        self.assertEqual(saved.receipt, original)
        self.assertEqual(saved.roster.lines, ('A', 'B'))
        self.assertEqual(saved.roster.pools, ('X', 'Y'))
        put_routes(reopened, DAY, 'r2', ['A', 'B'], ['X', 'Y'], DIAGONAL)
        put_routes(reopened, OTHER_DAY, 'r1', ['A'], ['Z'], [('A', 'Z')])
        reopened.initialize()
        reopened.close()

        final = self.database(RouteCatalog, path)
        self.assertEqual(final.get(DAY, 'r1'), saved)
        self.assertEqual(final.get(DAY, 'r2').open_routes, DIAGONAL)
        self.assertEqual(final.get(OTHER_DAY, 'r1').open_routes, (('A', 'Z'),))
