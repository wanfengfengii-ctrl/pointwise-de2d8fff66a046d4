import json
from collections.abc import Iterable

from counters.revisions import CounterRevision, CounterRows


def pack_counter_rows(rows: CounterRows) -> list[tuple[str, str]]:
    # Hexadecimal round-trips arbitrary Python integers without decimal digit limits.
    return [(endpoint, hex(liters)) for endpoint, liters in rows]


def unpack_counter_rows(rows: Iterable[tuple[str, str]]) -> CounterRows:
    return tuple((endpoint, int(liters, 16)) for endpoint, liters in rows)


def encode_counter_revision(revision: CounterRevision) -> str:
    return json.dumps({
        'day': revision.day,
        'revision': revision.revision,
        'lines': pack_counter_rows(revision.lines),
        'pools': pack_counter_rows(revision.pools),
    }, separators=(',', ':'))


def decode_counter_revision(payload: str) -> CounterRevision:
    data = json.loads(payload)
    return CounterRevision(
        data['day'], data['revision'],
        unpack_counter_rows(data['lines']), unpack_counter_rows(data['pools']),
    )
