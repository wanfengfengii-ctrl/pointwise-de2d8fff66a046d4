from collections.abc import Iterable, Mapping

from counters.ledger import CounterLedger
from counters.revisions import CounterReceipt, CounterRevision
from counters.validation import (
    CounterInputError, validate_counter_entries, validate_counter_identity,
)


def collect_counter_entries(entries: Iterable[tuple[str, int]]) -> dict[str, int]:
    """Read raw named records before conversion can hide duplicate endpoints."""
    return dict(validate_counter_entries(entries))


def stage_counters(
    ledger: CounterLedger,
    day: str,
    revision: str,
    lines: Mapping[str, int],
    pools: Mapping[str, int],
) -> CounterReceipt:
    validate_counter_identity(day, revision)
    if not isinstance(lines, Mapping) or not isinstance(pools, Mapping):
        raise CounterInputError('line and pool counters must be mappings')
    return ledger.put(CounterRevision(
        day, revision,
        validate_counter_entries(lines.items(), 'line'),
        validate_counter_entries(pools.items(), 'pool'),
    ))
