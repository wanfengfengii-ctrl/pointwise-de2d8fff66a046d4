from collections.abc import Iterable

from routes.endpoints import EndpointRoster, RoutePair
from routes.snapshot import RouteRevision


class RouteInputError(ValueError):
    """A route revision does not describe a valid roster and route set."""


def validate_route_registration(
    day: str,
    revision: str,
    lines: Iterable[str],
    pools: Iterable[str],
    open_routes: Iterable[RoutePair],
) -> RouteRevision:
    for field, value in (('day', day), ('revision', revision)):
        if not isinstance(value, str) or not value.strip():
            raise RouteInputError(f'{field} must be nonempty text')
    try:
        roster = EndpointRoster.from_sides(lines, pools)
        records = iter(open_routes)
    except (TypeError, ValueError) as error:
        raise RouteInputError(f'invalid roster or route collection: {error}') from error

    opened: set[RoutePair] = set()
    for record in records:
        if not isinstance(record, (list, tuple)) or len(record) != 2:
            raise RouteInputError('each open route must be a line/pool pair')
        line, pool = record
        if not isinstance(line, str) or not isinstance(pool, str):
            raise RouteInputError('open route endpoints must be text')
        if not roster.contains_route((line, pool)):
            raise RouteInputError(f'route {line!r} -> {pool!r} is outside its side rosters')
        opened.add((line, pool))
    return RouteRevision(day, revision, roster, tuple(sorted(opened)))
