from collections.abc import Iterable

from archive.artifacts import SealedBatch
from routes.endpoints import RoutePair


class QueryInputError(ValueError):
    """The requested group does not consist of route pairs."""


class UnknownEndpointError(QueryInputError):
    """An endpoint is absent from its side of the sealed roster."""


def normalize_query_routes(
    batch: SealedBatch, routes: Iterable[RoutePair],
) -> frozenset[RoutePair]:
    if isinstance(routes, (str, bytes)):
        raise QueryInputError('a route group must be a collection of pairs')
    try:
        records = iter(routes)
    except TypeError as error:
        raise QueryInputError('a route group must be iterable') from error

    evidence = batch.evidence
    lines = {name for name, _ in evidence.lines}
    pools = {name for name, _ in evidence.pools}
    requested: set[RoutePair] = set()
    for record in records:
        if not isinstance(record, (tuple, list)) or len(record) != 2:
            raise QueryInputError('each requested route must be a line/pool pair')
        line, pool = record
        if not isinstance(line, str) or not isinstance(pool, str):
            raise QueryInputError('requested endpoint names must be text')
        if line not in lines or pool not in pools:
            raise UnknownEndpointError(f'unknown endpoint in {line!r} -> {pool!r}')
        requested.add((line, pool))
    return frozenset(requested.intersection(evidence.open_routes))
