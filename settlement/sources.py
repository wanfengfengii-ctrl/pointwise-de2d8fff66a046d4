from dataclasses import dataclass

from counters.ledger import CounterLedger
from counters.revisions import CounterRevision
from routes.catalog import RouteCatalog
from routes.snapshot import RouteRevision
from settlement.failures import SourceBindingError


@dataclass(frozen=True, slots=True)
class BoundSources:
    counters: CounterRevision
    routes: RouteRevision


def bind_sources(
    counters: CounterLedger,
    routes: RouteCatalog,
    day: str,
    counter_revision: str,
    route_revision: str,
) -> BoundSources:
    for value in (day, counter_revision, route_revision):
        if not isinstance(value, str) or not value.strip():
            raise SourceBindingError('day and both revision identifiers must be nonempty text')
    counter_snapshot = counters.get(day, counter_revision)
    if counter_snapshot is None:
        raise SourceBindingError(f'missing counter revision {day}/{counter_revision}')
    route_snapshot = routes.get(day, route_revision)
    if route_snapshot is None:
        raise SourceBindingError(f'missing route revision {day}/{route_revision}')
    if (counter_snapshot.day, counter_snapshot.revision) != (day, counter_revision):
        raise SourceBindingError('counter ledger returned a different revision identity')
    if (route_snapshot.day, route_snapshot.revision) != (day, route_revision):
        raise SourceBindingError('route catalog returned a different revision identity')

    differences = route_snapshot.roster.coverage_difference(
        (name for name, _ in counter_snapshot.lines),
        (name for name, _ in counter_snapshot.pools),
    )
    if differences:
        raise SourceBindingError(f'counter endpoint coverage differs from the roster: {differences}')
    return BoundSources(counter_snapshot, route_snapshot)
