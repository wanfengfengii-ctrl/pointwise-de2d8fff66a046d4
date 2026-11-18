"""Regression fixtures and independent small integer allocation oracle."""

import sqlite3
import unittest
from contextlib import closing
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.store import ArchiveStore
from counters.imports import stage_counters
from counters.ledger import CounterLedger
from routes.catalog import RouteCatalog
from routes.registration import put_routes
from settlement.admission import certify

DAY = '2025-04-09'
OTHER_DAY = '2025-04-10'
FULL = (('A', 'X'), ('A', 'Y'), ('B', 'X'), ('B', 'Y'))
INTO_X = (('A', 'X'), ('B', 'X'))
DIAGONAL = (('A', 'X'), ('B', 'Y'))


class DatabaseCase(unittest.TestCase):
    def database(self, factory, path=':memory:'):
        db = factory(path)
        self.addCleanup(db.close)
        return db

    def directory(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)


class WarehouseCase(DatabaseCase):
    def setUp(self):
        self.counters = self.database(CounterLedger)
        self.routes = self.database(RouteCatalog)
        self.archive = self.database(ArchiveStore)

    def register(self, lines, pools, opened, *, counts='c1', routes='r1', day=DAY):
        put_routes(self.routes, day, routes, lines, pools, opened)
        stage_counters(self.counters, day, counts, lines, pools)

    def seal(self, counts='c1', routes='r1', *, day=DAY, before_commit=None):
        return certify(
            self.counters, self.routes, self.archive, day, counts, routes,
            before_commit=before_commit,
        )

    def close_sources(self):
        self.counters.close()
        self.routes.close()


def archive_ids(path):
    with closing(sqlite3.connect(path)) as connection:
        return tuple(
            tuple(row[0] for row in connection.execute(f'SELECT artifact_id FROM {table} ORDER BY artifact_id'))
            for table in ('artifacts', 'receipts')
        )


def route_subsets():
    for mask in product((False, True), repeat=len(FULL)):
        yield tuple(route for route, included in zip(FULL, mask) if included)


def oracle_cases():
    for a, b, x, y in product(range(3), repeat=4):
        if a + b != x + y:
            continue
        lines, pools = {'A': a, 'B': b}, {'X': x, 'Y': y}
        for opened in route_subsets():
            choices = [range(1 + min(lines[line], pools[pool])) for line, pool in opened]
            solutions = []
            for assignment in product(*choices):
                flow = dict(zip(opened, assignment))
                if any(sum(v for (l, _), v in flow.items() if l == name) != count
                       for name, count in lines.items()):
                    continue
                if any(sum(v for (_, p), v in flow.items() if p == name) != count
                       for name, count in pools.items()):
                    continue
                solutions.append(flow)
            yield lines, pools, opened, solutions
