from collections.abc import Iterable

from counters.revisions import CounterRows


class CounterInputError(ValueError):
    """An input record cannot be registered in the counter ledger."""


def validate_counter_identity(day: str, revision: str) -> None:
    for field, value in (('day', day), ('revision', revision)):
        if not isinstance(value, str) or not value.strip():
            raise CounterInputError(f'{field} must be nonempty text')


def validate_counter_entries(
    entries: Iterable[tuple[str, int]], side: str = 'counter',
) -> CounterRows:
    try:
        records = iter(entries)
    except TypeError as error:
        raise CounterInputError(f'{side} records must be iterable') from error

    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, (tuple, list)) or len(record) != 2:
            raise CounterInputError(f'{side} record must contain endpoint and liters')
        endpoint, liters = record
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise CounterInputError(f'{side} endpoint must be nonempty text')
        if endpoint in counts:
            raise CounterInputError(f'duplicate {side} endpoint {endpoint!r}')
        if type(liters) is not int or liters < 0:
            raise CounterInputError(f'{side} liters at {endpoint!r} must be a nonnegative integer')
        counts[endpoint] = liters
    return tuple(sorted(counts.items()))
