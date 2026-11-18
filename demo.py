import json
from contextlib import ExitStack, closing
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from accounts.bounds import bounds
from archive.lookup import read_receipt
from archive.store import ArchiveStore
from counters.imports import collect_counter_entries, stage_counters
from counters.ledger import CounterLedger
from routes.catalog import RouteCatalog
from routes.registration import put_routes
from settlement.admission import certify


def inspect(archive, artifact_id, queries):
    receipt = asdict(read_receipt(archive, artifact_id))
    del receipt['artifact_id']
    return {
        'receipt': receipt,
        'bounds': {name: bounds(archive, artifact_id, group) for name, group in queries.items()},
    }


def register_and_seal(ledger, catalog, archive, day, revision):
    route = put_routes(
        catalog, day, revision['route_revision'], revision['line_roster'],
        revision['pool_roster'], revision['open_routes'],
    )
    counter = stage_counters(
        ledger, day, revision['counter_revision'],
        collect_counter_entries(revision['lines']), collect_counter_entries(revision['pools']),
    )
    return certify(ledger, catalog, archive, day, counter.revision, route.revision)


def main():
    samples = Path(__file__).resolve().parent / 'samples'
    raw = json.loads((samples / 'daily.json').read_text(encoding='utf-8'))
    expected = json.loads((samples / 'expected.json').read_text(encoding='utf-8'))
    old_revision, new_revision = raw['revisions']
    day, queries = raw['day'], raw['queries']
    with TemporaryDirectory() as directory:
        root = Path(directory)
        archive_path = root / 'archive.sqlite'
        with ExitStack() as connected:
            ledger = connected.enter_context(closing(CounterLedger(root / 'counters.sqlite')))
            catalog = connected.enter_context(closing(RouteCatalog(root / 'routes.sqlite')))
            archive = connected.enter_context(closing(ArchiveStore(archive_path)))
            old_id = register_and_seal(ledger, catalog, archive, day, old_revision)
            original = inspect(archive, old_id, queries)
            new_id = register_and_seal(ledger, catalog, archive, day, new_revision)
        with closing(ArchiveStore(archive_path)) as reopened:
            new = inspect(reopened, new_id, queries)
            old = inspect(reopened, old_id, queries)

    if original != expected['old'] or old != expected['old'] or new != expected['new'] or old_id == new_id:
        raise RuntimeError(f'daily sample results differ from the hand calculation: {original!r}, {old!r}, {new!r}')
    print(f'已重开核对旧成果 {old_id} 与同日后续成果 {new_id}')
    record = {
        'case_id': 'v9.published_successor',
        'input': raw,
        'expected': expected['old'],
        'actual': original,
        'downstream_expected': {'old': expected['old'], 'new': expected['new']},
        'downstream_actual': {'old': old, 'new': new},
        'code_paths': [
            'counters/imports.py', 'routes/registration.py', 'settlement/admission.py',
            'archive/store.py', 'archive/lookup.py', 'accounts/bounds.py',
        ],
        'oracle': expected['oracle'],
    }
    print('POINTWISE_SCENARIO ' + json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
