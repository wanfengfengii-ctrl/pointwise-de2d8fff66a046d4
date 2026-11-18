from dataclasses import dataclass

from counters.revisions import CounterRows
from routes.endpoints import RoutePair
from settlement.sources import BoundSources


@dataclass(frozen=True, slots=True)
class AllocationEvidence:
    day: str
    counter_revision: str
    route_revision: str
    lines: CounterRows
    pools: CounterRows
    open_routes: tuple[RoutePair, ...]

    @property
    def totals(self) -> tuple[int, int]:
        return (
            sum(liters for _, liters in self.lines),
            sum(liters for _, liters in self.pools),
        )


def build_allocation_evidence(sources: BoundSources) -> AllocationEvidence:
    counters, routes = sources.counters, sources.routes
    return AllocationEvidence(
        counters.day, counters.revision, routes.revision,
        counters.lines, counters.pools, routes.open_routes,
    )
