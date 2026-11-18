from counters.imports import collect_counter_entries, stage_counters
from counters.ledger import CounterLedger, CounterRevisionConflict
from counters.revisions import CounterReceipt
from counters.validation import CounterInputError
from tests import DAY, OTHER_DAY, DatabaseCase


class CounterTests(DatabaseCase):
    def setUp(self):
        self.ledger = self.database(CounterLedger)

    def test_zero_and_identical_retry(self):
        lines = collect_counter_entries(iter([('B', 3), ('A', 0)]))
        receipt = stage_counters(self.ledger, DAY, 'c1', lines, {'X': 3})
        repeat = stage_counters(self.ledger, DAY, 'c1', {'B': 3, 'A': 0}, {'X': 3})
        saved = self.ledger.get(DAY, 'c1')
        self.assertEqual(receipt, CounterReceipt(DAY, 'c1'))
        self.assertEqual(repeat, receipt)
        self.assertEqual(saved.lines, (('A', 0), ('B', 3)))
        self.assertEqual(saved.totals, (3, 3))

    def test_conflicting_retry(self):
        receipt = stage_counters(self.ledger, DAY, 'c1', {'A': 2}, {'X': 2})
        with self.assertRaises(CounterRevisionConflict):
            stage_counters(self.ledger, DAY, 'c1', {'A': 3}, {'X': 2})
        saved = self.ledger.get(DAY, 'c1')
        self.assertEqual(saved.lines, (('A', 2),))
        self.assertEqual(saved.pools, (('X', 2),))
        self.assertEqual(saved.receipt, receipt)

    def test_same_total_conflict(self):
        receipt = stage_counters(self.ledger, DAY, 'c1', {'A': 1, 'B': 2}, {'X': 3})
        with self.assertRaises(CounterRevisionConflict):
            stage_counters(self.ledger, DAY, 'c1', {'A': 2, 'B': 1}, {'X': 3})
        saved = self.ledger.get(DAY, 'c1')
        self.assertEqual(saved.lines, (('A', 1), ('B', 2)))
        self.assertEqual(saved.receipt, receipt)
        pool_receipt = stage_counters(self.ledger, DAY, 'c2', {'A': 3}, {'X': 1, 'Y': 2})
        with self.assertRaises(CounterRevisionConflict):
            stage_counters(self.ledger, DAY, 'c2', {'A': 3}, {'X': 2, 'Y': 1})
        self.assertEqual(self.ledger.get(DAY, 'c2').receipt, pool_receipt)
        self.assertEqual(self.ledger.get(DAY, 'c2').pools, (('X', 1), ('Y', 2)))

    def test_invalid_entries(self):
        for invalid in (-1, True, False, 1.0, '1', None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(CounterInputError):
                    stage_counters(self.ledger, DAY, 'bad', {'A': invalid}, {'X': 1})
                with self.assertRaises(CounterInputError):
                    stage_counters(self.ledger, DAY, 'bad', {'A': 1}, {'X': invalid})
                self.assertIsNone(self.ledger.get(DAY, 'bad'))
        for records in ([('A', 0), ('A', 1)], [('A',)], [(None, 0)], [(' ', 0)], None):
            with self.subTest(records=records):
                with self.assertRaises(CounterInputError):
                    collect_counter_entries(records)
        with self.assertRaises(CounterInputError):
            stage_counters(self.ledger, DAY, 'bad', [('A', 1)], {'X': 1})
        with self.assertRaises(CounterInputError):
            stage_counters(self.ledger, DAY, '', {'A': 1}, {'X': 1})
        self.assertIsNone(self.ledger.get(DAY, 'bad'))

    def test_reopen_ledger(self):
        path = self.directory() / 'counters.sqlite'
        first = self.database(CounterLedger, path)
        receipt = stage_counters(first, DAY, 'c1', {'A': 0, 'B': 3}, {'X': 3})
        first.close()

        reopened = self.database(CounterLedger, path)
        saved = reopened.get(DAY, 'c1')
        self.assertEqual(saved.lines, (('A', 0), ('B', 3)))
        self.assertEqual(saved.pools, (('X', 3),))
        self.assertEqual(stage_counters(reopened, DAY, 'c1', {'B': 3, 'A': 0}, {'X': 3}), receipt)
        stage_counters(reopened, DAY, 'c2', {'A': 1, 'B': 3}, {'X': 4})
        stage_counters(reopened, OTHER_DAY, 'c1', {'A': 2}, {'X': 2})
        reopened.initialize()
        reopened.close()

        final = self.database(CounterLedger, path)
        self.assertEqual(final.get(DAY, 'c1'), saved)
        self.assertEqual(final.get(DAY, 'c2').lines, (('A', 1), ('B', 3)))
        self.assertEqual(final.get(OTHER_DAY, 'c1').lines, (('A', 2),))
